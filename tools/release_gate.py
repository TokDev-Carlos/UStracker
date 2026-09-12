from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path, PurePosixPath

REQUIRED={
 'UStracker.exe','UStracker.Shell.exe','UStracker.Updater.exe','VERSION.json','LICENSE.txt',
 'Runtime/python.exe','frontend/index.html','frontend/app.js','frontend/styles.css','Trust/update_public_key.pem'
}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--candidate',required=True); a=p.parse_args()
    path=Path(a.candidate)
    if not path.exists(): raise SystemExit(f'candidate missing: {path}')
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        for name in names:
            pp=PurePosixPath(name.replace('\\','/'))
            if pp.is_absolute() or '..' in pp.parts: raise SystemExit(f'unsafe member: {name}')
            lower=name.lower()
            if 'private' in lower and lower.endswith('.pem'): raise SystemExit('private key leaked into release')
            if lower.startswith('userdata/') and lower.endswith(('.db','.sqlite','.json')): raise SystemExit(f'user data leaked: {name}')
        missing=sorted(x for x in REQUIRED if x not in names)
        if missing: raise SystemExit('missing required release files: '+', '.join(missing))
        version=json.loads(z.read('VERSION.json'))
        if version.get('version')!='1.00.00.000': raise SystemExit('wrong candidate version')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({'status':'PASS','candidate':path.name,'sha256':digest},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
