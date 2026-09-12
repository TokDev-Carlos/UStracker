from __future__ import annotations

import json
from pathlib import Path
from .db import Database

DEFAULT_BRAND = {
    'product':'UStracker',
    'company_display_name':'UStracker',
    'contact_phone':'',
    'contact_email':'',
    'copyright':'Copyright CRJ',
}


def projection_path(root: Path) -> Path:
    p=Path(root)/'UserData'/'Public'/'production'/'view.json'; p.parent.mkdir(parents=True,exist_ok=True); return p


def rebuild(root:Path, db:Database) -> dict:
    settings={r['key']:r['value'] for r in db.query('SELECT key,value FROM settings')}
    brand={**DEFAULT_BRAND,**{k:v for k,v in settings.items() if k in {'company_display_name','contact_phone','contact_email'}}}
    clients=[{'public_name':r['public_name']} for r in db.query("SELECT public_name FROM clients WHERE archived=0 AND status='ACTIVE' AND public_name IS NOT NULL AND trim(public_name)<>'' ORDER BY public_name")]
    catalog=[{'code':r['code'],'name':r['name'],'category':r['category'],'kind':r['kind'],'price_cents':r['price_cents'],'billing_interval_months':r['billing_interval_months']}
             for r in db.query('SELECT code,name,category,kind,price_cents,billing_interval_months FROM catalog WHERE active=1 AND public=1 ORDER BY name')]
    data={'brand':brand,'clients':clients,'catalog':catalog,'integrations':{'drive':'PREPARED_DISABLED','tracking':'PREPARED_DISABLED','fiscal_official':'PREPARED_DISABLED'}}
    path=projection_path(root); tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path); return data


def read(root:Path) -> dict:
    path=projection_path(root)
    if not path.exists():
        data={'brand':DEFAULT_BRAND,'clients':[],'catalog':[],'integrations':{'drive':'PREPARED_DISABLED','tracking':'PREPARED_DISABLED','fiscal_official':'PREPARED_DISABLED'}}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return data
    return json.loads(path.read_text(encoding='utf-8'))
