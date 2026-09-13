from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path, PurePosixPath

REQUIRED={
 'UStracker.exe','UStracker.Shell.exe','UStracker.Updater.exe','VERSION.json','current.json','LICENSE.txt',
 'Runtime/python.exe','frontend/index.html','frontend/app.js','frontend/styles.css','Trust/update_public_key.pem',
 'Redist/MicrosoftEdgeWebView2RuntimeInstallerX64.exe','Docs/MANUAL_USUARIO.md','SBOM.json'
}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--candidate',required=True); a=p.parse_args()
    path=Path(a.candidate)
    if not path.exists(): raise SystemExit(f'candidate missing: {path}')
    expected=json.loads(Path('VERSION.json').read_text(encoding='utf-8'))['version']
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
        version=json.loads(z.read('VERSION.json')); current=json.loads(z.read('current.json'))
        if version.get('version')!=expected: raise SystemExit(f'wrong candidate version: {version.get("version")} expected {expected}')
        if current.get('version')!=expected: raise SystemExit(f'current.json version mismatch: {current.get("version")} expected {expected}')
        if current.get('schema_version')!=version.get('schema_version'): raise SystemExit('current.json schema mismatch')
        if int(version.get('schema_version',0))<2: raise SystemExit('schema version too old for closure release')
        if z.getinfo('Redist/MicrosoftEdgeWebView2RuntimeInstallerX64.exe').file_size < 50_000_000:
            raise SystemExit('WebView2 offline installer is unexpectedly small')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({'status':'PASS','candidate':path.name,'version':expected,'sha256':digest},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
