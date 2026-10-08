from __future__ import annotations

import re

from .db import Database
from .money import parse_money_api
from .services import audit, now, uid

CATEGORY_MAP={
    'AVULSA':'AVULSA','AVULSO':'AVULSA','ITEM':'AVULSA',
    'MENSAL':'MENSAL','MENSALIDADE':'MENSAL','PLAN':'MENSAL','PLANO':'MENSAL',
}

def normalize_category(value) -> str:
    key=str(value or '').strip().upper()
    try: return CATEGORY_MAP[key]
    except KeyError: raise ValueError('category must be Avulsa or Mensal')

def _kind(category:str)->str:
    return 'PLAN' if category=='MENSAL' else 'ITEM'

def _next_code(con)->str:
    maximum=0
    for row in con.execute("SELECT code FROM catalog WHERE upper(code) GLOB 'PRD[0-9]*'").fetchall():
        m=re.fullmatch(r'PRD(\d+)',str(row['code']).upper())
        if m: maximum=max(maximum,int(m.group(1)))
    return f'PRD{maximum+1:03d}'

def _normalize_components(payload:dict, *, allow_absent:bool=False):
    if 'cost_components' not in payload:
        if allow_absent and 'cost' not in payload: return None
        raw=[{'amount':payload.get('cost','0')}]
    else:
        raw=payload.get('cost_components') or []
        if not raw: raw=[{'amount':'0'}]
    normalized=[]
    multiple=len(raw)>=2
    for pos,item in enumerate(raw):
        description=str(item.get('description') or '').strip() or None
        if multiple and not description:
            raise ValueError('description is required when there are multiple cost components')
        amount=parse_money_api(item.get('amount', item.get('amount_cents',0))) if 'amount_cents' not in item else int(item['amount_cents'])
        if amount < 0: raise ValueError('cost component cannot be negative')
        normalized.append({'description':description,'amount_cents':amount,'position':pos})
    return normalized

def _write_components(con,catalog_id:str,components:list[dict],ts:str):
    con.execute('DELETE FROM catalog_cost_components WHERE catalog_id=?',(catalog_id,))
    for comp in components:
        con.execute(
            'INSERT INTO catalog_cost_components(id,catalog_id,description,amount_cents,position,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (uid(),catalog_id,comp['description'],comp['amount_cents'],comp['position'],ts,ts)
        )

def _history(con,catalog_id:str,price:int,cost:int,ts:str):
    # Timestamp keys preserve multiple price/cost changes on the same calendar day.
    effective=ts
    con.execute('INSERT INTO catalog_prices(id,catalog_id,effective_from,price_cents,cost_cents,created_at) VALUES(?,?,?,?,?,?)',
                (uid(),catalog_id,effective,price,cost,ts))

def _hydrate(con,row)->dict:
    out=dict(row)
    out['description']=out.get('description') or out.get('name')
    out['cost_components']=[dict(r) for r in con.execute(
        'SELECT id,description,amount_cents,position FROM catalog_cost_components WHERE catalog_id=? ORDER BY position,id',(row['id'],)
    ).fetchall()]
    return out

def create_catalog_item(db:Database,actor:int,p:dict)->dict:
    description=str(p.get('description') or p.get('name') or '').strip()
    if not description: raise ValueError('description required')
    category=normalize_category(p.get('category'))
    components=_normalize_components(p)
    price=parse_money_api(p.get('price','0'))
    cost=sum(c['amount_cents'] for c in components)
    ts=now(); cid=uid()
    with db.transaction() as con:
        code=_next_code(con)
        rec={
            'id':cid,'code':code,'name':description,'description':description,'category':category,'kind':_kind(category),
            'billing_interval_months':12 if int(p.get('billing_interval_months',1))>=12 else 1,
            'price_cents':price,'cost_cents':cost,'notes':p.get('notes'),
            'public':1 if p.get('public') else 0,'active':1 if p.get('active',True) else 0,
            'revision':1,'created_at':ts,'updated_at':ts,
        }
        con.execute('''INSERT INTO catalog(id,code,name,description,category,kind,billing_interval_months,price_cents,cost_cents,notes,public,active,revision,created_at,updated_at)
                       VALUES(:id,:code,:name,:description,:category,:kind,:billing_interval_months,:price_cents,:cost_cents,:notes,:public,:active,:revision,:created_at,:updated_at)''',rec)
        _write_components(con,cid,components,ts); _history(con,cid,price,cost,ts)
        audit(con,actor,'CATALOG_CREATE','catalog',cid,None,rec)
        return _hydrate(con,con.execute('SELECT * FROM catalog WHERE id=?',(cid,)).fetchone())

