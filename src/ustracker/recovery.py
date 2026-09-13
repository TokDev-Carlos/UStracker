from __future__ import annotations

import argparse
import io
import json
import shutil
import struct
import zipfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .crypto import b64d, b64e, random_bytes, sha256_hex

MAGIC = b'USTRACKER_RECOVERY_EXPORT_V1\n'
AAD = b'UStracker/recovery/v1'
RECOVERY_ROOTS = (
    'UserData/Auth',
    'UserData/Production',
    'UserData/Test',
    'UserData/Media',
    'UserData/Public',
)


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
    root = Path(root).resolve()
    output = Path(output).resolve()
    mem = io.BytesIO()
    included: list[str] = []
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel_root in RECOVERY_ROOTS:
            base = root / rel_root
            if not base.exists():
                continue
            for path in sorted(p for p in base.rglob('*') if p.is_file()):
                rel = path.relative_to(root).as_posix()
                _safe(rel)
                z.write(path, arcname=rel)
                included.append(rel)
        if not any(x.startswith('UserData/Auth/') for x in included):
            raise ValueError('AuthStore is missing; recovery export refused')
        if not any(x.startswith(('UserData/Production/', 'UserData/Test/')) for x in included):
            raise ValueError('operational dataset is missing; recovery export refused')
    payload = mem.getvalue()
    salt = random_bytes(16)
    nonce = random_bytes(12)
    key = _derive(passphrase, salt)
    header = {
        'version': 1,
        'salt': b64e(salt),
        'nonce': b64e(nonce),
        'sha256_plain': sha256_hex(payload),
        'member_count': len(included),
    }
    hb = json.dumps(header, sort_keys=True, separators=(',', ':')).encode('utf-8')
    cipher = AESGCM(key).encrypt(nonce, payload, AAD + hb)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(MAGIC + struct.pack('>I', len(hb)) + hb + cipher)
    return output


def inspect_recovery(package: Path | str, passphrase: str) -> dict:
    raw = Path(package).read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError('invalid recovery package')
    offset = len(MAGIC)
    if len(raw) < offset + 4:
        raise ValueError('truncated recovery package')
    hlen = struct.unpack('>I', raw[offset:offset + 4])[0]
    if hlen < 2 or hlen > 65536 or len(raw) < offset + 4 + hlen:
        raise ValueError('invalid recovery header')
    hb = raw[offset + 4:offset + 4 + hlen]
    header = json.loads(hb)
    key = _derive(passphrase, b64d(header['salt']))
    payload = AESGCM(key).decrypt(b64d(header['nonce']), raw[offset + 4 + hlen:], AAD + hb)
    if sha256_hex(payload) != header['sha256_plain']:
        raise ValueError('recovery hash mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        names = z.namelist()
        for name in names:
            _safe(name)
        if not any(x.startswith('UserData/Auth/') for x in names):
            raise ValueError('recovery package has no AuthStore')
        if not any(x.startswith(('UserData/Production/', 'UserData/Test/')) for x in names):
            raise ValueError('recovery package has no operational dataset')
    return {'header': header, 'payload': payload, 'members': names}


def import_recovery(package: Path | str, destination: Path | str, passphrase: str) -> Path:
    inspected = inspect_recovery(package, passphrase)
    payload = inspected['payload']
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / '.recovery-staging'
    backup = destination / '.recovery-previous'
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for name in z.namelist():
                rel = _safe(name)
                target = staging.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
        staged_userdata = staging / 'UserData'
        if not staged_userdata.exists():
            raise ValueError('recovery package has no UserData')
        live_userdata = destination / 'UserData'
        live_userdata.mkdir(parents=True, exist_ok=True)
        backup.mkdir(parents=True, exist_ok=True)
        for name in ('Auth', 'Production', 'Test', 'Media', 'Public'):
            src = staged_userdata / name
            dst = live_userdata / name
            old = backup / name
            if dst.exists():
                shutil.move(str(dst), str(old))
            if src.exists():
                shutil.move(str(src), str(dst))
        # Local state must never travel between machines.
        shutil.rmtree(live_userdata / 'State', ignore_errors=True)
    except Exception:
        live_userdata = destination / 'UserData'
        if backup.exists():
            for old in list(backup.iterdir()):
                dst = live_userdata / old.name
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst, ignore_errors=True)
                    else:
                        dst.unlink(missing_ok=True)
                shutil.move(str(old), str(dst))
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description='UStracker encrypted recovery package')
    sub = parser.add_subparsers(dest='command', required=True)
    exp = sub.add_parser('export')
    exp.add_argument('--root', required=True)
    exp.add_argument('--output', required=True)
    exp.add_argument('--passphrase', required=True)
    imp = sub.add_parser('import')
    imp.add_argument('--package', required=True)
    imp.add_argument('--destination', required=True)
    imp.add_argument('--passphrase', required=True)
    args = parser.parse_args()
    if args.command == 'export':
        export_recovery(args.root, args.output, args.passphrase)
    else:
        import_recovery(args.package, args.destination, args.passphrase)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
