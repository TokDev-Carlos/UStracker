from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

MANIFEST = 'manifest.json'
SIGNATURE = 'manifest.sig'
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def _safe_relative(name: str) -> PurePosixPath:
    p = PurePosixPath(name.replace('\\', '/'))
    if p.is_absolute() or '..' in p.parts or ':' in name or not p.parts:
        raise ValueError(f'unsafe package path: {name}')
    return p


def _payload_files(source: Path) -> list[dict]:
    items: list[dict] = []
    for path in sorted(p for p in source.rglob('*') if p.is_file()):
        rel = path.relative_to(source).as_posix()
        _safe_relative(rel)
        data = path.read_bytes()
        items.append({'path': rel, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    return items


def build_signed_package(source: Path | str, output: Path | str, from_version: str, to_version: str,
                         private_key: Ed25519PrivateKey) -> Path:
    source = Path(source)
    output = Path(output)
    files = _payload_files(source)
    total = sum(item['size'] for item in files)
    if total > MAX_EXPANDED_BYTES:
        raise ValueError('package exceeds expanded-size limit')
    manifest = {
        'format': 'USTRACKER_UPDATE_V1',
        'product': 'UStracker',
        'from_version': from_version,
        'to_version': to_version,
        'files': files,
        'total_expanded_bytes': total,
    }
    raw = _canonical(manifest)
    sig = private_key.sign(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST, raw)
        z.writestr(SIGNATURE, sig)
        for item in files:
            z.write(source / item['path'], arcname='payload/' + item['path'])
    return output


def inspect_package(package: Path | str, public_key: Ed25519PublicKey) -> dict:
    package = Path(package)
    with zipfile.ZipFile(package) as z:
        names = z.namelist()
        for name in names:
            _safe_relative(name)
        if MANIFEST not in names or SIGNATURE not in names:
            raise ValueError('update manifest/signature missing')
        raw = z.read(MANIFEST)
        public_key.verify(z.read(SIGNATURE), raw)
        manifest = json.loads(raw)
        if manifest.get('format') != 'USTRACKER_UPDATE_V1' or manifest.get('product') != 'UStracker':
            raise ValueError('unsupported update format')
        files = manifest.get('files') or []
        total = 0
        expected_names = {MANIFEST, SIGNATURE}
        seen_casefold: set[str] = set()
        for item in files:
            rel = _safe_relative(str(item['path'])).as_posix()
            folded = rel.casefold()
            if folded in seen_casefold:
                raise ValueError('case-colliding update paths')
            seen_casefold.add(folded)
            member = 'payload/' + rel
            expected_names.add(member)
            info = z.getinfo(member)
            if info.is_dir() or info.file_size != int(item['size']):
                raise ValueError(f'update size mismatch: {rel}')
            total += info.file_size
            if total > min(int(manifest.get('total_expanded_bytes', 0)), MAX_EXPANDED_BYTES):
                raise ValueError('update expanded-size limit exceeded')
            if hashlib.sha256(z.read(member)).hexdigest() != item['sha256']:
                raise ValueError(f'update hash mismatch: {rel}')
        # Extra members are rejected, including a traversal entry added after signing.
        if set(names) != expected_names:
            raise ValueError('unexpected update member')
        if total != int(manifest.get('total_expanded_bytes', -1)):
            raise ValueError('update total size mismatch')
        return manifest


def safe_extract(package: Path | str, destination: Path | str, public_key: Ed25519PublicKey) -> dict:
    manifest = inspect_package(package, public_key)
    destination = Path(destination)
    staging = destination.with_name(destination.name + '.staging')
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(package) as z:
            for item in manifest['files']:
                rel = _safe_relative(item['path'])
                target = staging.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read('payload/' + rel.as_posix()))
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest
