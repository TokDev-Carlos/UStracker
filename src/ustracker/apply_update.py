from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from .update import inspect_package, safe_extract

UTC = timezone.utc
STATES = ('RECEIVED','VALIDATED','QUIESCED','BACKED_UP','STAGED','MIGRATED','SWITCHED','VERIFIED','ACCEPTED')


def _version(root: Path) -> str:
    return json.loads((root/'VERSION.json').read_text(encoding='utf-8'))['version']


def _write_journal(root: Path, journal: dict, state: str) -> None:
    if state not in STATES: raise ValueError('invalid update state')
    journal['state']=state; journal['updated_at']=datetime.now(UTC).isoformat()
    directory=root/'UserData'/'State'; directory.mkdir(parents=True,exist_ok=True)
    path=directory/'update_journal.json'; tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)


def _backend_running(root: Path) -> bool:
    state=root/'UserData'/'State'/'backend.json'
    if not state.exists(): return False
    try:
        port=int(json.loads(state.read_text(encoding='utf-8'))['port'])
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health',timeout=1) as response:
            return response.status==200
    except Exception:
        state.unlink(missing_ok=True); return False


def _verify_switched_files(root: Path, manifest: dict) -> None:
    for item in manifest['files']:
        path=root/Path(item['path'])
        if not path.exists() or not path.is_file(): raise RuntimeError(f"updated file missing: {item['path']}")
        if path.stat().st_size!=int(item['size']): raise RuntimeError(f"updated file size mismatch: {item['path']}")
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']: raise RuntimeError(f"updated file hash mismatch: {item['path']}")


def apply(root: Path, package: Path) -> dict:
    root=root.resolve(); package=package.resolve()
    journal={'from':_version(root),'to':None,'state':'RECEIVED','package':package.name,'files':[],'started_at':datetime.now(UTC).isoformat()}
    _write_journal(root,journal,'RECEIVED')
    trust=root/'Trust'/'update_public_key.pem'
    if not trust.exists(): raise RuntimeError('trusted update public key is missing')
    public=load_pem_public_key(trust.read_bytes()); manifest=inspect_package(package,public); journal['to']=manifest['to_version']
    if journal['from']!=manifest['from_version']: raise RuntimeError('update does not match installed version')
    for item in manifest['files']:
        first=Path(item['path']).parts[0].casefold()
        if first in {'userdata','trust'}: raise RuntimeError('update package cannot replace UserData or Trust')
    _write_journal(root,journal,'VALIDATED')
    if _backend_running(root): raise RuntimeError('UStracker backend is running; use Encerrar sistema before applying the update')
    _write_journal(root,journal,'QUIESCED')
    work=root/'.update-work'; stage=work/'stage'; rollback=work/'rollback'
    shutil.rmtree(work,ignore_errors=True); work.mkdir(parents=True); rollback.mkdir(parents=True)
    for item in manifest['files']:
        rel=Path(item['path']); dst=root/rel; old=rollback/rel
        if dst.exists(): old.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(dst,old)
        journal['files'].append({'path':rel.as_posix(),'had_old':old.exists()})
    _write_journal(root,journal,'BACKED_UP')
    try:
        safe_extract(package,stage,public); _write_journal(root,journal,'STAGED')
        journal['migration_mode']='AUTHENTICATED_RUNTIME_ON_NEXT_OPEN'; _write_journal(root,journal,'MIGRATED')
        for item in manifest['files']:
            rel=Path(item['path']); src=stage/rel; dst=root/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        _write_journal(root,journal,'SWITCHED')
        _verify_switched_files(root,manifest)
        if _version(root)!=manifest['to_version']: raise RuntimeError('post-switch version verification failed')
        _write_journal(root,journal,'VERIFIED'); _write_journal(root,journal,'ACCEPTED'); return journal
    except Exception:
        for entry in reversed(journal['files']):
            rel=Path(entry['path']); dst=root/rel; old=rollback/rel
            if old.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(old,dst)
            elif dst.exists(): dst.unlink()
        journal['rollback_at']=datetime.now(UTC).isoformat(); journal['rollback_reason']='update_failed_before_acceptance'; _write_journal(root,journal,'QUIESCED'); raise
    finally:
        shutil.rmtree(work,ignore_errors=True)


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('package'); parser.add_argument('--root',required=True); args=parser.parse_args()
    try: print(json.dumps(apply(Path(args.root),Path(args.package)),ensure_ascii=False,indent=2)); return 0
    except Exception as exc: print(f'UStracker update failed: {exc}',file=sys.stderr); return 1

if __name__=='__main__': raise SystemExit(main())
