from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image, ImageOps

from .crypto import random_bytes
from .db import Database
from .services import audit, now, uid

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000


def _encode(data: bytes, max_px: int, quality: int) -> tuple[bytes, int, int]:
    if len(data) > MAX_BYTES:
        raise ValueError('image exceeds 20 MiB')
    with Image.open(io.BytesIO(data)) as im:
        if getattr(im, 'n_frames', 1) != 1:
            raise ValueError('animated images are not supported')
        if im.width * im.height > MAX_PIXELS:
            raise ValueError('image exceeds 40 MP')
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, format='WEBP', quality=quality, method=6)
        return out.getvalue(), im.width, im.height


def _seal(key: bytes, payload: bytes, aad: bytes) -> bytes:
    nonce = random_bytes(12)
    return nonce + AESGCM(key).encrypt(nonce, payload, aad)


def _open(key: bytes, payload: bytes, aad: bytes) -> bytes:
    return AESGCM(key).decrypt(payload[:12], payload[12:], aad)


def _journal_dir(root: Path) -> Path:
    path = root / 'UserData' / 'State' / 'media-journal'
    path.mkdir(parents=True, exist_ok=True)
    return path


def recover_media_journals(root: Path | str, db: Database) -> dict:
    root = Path(root)
    repaired = 0
    removed = 0
    for journal in _journal_dir(root).glob('*.json'):
        try:
            data = json.loads(journal.read_text(encoding='utf-8'))
            if data.get('environment') != db.environment:
                continue
            row = db.one('SELECT id FROM media WHERE id=?', (data['id'],))
            entries = data.get('files') or []
            if row:
                ok = True
                for entry in entries:
                    pending = root / entry['pending']
                    final = root / entry['final']
                    if not final.exists() and pending.exists():
                        final.parent.mkdir(parents=True, exist_ok=True)
                        pending.replace(final)
                        repaired += 1
                    if not final.exists():
                        ok = False
                if ok:
                    journal.unlink(missing_ok=True)
            else:
                for entry in entries:
                    (root / entry['pending']).unlink(missing_ok=True)
                    (root / entry['final']).unlink(missing_ok=True)
                    removed += 1
                journal.unlink(missing_ok=True)
        except Exception:
            continue
    return {'repaired': repaired, 'removed_orphans': removed}


def store(root: Path, db: Database, actor: int, media_key: bytes, entity_type: str, entity_id: str, data: bytes, retain_original: bool = False) -> dict:
    operational, w, h = _encode(data, 1920, 82)
    thumb, _, _ = _encode(data, 320, 75)
    mid = uid()
    root = Path(root)
    base = root / 'UserData' / 'Media' / db.environment
    base.mkdir(parents=True, exist_ok=True)
    op_path = base / f'{mid}.webp.aead'
    th_path = base / f'{mid}.thumb.webp.aead'
    orig_path = base / f'{mid}.original.aead' if retain_original else None
    payloads = [
        (op_path, _seal(media_key, operational, f'{mid}:operational:v1'.encode())),
        (th_path, _seal(media_key, thumb, f'{mid}:thumb:v1'.encode())),
    ]
    if orig_path:
        payloads.append((orig_path, _seal(media_key, data, f'{mid}:original:v1'.encode())))
    files = []
    for final, payload in payloads:
        pending = final.with_suffix(final.suffix + '.pending')
        pending.write_bytes(payload)
        files.append({'pending': str(pending.relative_to(root)), 'final': str(final.relative_to(root))})
    journal = _journal_dir(root) / f'{mid}.json'
    journal.write_text(json.dumps({'id': mid, 'environment': db.environment, 'files': files}, indent=2), encoding='utf-8')
    rec = {
        'id': mid,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'variant_path': str(op_path.relative_to(root)),
        'thumb_path': str(th_path.relative_to(root)),
        'original_path': str(orig_path.relative_to(root)) if orig_path else None,
        'mime': 'image/webp',
        'width': w,
        'height': h,
        'sha256': hashlib.sha256(operational).hexdigest(),
        'created_at': now(),
    }
    try:
        with db.transaction() as con:
            con.execute(
                '''INSERT INTO media(id,entity_type,entity_id,variant_path,thumb_path,original_path,mime,width,height,sha256,created_at)
                   VALUES(:id,:entity_type,:entity_id,:variant_path,:thumb_path,:original_path,:mime,:width,:height,:sha256,:created_at)''',
                rec,
            )
            audit(con, actor, 'MEDIA_CREATE', 'media', mid, None, {k:v for k,v in rec.items() if k not in {'variant_path','thumb_path','original_path'}})
        for entry in files:
            pending = root / entry['pending']
            final = root / entry['final']
            pending.replace(final)
        journal.unlink(missing_ok=True)
        return rec
    except Exception:
        recover_media_journals(root, db)
        raise


def load(root: Path, db: Database, media_key: bytes, mid: str, variant: str = 'operational') -> tuple[bytes, str]:
    row = db.one('SELECT * FROM media WHERE id=?', (mid,))
    if not row:
        raise KeyError('media not found')
    col = {'operational':'variant_path','thumb':'thumb_path','original':'original_path'}.get(variant)
    if not col or not row[col]:
        raise KeyError('variant not found')
    raw = (Path(root) / row[col]).read_bytes()
    return _open(media_key, raw, f'{mid}:{variant}:v1'.encode()), ('image/webp' if variant != 'original' else 'application/octet-stream')
