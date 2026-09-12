from __future__ import annotations

import io
import json
import os
import shutil
import struct
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .crypto import b64d, b64e, random_bytes, sha256_hex

MAGIC = b'USTRACKER_RECOVERY_EXPORT_V1\n'
AAD = b'UStracker/recovery/v1'


def _derive(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 12:
        raise ValueError('recovery passphrase must contain at least 12 characters')
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(passphrase.encode('utf-8'))


def _safe(name: str) -> PurePosixPath:
    p = PurePosixPath(name.replace('\\', '/'))
    if p.is_absolute() or '..' in p.parts or ':' in name:
        raise ValueError('unsafe recovery member')
    return p


def export_recovery(root: Path | str, output: Path | str, passphrase: str) -> Path:
    root = Path(root)
    output = Path(output)
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        # Recovery intentionally includes Auth/Vault plus operational datasets when present.
        for rel_root in ('UserData/Auth', 'UserData/Data', 'UserData/Media', 'UserData/Public'):
            base = root / rel_root
            if not base.exists():
                continue
            for path in sorted(p for p in base.rglob('*') if p.is_file()):
                rel = path.relative_to(root).as_posix()
                _safe(rel)
                z.write(path, arcname=rel)
    payload = mem.getvalue()
    salt = random_bytes(16)
    nonce = random_bytes(12)
    key = _derive(passphrase, salt)
    header = {'version': 1, 'salt': b64e(salt), 'nonce': b64e(nonce), 'sha256_plain': sha256_hex(payload)}
    hb = json.dumps(header, sort_keys=True, separators=(',', ':')).encode('utf-8')
    cipher = AESGCM(key).encrypt(nonce, payload, AAD + hb)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(MAGIC + struct.pack('>I', len(hb)) + hb + cipher)
    return output


def import_recovery(package: Path | str, destination: Path | str, passphrase: str) -> Path:
    raw = Path(package).read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError('invalid recovery package')
    offset = len(MAGIC)
    hlen = struct.unpack('>I', raw[offset:offset + 4])[0]
    if hlen < 2 or hlen > 65536:
        raise ValueError('invalid recovery header')
    hb = raw[offset + 4:offset + 4 + hlen]
    header = json.loads(hb)
    key = _derive(passphrase, b64d(header['salt']))
    payload = AESGCM(key).decrypt(b64d(header['nonce']), raw[offset + 4 + hlen:], AAD + hb)
    if sha256_hex(payload) != header['sha256_plain']:
        raise ValueError('recovery hash mismatch')
    destination = Path(destination)
    staging = destination.with_name(destination.name + '.staging')
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for name in z.namelist():
                rel = _safe(name)
                target = staging.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination
