from __future__ import annotations
import importlib.metadata as md
import json
import sys
from pathlib import Path

names = ['fastapi','uvicorn','cryptography','Pillow','openpyxl','python-multipart','sqlcipher3']
components=[]
for name in names:
    try:
        dist=md.distribution(name)
        components.append({'name':dist.metadata['Name'],'version':dist.version,'license':dist.metadata.get('License','')})
    except md.PackageNotFoundError:
        components.append({'name':name,'version':'NOT_FOUND','license':''})
components.extend([
    {'name':'CPython Embedded','version':'3.13.15','license':'PSF-2.0'},
    {'name':'Microsoft Edge WebView2 Runtime','version':'152.0.4191.53','license':'Microsoft Software License Terms'},
    {'name':'UStracker','version':'1.00.01.000','license':'Proprietary / LICENSE.txt'},
])
out=Path(sys.argv[1]) if len(sys.argv)>1 else Path('SBOM.json')
out.write_text(json.dumps({'bomFormat':'UStracker-SBOM','specVersion':'1.0','components':components},indent=2),encoding='utf-8')
