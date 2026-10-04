from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image, ImageOps

from .crypto import random_bytes
from .db import Database
from .paths import resolve_stored_path
from .services import audit, now, uid

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000


def _encode(data: bytes, max_px: int, quality: int, *, allowed_formats: set[str] | None = None) -> tuple[bytes, int, int]:
    if len(data) > MAX_BYTES:
        raise ValueError('image exceeds 20 MiB')
    with Image.open(io.BytesIO(data)) as im:
        if allowed_formats is not None and (im.format or '').upper() not in allowed_formats:
            raise ValueError('client photos must be JPEG, PNG or WebP')
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
                    pending = resolve_stored_path(root, entry['pending'])
                    final = resolve_stored_path(root, entry['final'])
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
                    resolve_stored_path(root, entry['pending']).unlink(missing_ok=True)
                    resolve_stored_path(root, entry['final']).unlink(missing_ok=True)
                    removed += 1
                journal.unlink(missing_ok=True)
        except Exception:
            continue
    return {'repaired': repaired, 'removed_orphans': removed}


def store(root: Path, db: Database, actor: int, media_key: bytes, entity_type: str, entity_id: str, data: bytes, retain_original: bool = False) -> dict:
    allowed_formats = {'JPEG','PNG','WEBP'} if entity_type == 'client' else None
    operational, w, h = _encode(data, 1920, 82, allowed_formats=allowed_formats)
    thumb, _, _ = _encode(data, 320, 75, allowed_formats=allowed_formats)
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
        files.append({'pending': pending.relative_to(root).as_posix(), 'final': final.relative_to(root).as_posix()})
    journal = _journal_dir(root) / f'{mid}.json'
    journal.write_text(json.dumps({'id': mid, 'environment': db.environment, 'files': files}, indent=2), encoding='utf-8')
    rec = {
        'id': mid,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'variant_path': op_path.relative_to(root).as_posix(),
        'thumb_path': th_path.relative_to(root).as_posix(),
        'original_path': orig_path.relative_to(root).as_posix() if orig_path else None,
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
            pending = resolve_stored_path(root, entry['pending'])
            final = resolve_stored_path(root, entry['final'])
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
    raw = resolve_stored_path(root, row[col]).read_bytes()
    return _open(media_key, raw, f'{mid}:{variant}:v1'.encode()), ('image/webp' if variant != 'original' else 'application/octet-stream')


def remove(root: Path | str, db: Database, actor: int, mid: str) -> dict:
    root = Path(root)
    row = db.one('SELECT * FROM media WHERE id=?', (mid,))
    if not row:
        raise KeyError('media not found')
    public = {key: row[key] for key in ('id', 'entity_type', 'entity_id', 'mime', 'width', 'height', 'sha256', 'created_at')}
    with db.transaction() as con:
        con.execute('DELETE FROM media WHERE id=?', (mid,))
        audit(con, actor, 'MEDIA_DELETE', 'media', mid, public, None)
    for column in ('variant_path', 'thumb_path', 'original_path'):
        relative = row[column]
        if relative:
            try:
                resolve_stored_path(root, relative).unlink(missing_ok=True)
            except ValueError:
                pass
    return {'id': mid, 'removed': True}
