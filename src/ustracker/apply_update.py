from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_public_key

from .update import inspect_package, safe_extract


def _version(root: Path) -> str:
    return json.loads((root / 'VERSION.json').read_text(encoding='utf-8'))['version']


def apply(root: Path, package: Path) -> dict:
    trust = root / 'Trust' / 'update_public_key.pem'
    if not trust.exists():
        raise RuntimeError('trusted update public key is missing')
    public = load_pem_public_key(trust.read_bytes())
    manifest = inspect_package(package, public)
    if _version(root) != manifest['from_version']:
        raise RuntimeError('update does not match installed version')
    for item in manifest['files']:
        first = Path(item['path']).parts[0].casefold()
        if first in {'userdata', 'trust'}:
            raise RuntimeError('update package cannot replace UserData or Trust')

    work = root / '.update-work'
    stage = work / 'stage'
    rollback = work / 'rollback'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    safe_extract(package, stage, public)
    journal = {'from': manifest['from_version'], 'to': manifest['to_version'], 'state': 'STAGED', 'files': []}
    try:
        rollback.mkdir(parents=True)
        for item in manifest['files']:
            rel = Path(item['path'])
            src = stage / rel
            dst = root / rel
            old = rollback / rel
            if dst.exists():
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, old)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            journal['files'].append({'path': rel.as_posix(), 'had_old': old.exists()})
        journal['state'] = 'ACCEPTED'
        (root / 'UserData' / 'State').mkdir(parents=True, exist_ok=True)
        (root / 'UserData' / 'State' / 'last_update.json').write_text(json.dumps(journal, indent=2), encoding='utf-8')
        return journal
    except Exception:
        for entry in reversed(journal['files']):
            rel = Path(entry['path'])
            dst = root / rel
            old = rollback / rel
            if old.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, dst)
            elif dst.exists():
                dst.unlink()
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('package')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    try:
        result = apply(Path(args.root).resolve(), Path(args.package).resolve())
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f'UStracker update failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
