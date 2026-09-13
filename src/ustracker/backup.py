from __future__ import annotations

import io
import json
import shutil
import struct
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto import b64d, b64e, derive_backup_key, random_bytes, sha256_hex
from .db import Database

MAGIC = b'USTRACKER_LOCAL_BACKUP_V1\n'
UTC = timezone.utc
DEFAULT_RETENTION = 14


def create_backup(root: Path, db: Database, vrk: bytes) -> Path:
    root = Path(root)
    out_dir = root / 'UserData' / 'Backups'
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot = out_dir / f'._snapshot_{db.environment}.db'
    snapshot.unlink(missing_ok=True)
    # DELETE journal mode + exclusive lock gives a self-consistent file snapshot.
    con = db.connect()
    try:
        con.execute('BEGIN EXCLUSIVE')
        shutil.copy2(db.path, snapshot)
        con.rollback()
    finally:
        con.close()
    mem = io.BytesIO()
    try:
        with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(snapshot, arcname='database/ustracker.db')
            media_root = root / 'UserData' / 'Media' / db.environment
            if media_root.exists():
                for p in media_root.rglob('*'):
                    if p.is_file():
                        z.write(p, arcname='media/' + p.relative_to(media_root).as_posix())
            public = root / 'UserData' / 'Public' / 'production' / 'view.json'
            if db.environment == 'production' and public.exists():
                z.write(public, arcname='public/view.json')
    finally:
        snapshot.unlink(missing_ok=True)
    payload = mem.getvalue()
    salt = random_bytes(16)
    nonce = random_bytes(12)
    key = derive_backup_key(vrk, salt)
    header = {
        'version': 1,
        'environment': db.environment,
        'salt': b64e(salt),
        'nonce': b64e(nonce),
        'sha256_plain': sha256_hex(payload),
        'created_at': datetime.now(UTC).isoformat(),
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(',', ':')).encode()
    cipher = AESGCM(key).encrypt(nonce, payload, header_bytes)
    name = f"UStracker_{db.environment}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.usbk"
    path = out_dir / name
    path.write_bytes(MAGIC + struct.pack('>I', len(header_bytes)) + header_bytes + cipher)
    verify_backup(path, vrk)
    return path


def _decrypt(path: Path, vrk: bytes) -> tuple[dict, bytes]:
    raw = Path(path).read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError('invalid backup magic')
    off = len(MAGIC)
    if len(raw) < off + 4:
        raise ValueError('truncated backup')
    hlen = struct.unpack('>I', raw[off:off + 4])[0]
    if hlen < 2 or hlen > 65536 or len(raw) < off + 4 + hlen:
        raise ValueError('invalid header size')
    hb = raw[off + 4:off + 4 + hlen]
    header = json.loads(hb)
    key = derive_backup_key(vrk, b64d(header['salt']))
    plain = AESGCM(key).decrypt(b64d(header['nonce']), raw[off + 4 + hlen:], hb)
    if sha256_hex(plain) != header['sha256_plain']:
        raise ValueError('backup hash mismatch')
    return header, plain


def verify_backup(path: Path, vrk: bytes) -> dict:
    header, plain = _decrypt(path, vrk)
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        names = z.namelist()
        if 'database/ustracker.db' not in names:
            raise ValueError('database missing from backup')
        for n in names:
            if n.startswith('/') or '..' in Path(n).parts:
                raise ValueError('unsafe backup member')
    return header


def restore_backup(root: Path, db: Database, vrk: bytes, path: Path) -> None:
    header, plain = _decrypt(path, vrk)
    if header['environment'] != db.environment:
        raise ValueError('backup environment mismatch')
    root = Path(root)
    staging = Path(tempfile.mkdtemp(prefix='ustracker-restore-', dir=str(root / 'UserData')))
    old = db.path.with_suffix('.pre_restore')
    try:
        with zipfile.ZipFile(io.BytesIO(plain)) as z:
            for n in z.namelist():
                if n.startswith('/') or '..' in Path(n).parts:
                    raise ValueError('unsafe backup member')
            z.extractall(staging)
        candidate = staging / 'database' / 'ustracker.db'
        if not candidate.exists():
            raise ValueError('backup database candidate missing')
        if old.exists():
            old.unlink()
        if db.path.exists():
            shutil.copy2(db.path, old)
        shutil.copy2(candidate, db.path)
        try:
            test = Database(root, db.environment, db.key)
            test.one("SELECT value FROM meta WHERE key='schema_version'")
        except Exception:
            if old.exists():
                shutil.copy2(old, db.path)
            raise
        media_src = staging / 'media'
        media_dst = root / 'UserData' / 'Media' / db.environment
        if media_src.exists():
            if media_dst.exists():
                shutil.rmtree(media_dst)
            shutil.copytree(media_src, media_dst)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def prune_backups(root: Path | str, environment: str, keep: int = DEFAULT_RETENTION) -> list[str]:
    keep = max(1, min(100, int(keep)))
    directory = Path(root) / 'UserData' / 'Backups'
    directory.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        directory.glob(f'UStracker_{environment}_*.usbk'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed: list[str] = []
    for path in candidates[keep:]:
        path.unlink(missing_ok=True)
        removed.append(path.name)
    return removed


def maybe_automatic_backup(
    root: Path | str,
    db: Database,
    vrk: bytes,
    *,
    interval_hours: int = 24,
    retention: int = DEFAULT_RETENTION,
) -> Path | None:
    root = Path(root)
    state_dir = root / 'UserData' / 'State'
    state_dir.mkdir(parents=True, exist_ok=True)
    marker = state_dir / f'auto_backup_{db.environment}.json'
    current = datetime.now(UTC)
    if marker.exists():
        try:
            data = json.loads(marker.read_text(encoding='utf-8'))
            last = datetime.fromisoformat(data['at'])
            if current - last < timedelta(hours=max(1, interval_hours)):
                return None
        except Exception:
            pass
    backup = create_backup(root, db, vrk)
    prune_backups(root, db.environment, retention)
    tmp = marker.with_suffix('.tmp')
    tmp.write_text(json.dumps({'at': current.isoformat(), 'backup': backup.name}), encoding='utf-8')
    tmp.replace(marker)
    return backup