def update_catalog_item(db:Database,actor:int,catalog_id:str,p:dict)->dict:
    with db.transaction() as con:
        row=con.execute('SELECT * FROM catalog WHERE id=?',(catalog_id,)).fetchone()
        if not row: raise KeyError('catalog item not found')
        expected=int(p.get('expected_revision',0))
        if expected<=0 or int(row['revision'])!=expected: raise ValueError(f"revision conflict: current={row['revision']}")
        before=dict(row); ts=now()
        description=str(p.get('description',p.get('name',row['description'] or row['name'])) or '').strip()
        if not description: raise ValueError('description required')
        category=normalize_category(p.get('category',row['category']))
        price=int(row['price_cents']) if 'price' not in p else parse_money_api(p['price'])
        components=_normalize_components(p,allow_absent=True)
        if components is None:
            existing=[dict(r) for r in con.execute('SELECT description,amount_cents,position FROM catalog_cost_components WHERE catalog_id=? ORDER BY position,id',(catalog_id,)).fetchall()]
            components=existing or [{'description':None,'amount_cents':int(row['cost_cents']),'position':0}]
        cost=sum(int(c['amount_cents']) for c in components)
        values={'id':catalog_id,'name':description,'description':description,'category':category,'kind':_kind(category),
                'billing_interval_months':int(p.get('billing_interval_months',row['billing_interval_months'])),
                'price_cents':price,'cost_cents':cost,'notes':p.get('notes',row['notes']),
                'public':1 if p.get('public',bool(row['public'])) else 0,'active':1 if p.get('active',bool(row['active'])) else 0,'updated_at':ts}
        con.execute('''UPDATE catalog SET name=:name,description=:description,category=:category,kind=:kind,billing_interval_months=:billing_interval_months,
                       price_cents=:price_cents,cost_cents=:cost_cents,notes=:notes,public=:public,active=:active,
                       revision=revision+1,updated_at=:updated_at WHERE id=:id''',values)
        _write_components(con,catalog_id,components,ts)
        if price!=int(row['price_cents']) or cost!=int(row['cost_cents']): _history(con,catalog_id,price,cost,ts)
        after=con.execute('SELECT * FROM catalog WHERE id=?',(catalog_id,)).fetchone(); audit(con,actor,'CATALOG_UPDATE','catalog',catalog_id,before,dict(after))
        return _hydrate(con,after)

def get_catalog_item(db:Database,catalog_id:str)->dict:
    with db.transaction() as con:
        row=con.execute('SELECT * FROM catalog WHERE id=?',(catalog_id,)).fetchone()
        if not row: raise KeyError('catalog item not found')
        return _hydrate(con,row)

def _usage(con,catalog_id:str)->int:
    n=0
    for sql in ('SELECT COUNT(*) FROM subscription_items WHERE catalog_id=?','SELECT COUNT(*) FROM direct_sale_items WHERE catalog_id=?',
                'SELECT COUNT(*) FROM expenses WHERE catalog_id=?'):
        n+=int(con.execute(sql,(catalog_id,)).fetchone()[0] or 0)
    return n

def remove_catalog_item(db:Database,actor:int,catalog_id:str)->dict:
    """AJ-11: delete a product never used; a product already used is archived (history preserved)."""
    with db.transaction() as con:
        row=con.execute('SELECT * FROM catalog WHERE id=?',(catalog_id,)).fetchone()
        if not row: raise KeyError('catalog item not found')
        if _usage(con,catalog_id):
            con.execute('UPDATE catalog SET active=0,revision=revision+1,updated_at=? WHERE id=?',(now(),catalog_id))
            audit(con,actor,'CATALOG_ARCHIVE','catalog',catalog_id,dict(row),{'active':0})
            return {'id':catalog_id,'deleted':False,'archived':True}
        from .trash import put as trash_put
        trash_put(con,actor,'catalog',catalog_id,f"{row['code']} · {row['name']}",{
            'row':dict(row),
            'components':[dict(r) for r in con.execute('SELECT * FROM catalog_cost_components WHERE catalog_id=?',(catalog_id,)).fetchall()],
            'prices':[dict(r) for r in con.execute('SELECT * FROM catalog_prices WHERE catalog_id=?',(catalog_id,)).fetchall()]})
        con.execute('DELETE FROM catalog_cost_components WHERE catalog_id=?',(catalog_id,))
        con.execute('DELETE FROM catalog_prices WHERE catalog_id=?',(catalog_id,))
        con.execute('DELETE FROM catalog WHERE id=?',(catalog_id,))
        audit(con,actor,'CATALOG_DELETE','catalog',catalog_id,dict(row),None)
        return {'id':catalog_id,'deleted':True,'archived':False}

def list_catalog(db:Database)->list[dict]:
    with db.transaction() as con:
        out=[]
        for row in con.execute('SELECT * FROM catalog ORDER BY active DESC,code,id').fetchall():
            rec=_hydrate(con,row); rec['usage_count']=_usage(con,row['id']); out.append(rec)
        return out
