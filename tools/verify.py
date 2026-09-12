from __future__ import annotations
import argparse, os, platform, subprocess, sys
from pathlib import Path

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--integration',action='store_true'); p.add_argument('--task'); p.add_argument('--native',action='store_true'); p.add_argument('--profile'); p.add_argument('--evidence-dir',default='Evidence'); p.add_argument('--explain',action='store_true'); a=p.parse_args()
    if a.explain:
        print('UStracker verification: unit/integration suite; native profile checks require matching Windows host.')
        return 0
    if a.native:
        if platform.system()!='Windows':
            print('BLOCKED: native verification requires Windows',file=sys.stderr); return 3
        if a.profile=='win10_22h2':
            release=platform.release(); version=platform.version()
            if release!='10': print(f'BLOCKED: expected Windows 10, got {release} {version}',file=sys.stderr); return 3
    root=Path(__file__).resolve().parents[1]
    env=os.environ.copy(); env['PYTHONPATH']=str(root/'src')
    if os.environ.get('USTRACKER_PRODUCTION_VERIFY')!='1': env.setdefault('USTRACKER_DEV_PLAINTEXT','1')
    cmd=[sys.executable,'-m','pytest','-q']
    print(' '.join(cmd)); return subprocess.call(cmd,cwd=root,env=env)
if __name__=='__main__': raise SystemExit(main())
