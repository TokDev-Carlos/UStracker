from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

from .db import Database, fold_text
from .money import due_date, parse_money_api
from .vehicle_types import annotate_vehicle, vehicle_breakdown
from .projections import client_projection, general_expenses, month_forecast, realized_revenue
from .clients import companies_from_payload, documents_from_payload, has_contact, infer_document_type, normalize_document_number, validate_document

UTC=timezone.utc

def now() -> str:
    return datetime.now(UTC).isoformat()

def uid() -> str:
    return str(uuid.uuid4())

def rowdict(row) -> dict:
    return dict(row) if row is not None else {}

def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        blocked={'password','token','cookie','vrk','db_key','media_key','document','address','phone','email'}
        return {k: ('[REDACTED]' if k.lower() in blocked else _sanitize(v)) for k,v in value.items()}
    if isinstance(value, list): return [_sanitize(x) for x in value]
    return value

def audit(con, actor_slot:int, action:str, entity_type:str|None, entity_id:str|None, before:Any=None, after:Any=None):
    previous=con.execute('SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone()
    prev=previous[0] if previous else ''
    payload=json.dumps({'at':now(),'actor_slot':actor_slot,'action':action,'entity_type':entity_type,'entity_id':entity_id,
                        'before':_sanitize(before),'after':_sanitize(after),'previous_hash':prev},sort_keys=True,ensure_ascii=False,separators=(',',':'))
    digest=hashlib.sha256(payload.encode()).hexdigest()
    data=json.loads(payload)
    con.execute('INSERT INTO audit_events(at,actor_slot,action,entity_type,entity_id,before_json,after_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?,?,?)',
                (data['at'],actor_slot,action,entity_type,entity_id,json.dumps(data['before'],ensure_ascii=False),json.dumps(data['after'],ensure_ascii=False),prev,digest))

def list_table(db:Database, table:str, where='1=1', args=(), order='created_at DESC', limit=100):
    allowed={'clients','fleets','vehicles','catalog','subscriptions','charges','payments','credits','expenses','fiscal_obligations','stations'}
    if table not in allowed: raise ValueError('invalid table')
    rows=db.query(f'SELECT * FROM {table} WHERE {where} ORDER BY {order} LIMIT ?', (*args,limit))
    return [dict(r) for r in rows]

def _insert_client_document(con, client_id:str, payload:dict, ts:str) -> dict:
    doc=validate_document(payload)
    existing=con.execute(
        'SELECT id FROM client_documents WHERE type=? AND normalized_number=? AND archived=0',
        (doc['type'],doc['normalized_number'])
    ).fetchone()
    if existing:
        raise ValueError('document already registered')
    for legacy in con.execute("SELECT id,document FROM clients WHERE document IS NOT NULL AND trim(document)<>'' AND id<>?", (client_id,)).fetchall():
        legacy_number=normalize_document_number(legacy['document'])
        if legacy_number == doc['normalized_number'] and infer_document_type(legacy['document']) == doc['type']:
            raise ValueError('document already registered')
    if doc['is_primary']:
        con.execute('UPDATE client_documents SET is_primary=0,updated_at=? WHERE client_id=? AND archived=0',(ts,client_id))
    did=uid()
    rec={'id':did,'client_id':client_id,**doc,'archived':0,'created_at':ts,'updated_at':ts}
    con.execute(
        'INSERT INTO client_documents(id,client_id,type,number,normalized_number,is_primary,archived,created_at,updated_at) '
        'VALUES(:id,:client_id,:type,:number,:normalized_number,:is_primary,:archived,:created_at,:updated_at)',rec)
    return rec


def _replace_client_document(con, client_id:str, payload:dict, ts:str) -> tuple[dict, list[dict]]:
    doc=validate_document({**payload,'is_primary':True})
    duplicate=con.execute(
        'SELECT id FROM client_documents WHERE type=? AND normalized_number=? AND archived=0 AND client_id<>?',
        (doc['type'],doc['normalized_number'],client_id)
    ).fetchone()
    if duplicate: raise ValueError('document already registered')
    previous=[dict(row) for row in con.execute(
        'SELECT * FROM client_documents WHERE client_id=? AND archived=0 ORDER BY is_primary DESC,created_at,id',
        (client_id,)
    ).fetchall()]
    if len(previous)==1 and previous[0]['type']==doc['type'] and previous[0]['normalized_number']==doc['normalized_number']:
        return previous[0],previous
    if previous:
        con.execute('UPDATE client_documents SET archived=1,is_primary=0,updated_at=? WHERE client_id=? AND archived=0',(ts,client_id))
    rec=_insert_client_document(con,client_id,doc,ts)
    return rec,previous


def _insert_client_company(con, client_id:str, payload:dict, ts:str) -> dict:
    legal_name=str(payload.get('legal_name') or '').strip()
    if not legal_name: raise ValueError('company legal_name required')
    company={
        'legal_name':legal_name,
        'trade_name':str(payload.get('trade_name') or '').strip() or None,
        'document':str(payload.get('document') or '').strip() or None,
        'normalized_document':normalize_document_number(payload.get('document')) or None,
        'is_primary':1 if payload.get('is_primary') else 0,
    }
    if company['is_primary']:
        con.execute('UPDATE client_companies SET is_primary=0,updated_at=? WHERE client_id=? AND archived=0',(ts,client_id))
    company_id=uid()
    rec={'id':company_id,'client_id':client_id,**company,'archived':0,'created_at':ts,'updated_at':ts}
    con.execute(
        'INSERT INTO client_companies(id,client_id,legal_name,trade_name,document,normalized_document,is_primary,archived,created_at,updated_at) '
        'VALUES(:id,:client_id,:legal_name,:trade_name,:document,:normalized_document,:is_primary,:archived,:created_at,:updated_at)',rec)
    return rec


def list_client_documents(db:Database, client_id:str)->list[dict]:
    return [dict(r) for r in db.query(
        'SELECT * FROM client_documents WHERE client_id=? AND archived=0 ORDER BY is_primary DESC,created_at,id',
        (client_id,)
    )]


def list_client_companies(db:Database, client_id:str)->list[dict]:
    return [dict(r) for r in db.query(
        'SELECT * FROM client_companies WHERE client_id=? AND archived=0 ORDER BY is_primary DESC,created_at,id',
        (client_id,)
    )]


def create_client_document(db:Database, actor:int, client_id:str, p:dict)->dict:
    ts=now()
    with db.transaction() as con:
        client=con.execute('SELECT * FROM clients WHERE id=? AND archived=0',(client_id,)).fetchone()
        if not client: raise KeyError('client not found')
        rec,previous=_replace_client_document(con,client_id,p,ts)
        con.execute('UPDATE clients SET document=?,revision=revision+1,updated_at=? WHERE id=?',(rec['number'],ts,client_id))
        audit(con,actor,'CLIENT_DOCUMENT_REPLACE','client_document',rec['id'],previous,rec)
        return rec


def create_client_company(db:Database, actor:int, client_id:str, p:dict)->dict:
    ts=now()
    with db.transaction() as con:
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0',(client_id,)).fetchone():
            raise KeyError('client not found')
        rec=_insert_client_company(con,client_id,p,ts)
        con.execute('UPDATE clients SET revision=revision+1,updated_at=? WHERE id=?',(ts,client_id))
        audit(con,actor,'CLIENT_COMPANY_CREATE','client_company',rec['id'],None,rec)
        return rec


def create_client(db:Database, actor:int, p:dict)->dict:
    legal_name=str(p.get('legal_name') or '').strip()
    if not legal_name: raise ValueError('legal_name required')
    documents=documents_from_payload(p)
    if not documents: raise ValueError('at least one document required')
    if len(documents) != 1: raise ValueError('exactly one active document is allowed')
    if not has_contact(p): raise ValueError('at least one contact required')
    companies=companies_from_payload(p)
    if documents[0]['type']=='CNPJ' and not companies:
        # H-07: client with CNPJ is a company — it becomes its own primary company.
        companies=[{'legal_name':legal_name,'trade_name':str(p.get('trade_name') or '').strip() or None,
                    'document':documents[0]['number'],'is_primary':1}]
    status=p.get('status','ACTIVE')
    if status not in {'ACTIVE','INACTIVE','CANCELLED'}: raise ValueError('invalid status')
    cid=uid(); ts=now()
    primary_doc=next((doc for doc in documents if doc['is_primary']),documents[0])
    rec={'id':cid,'legal_name':legal_name,'trade_name':p.get('trade_name'),'public_name':p.get('public_name'),
         'document':str(p.get('document') or primary_doc['number']).strip(),'email':str(p.get('email') or '').strip() or None,
         'phone':str(p.get('phone') or '').strip() or None,'address':p.get('address'),'notes':p.get('notes'),
         'status':status,'archived':0,'revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute(
            'INSERT INTO clients(id,legal_name,trade_name,public_name,document,email,phone,address,notes,status,archived,revision,created_at,updated_at) '
            'VALUES(:id,:legal_name,:trade_name,:public_name,:document,:email,:phone,:address,:notes,:status,:archived,:revision,:created_at,:updated_at)',rec)
        child_docs=[_insert_client_document(con,cid,doc,ts) for doc in documents]
        child_companies=[_insert_client_company(con,cid,company,ts) for company in companies]
        audit(con,actor,'CLIENT_CREATE','client',cid,None,{**rec,'documents':child_docs,'companies':child_companies})
    return rec


def update_client(db:Database, actor:int, cid:str, p:dict)->dict:
    with db.transaction() as con:
        old=con.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
        if not old: raise KeyError('client not found')
        before=dict(old)
        if p.get('expected_revision') is not None and int(p['expected_revision']) != int(old['revision']):
            raise ValueError(f"revision conflict: current={old['revision']}")
        if 'legal_name' in p and not str(p.get('legal_name') or '').strip():
            raise ValueError('legal_name required')
        if ('email' in p or 'phone' in p) and not has_contact(p,existing_email=old['email'],existing_phone=old['phone']):
            raise ValueError('at least one contact required')
        if 'status' in p and p['status'] not in {'ACTIVE','INACTIVE','CANCELLED'}:
            raise ValueError('invalid status')
        allowed={'legal_name','trade_name','public_name','email','phone','address','notes','status'}
        fields=[]; values=[]
        for k,v in p.items():
            if k in allowed:
                if k in {'legal_name','email','phone'} and isinstance(v,str):
                    v=v.strip() or None
                fields.append(f'{k}=?'); values.append(v)
        ts=now()
        if 'document' in p:
            number=str(p.get('document') or '').strip()
            if not number: raise ValueError('at least one document required')
            rec,_previous=_replace_client_document(con,cid,{
                'type':p.get('document_type') or infer_document_type(number),
                'number':number,
                'is_primary':True,
            },ts)
            fields.append('document=?'); values.append(rec['number'])
        if not fields: return before
        fields+=['revision=revision+1','updated_at=?']; values.append(ts); values.append(cid)
        con.execute(f"UPDATE clients SET {','.join(fields)} WHERE id=?",values)
        after=dict(con.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone())
        audit(con,actor,'CLIENT_UPDATE','client',cid,before,after)
        return after


def list_clients(db:Database, *, include_archived:bool=False, limit:int=20000)->list[dict]:
    where='' if include_archived else 'WHERE c.archived=0'
    rows=db.query(f'''SELECT c.*,
        COALESCE((SELECT cc.legal_name FROM client_companies cc WHERE cc.client_id=c.id AND cc.archived=0
                  ORDER BY cc.is_primary DESC,cc.created_at,cc.id LIMIT 1),c.trade_name,'') AS primary_company,
        CASE WHEN COALESCE(trim(c.email),'')<>'' THEN c.email ELSE COALESCE(c.phone,'') END AS primary_contact,
        (SELECT COUNT(*) FROM vehicles v WHERE v.client_id=c.id AND v.archived=0) AS vehicles_count,
        (SELECT COALESCE(SUM(p.amount_cents),0) FROM payments p WHERE p.client_id=c.id AND p.reversed_at IS NULL)
        +(SELECT COALESCE(SUM(ds.total_cents),0) FROM direct_sales ds WHERE ds.client_id=c.id AND ds.status='PAID') AS generated_value_cents
        FROM clients c {where} ORDER BY c.archived,c.legal_name LIMIT ?''',(limit,))
    items=[dict(row) for row in rows]
    projection=client_projection(db,[row['id'] for row in items])
    for row in items:
        p=projection[row['id']]
        row['contracted_active_cents']=p['contracted_active_cents']
        row['realized_revenue_cents']=p['realized_revenue_cents']
        row['generated_value_cents']=p['realized_revenue_cents']
    return items


def search_client_entities(db:Database, query:str, *, limit:int=20)->list[dict]:
    needle=fold_text(query).strip()
    if not needle: return []
    bounded=max(1,min(int(limit),30))
    like=f'%{needle}%'
    normalized_document=normalize_document_number(query)
    document_like=f'%{fold_text(normalized_document)}%'
    rows=db.query('''SELECT c.id,c.code,c.legal_name AS display_name,c.phone,c.email,c.status,
        COALESCE((SELECT cd.number FROM client_documents cd WHERE cd.client_id=c.id AND cd.archived=0
                  ORDER BY cd.is_primary DESC,cd.created_at,cd.id LIMIT 1),c.document,'') AS primary_document,
        COALESCE((SELECT cc.legal_name FROM client_companies cc WHERE cc.client_id=c.id AND cc.archived=0
                  ORDER BY cc.is_primary DESC,cc.created_at,cc.id LIMIT 1),c.trade_name,'') AS primary_company
        FROM clients c WHERE c.archived=0 AND (
          fold_text(c.code) LIKE ?
          OR EXISTS(SELECT 1 FROM logical_codes lc WHERE lc.client_id=c.id AND fold_text(lc.code) LIKE ?)
          OR fold_text(c.legal_name) LIKE ? OR fold_text(c.trade_name) LIKE ? OR fold_text(c.public_name) LIKE ?
          OR fold_text(c.phone) LIKE ? OR fold_text(c.email) LIKE ?
          OR EXISTS(SELECT 1 FROM client_documents cd WHERE cd.client_id=c.id AND cd.archived=0
                    AND (fold_text(cd.number) LIKE ? OR fold_text(cd.normalized_number) LIKE ?))
          OR EXISTS(SELECT 1 FROM client_companies cc WHERE cc.client_id=c.id AND cc.archived=0
                    AND (fold_text(cc.legal_name) LIKE ? OR fold_text(cc.trade_name) LIKE ? OR fold_text(cc.document) LIKE ?))
        ) ORDER BY fold_text(c.legal_name),c.id LIMIT ?''',
        (like,like,like,like,like,like,like,like,document_like,like,like,like,bounded))
    return [dict(row) for row in rows]


def _archive_block_reasons(con, client_id:str)->list[str]:
    reasons=[]
    if con.execute("SELECT 1 FROM direct_sales WHERE client_id=? AND status='OPEN' LIMIT 1",(client_id,)).fetchone():
        reasons.append('open direct sale')
    if con.execute("SELECT 1 FROM charges WHERE client_id=? AND status IN ('OPEN','PARTIAL') LIMIT 1",(client_id,)).fetchone():
        reasons.append('open charge')
    if con.execute("SELECT 1 FROM subscriptions WHERE client_id=? AND lifecycle_status IN ('ACTIVE','PAUSED') LIMIT 1",(client_id,)).fetchone():
        reasons.append('active subscription')
    return reasons


def archive_clients(db:Database, actor:int, client_ids:list[str])->dict:
    ordered=list(dict.fromkeys(str(cid) for cid in (client_ids or []) if cid))
    if not ordered: raise ValueError('client_ids required')
    archived=[]; blocked=[]; ts=now()
    with db.transaction() as con:
        for cid in ordered:
            row=con.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
            if not row or row['archived']:
                blocked.append({'id':cid,'reasons':['client not found or already archived']})
                continue
            reasons=_archive_block_reasons(con,cid)
            if reasons:
                blocked.append({'id':cid,'reasons':reasons})
                continue
            before=dict(row)
            con.execute("UPDATE clients SET archived=1,status='INACTIVE',revision=revision+1,updated_at=? WHERE id=?",(ts,cid))
            from .trash import put as trash_put
            from .mobility_delete import cascade_client_archive
            taken=cascade_client_archive(con,cid,ts)
            trash_put(con,actor,'client',cid,f"{row['code'] or ''} {row['legal_name']}".strip(),{'id':cid,**taken})
            after=dict(con.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone())
            audit(con,actor,'CLIENT_ARCHIVE','client',cid,before,after)
            archived.append(cid)
    return {'archived_ids':archived,'blocked':blocked}

def create_vehicle(db:Database, actor:int, p:dict)->dict:
    # Compatibility seam: R03 centralizes all vehicle invariants in mobility.py.
    from .mobility import create_vehicle as create_mobility_vehicle
    return create_mobility_vehicle(db,actor,p)

def create_catalog(db:Database, actor:int, p:dict)->dict:
    # Compatibility seam: R04 owns catalog invariants and automatic codes.
    from .catalog import create_catalog_item
    return create_catalog_item(db,actor,p)

def _hydrate_subscription(con, row)->dict:
    rec=dict(row)
    client=con.execute('''SELECT c.legal_name,c.code,
        (SELECT cc.legal_name FROM client_companies cc
         WHERE cc.client_id=c.id AND cc.archived=0
         ORDER BY cc.is_primary DESC,cc.created_at,cc.id LIMIT 1) AS company_name
        FROM clients c WHERE c.id=?''',(rec['client_id'],)).fetchone()
    rec['client_name']=client['legal_name'] if client else None
    rec['client_code']=client['code'] if client else None
    rec['company_name']=client['company_name'] if client else None
    items=[]
    for item in con.execute('''SELECT si.*,c.code AS plan_code,c.name AS plan_name,c.category AS plan_category
                               FROM subscription_items si
                               LEFT JOIN catalog c ON c.id=si.catalog_id
                               WHERE si.subscription_id=? ORDER BY si.rowid''',(rec['id'],)).fetchall():
        items.append(dict(item))
    targets=[]
    for target in con.execute('''SELECT st.*,
        CASE WHEN st.vehicle_id IS NOT NULL THEN 'VEHICLE' ELSE 'FLEET' END AS target_type,
        v.code AS vehicle_code,v.type AS vehicle_type,f.code AS fleet_code,
        v.plate AS vehicle_plate,v.brand AS vehicle_brand,v.model AS vehicle_model,v.fleet_id AS vehicle_fleet_id,
        f.name AS fleet_name,cc.legal_name AS fleet_company_name
        FROM subscription_targets st
        LEFT JOIN vehicles v ON v.id=st.vehicle_id
        LEFT JOIN fleets f ON f.id=st.fleet_id
        LEFT JOIN client_companies cc ON cc.id=f.client_company_id
        WHERE st.subscription_id=? ORDER BY st.created_at,st.rowid''',(rec['id'],)).fetchall():
        item=dict(target)
        item['target_name']=item['vehicle_plate'] if item['target_type']=='VEHICLE' else item['fleet_name']
        if item['target_type']=='VEHICLE': annotate_vehicle(item,'vehicle_type','vehicle_')
        targets.append(item)
    rec['items']=items
    rec['subscription_items']=items
    rec['targets']=targets
    rec['effective_total_cents']=sum(int(item['quantity'])*int(item['unit_price_cents']) for item in items)
    return rec

def get_subscription(db:Database, subscription_id:str)->dict:
    with db.transaction() as con:
        row=con.execute('SELECT * FROM subscriptions WHERE id=?',(subscription_id,)).fetchone()
        if not row: raise KeyError('subscription not found')
        return _hydrate_subscription(con,row)

def list_subscriptions(db:Database, *, client_id:str|None=None, limit:int=500)->list[dict]:
    where=' WHERE client_id=?' if client_id else ''
    args=(client_id,) if client_id else ()
    with db.transaction() as con:
        rows=con.execute(f'SELECT * FROM subscriptions{where} ORDER BY created_at DESC,id LIMIT ?',(*args,int(limit))).fetchall()
        return [_hydrate_subscription(con,row) for row in rows]

def create_subscription(db:Database, actor:int, p:dict)->dict:
    sid=uid(); ts=now(); items=p.get('items') or []
    client_id=str(p.get('client_id') or '').strip()
    start_on=str(p.get('start_on') or '').strip()
    if not client_id or not start_on or not items: raise ValueError('client_id, start_on and items required')
    try:
        signed_on=date.fromisoformat(str(p.get('signed_on') or date.today().isoformat()))
        start_date=date.fromisoformat(start_on)
        end_on=str(p.get('end_on') or '').strip() or None
        end_date=date.fromisoformat(end_on) if end_on else None
    except (TypeError,ValueError) as exc:
        raise ValueError('invalid subscription date') from exc
    if end_date and end_date<start_date: raise ValueError('end_on cannot precede start_on')
    try: due_day=int(p.get('due_day',10))
    except (TypeError,ValueError) as exc: raise ValueError('due_day must be between 1 and 31') from exc
    if due_day<1 or due_day>31: raise ValueError('due_day must be between 1 and 31')
    cycle=p.get('billing_cycle') or ('ANNUAL' if int(p.get('billing_interval_months',1))>=12 else 'MONTHLY')
    if cycle not in {'DAILY','MONTHLY','ANNUAL'}: raise ValueError('invalid billing_cycle')
    interval={'DAILY':0,'MONTHLY':1,'ANNUAL':12}[cycle]
    lifecycle_status=p.get('lifecycle_status','ACTIVE')
    if lifecycle_status not in {'ACTIVE','PAUSED','CANCELLED','ENDED'}: raise ValueError('invalid lifecycle_status')
    raw_vehicle_ids=list(p.get('target_vehicle_ids') or [])
    raw_fleet_ids=list(p.get('target_fleet_ids') or [])
    for item in items:
        if item.get('vehicle_id'): raw_vehicle_ids.append(item['vehicle_id'])
    vehicle_ids=[str(value or '').strip() for value in raw_vehicle_ids]
    fleet_ids=[str(value or '').strip() for value in raw_fleet_ids]
    if any(not value for value in vehicle_ids+fleet_ids): raise ValueError('target id required')
    if len(vehicle_ids)!=len(set(vehicle_ids)): raise ValueError('duplicate vehicle target')
    if len(fleet_ids)!=len(set(fleet_ids)): raise ValueError('duplicate fleet target')
    rec={'id':sid,'client_id':client_id,'signed_on':signed_on.isoformat(),'start_on':start_date.isoformat(),'end_on':end_on,
         'due_day':due_day,'billing_interval_months':interval,'billing_cycle':cycle,'renewal_mode':p.get('renewal_mode','MANUAL'),
         'lifecycle_status':lifecycle_status,'revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        client=con.execute('SELECT id FROM clients WHERE id=? AND archived=0 AND status=?',(client_id,'ACTIVE')).fetchone()
        if not client: raise ValueError('client is not eligible for subscription')
        normalized_items=[]
        for item in items:
            catalog_id=str(item.get('catalog_id') or '').strip()
            catalog=con.execute("SELECT * FROM catalog WHERE id=? AND active=1 AND upper(category)='MENSAL'",(catalog_id,)).fetchone()
            if not catalog: raise ValueError('active monthly plan not found')
            try: quantity=int(item.get('quantity',1))
            except (TypeError,ValueError) as exc: raise ValueError('quantity must be positive') from exc
            if quantity<=0: raise ValueError('quantity must be positive')
            unit=parse_money_api(item['unit_price']) if 'unit_price' in item else int(catalog['price_cents'])
            if unit<0: raise ValueError('unit price cannot be negative')
            normalized_items.append({
                'id':uid(),'subscription_id':sid,'catalog_id':catalog_id,
                'vehicle_id':str(item.get('vehicle_id') or '').strip() or None,
                'description':str(item.get('description') or catalog['name']).strip(),
                'quantity':quantity,'unit_price_cents':unit,
            })
        for vehicle_id in vehicle_ids:
            vehicle=con.execute('SELECT client_id FROM vehicles WHERE id=? AND archived=0',(vehicle_id,)).fetchone()
            if not vehicle or vehicle['client_id']!=client_id: raise ValueError('vehicle does not belong to client')
        for fleet_id in fleet_ids:
            fleet=con.execute('''SELECT f.client_id,cc.client_id AS company_client_id
                                 FROM fleets f LEFT JOIN client_companies cc
                                 ON cc.id=f.client_company_id AND cc.archived=0
                                 WHERE f.id=? AND f.archived=0''',(fleet_id,)).fetchone()
            if not fleet or fleet['client_id']!=client_id: raise ValueError('fleet does not belong to client')
            if fleet['company_client_id']!=client_id: raise ValueError('fleet company does not belong to client')
        con.execute('''INSERT INTO subscriptions(id,client_id,signed_on,start_on,end_on,due_day,billing_interval_months,billing_cycle,renewal_mode,lifecycle_status,revision,created_at,updated_at)
                     VALUES(:id,:client_id,:signed_on,:start_on,:end_on,:due_day,:billing_interval_months,:billing_cycle,:renewal_mode,:lifecycle_status,:revision,:created_at,:updated_at)''',rec)
        for item in normalized_items:
            con.execute('INSERT INTO subscription_items(id,subscription_id,catalog_id,vehicle_id,description,quantity,unit_price_cents) VALUES(?,?,?,?,?,?,?)',
                        (item['id'],sid,item['catalog_id'],item['vehicle_id'],item['description'],item['quantity'],item['unit_price_cents']))
        for vehicle_id in vehicle_ids:
            con.execute('INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                        (uid(),sid,vehicle_id,None,ts))
        for fleet_id in fleet_ids:
            con.execute('INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                        (uid(),sid,None,fleet_id,ts))
        hydrated=_hydrate_subscription(con,con.execute('SELECT * FROM subscriptions WHERE id=?',(sid,)).fetchone())
        audit(con,actor,'SUBSCRIPTION_CREATE','subscription',sid,None,hydrated)
        # 2.7.0 (H-20): frota só agrupa — uma assinatura por veículo
        from .fleet_split import split_subscription
        extra=split_subscription(con,sid,actor,ts)
        hydrated=_hydrate_subscription(con,con.execute('SELECT * FROM subscriptions WHERE id=?',(sid,)).fetchone())
        hydrated['group_ids']=[sid,*extra]
        return hydrated

def create_direct_sale(db:Database, actor:int, p:dict)->dict:
    client_id=p.get('client_id')
    sold_on=p.get('sold_on') or date.today().isoformat()
    items=p.get('items') or []
    status=p.get('status','OPEN')
    if not client_id or not items: raise ValueError('client_id and items required')
    if status not in {'OPEN','PAID'}: raise ValueError('invalid initial sale status')
    date.fromisoformat(sold_on)
    paid_on=(p.get('paid_on') or sold_on) if status=='PAID' else None
    if paid_on: date.fromisoformat(paid_on)
    sale_id=uid(); ts=now(); normalized=[]
    with db.transaction() as con:
        if not con.execute('SELECT id FROM clients WHERE id=?',(client_id,)).fetchone():
            raise ValueError('client not found')
        for item in items:
            quantity=int(item.get('quantity',1))
            if quantity<=0: raise ValueError('quantity must be positive')
            catalog_id=item.get('catalog_id') or None
            vehicle_id=item.get('vehicle_id') or None
            catalog=None
            if catalog_id:
                catalog=con.execute('SELECT * FROM catalog WHERE id=? AND active=1',(catalog_id,)).fetchone()
                if not catalog: raise ValueError('active catalog item not found')
                if str(catalog['category']).upper() != 'AVULSA': raise ValueError('direct sales accept only Avulsa catalog products')
            if vehicle_id:
                vehicle=con.execute('SELECT client_id FROM vehicles WHERE id=? AND archived=0',(vehicle_id,)).fetchone()
                if not vehicle or vehicle['client_id']!=client_id: raise ValueError('vehicle does not belong to client')
            description=(item.get('description') or (catalog['name'] if catalog else '')).strip()
            if not description: raise ValueError('item description required')
            unit=(parse_money_api(item['unit_price']) if item.get('unit_price') is not None
                  else int(catalog['price_cents'] if catalog else 0))
            if unit<0: raise ValueError('unit_price cannot be negative')
            normalized.append({'id':uid(),'sale_id':sale_id,'catalog_id':catalog_id,'vehicle_id':vehicle_id,
                               'description':description,'quantity':quantity,'unit_price_cents':unit})
        rec={'id':sale_id,'client_id':client_id,'sold_on':sold_on,'status':status,'paid_on':paid_on,
             'total_cents':sum(x['quantity']*x['unit_price_cents'] for x in normalized),
             'notes':p.get('notes'),'revision':1,'created_at':ts,'updated_at':ts}
        con.execute('''INSERT INTO direct_sales(id,client_id,sold_on,status,paid_on,total_cents,notes,revision,created_at,updated_at)
                       VALUES(:id,:client_id,:sold_on,:status,:paid_on,:total_cents,:notes,:revision,:created_at,:updated_at)''',rec)
        for item in normalized:
            con.execute('''INSERT INTO direct_sale_items(id,sale_id,catalog_id,vehicle_id,description,quantity,unit_price_cents)
                           VALUES(:id,:sale_id,:catalog_id,:vehicle_id,:description,:quantity,:unit_price_cents)''',item)
        audit(con,actor,'DIRECT_SALE_CREATE','direct_sale',sale_id,None,{**rec,'items':normalized})
    return {**rec,'items':normalized}

def set_direct_sale_status(db:Database, actor:int, sale_id:str, p:dict)->dict:
    status=p.get('status')
    if status not in {'OPEN','PAID','CANCELLED'}: raise ValueError('invalid sale status')
    with db.transaction() as con:
        row=con.execute('SELECT * FROM direct_sales WHERE id=?',(sale_id,)).fetchone()
        if not row: raise KeyError('direct sale not found')
        if p.get('expected_revision') is not None and int(p['expected_revision'])!=int(row['revision']):
            raise ValueError(f"revision conflict: current={row['revision']}")
        before=dict(row)
        paid_on=(p.get('paid_on') or date.today().isoformat()) if status=='PAID' else None
        if paid_on: date.fromisoformat(paid_on)
        con.execute('''UPDATE direct_sales SET status=?,paid_on=?,revision=revision+1,updated_at=? WHERE id=?''',
                    (status,paid_on,now(),sale_id))
        after=dict(con.execute('SELECT * FROM direct_sales WHERE id=?',(sale_id,)).fetchone())
        audit(con,actor,'DIRECT_SALE_STATUS','direct_sale',sale_id,before,after)
        return after

def list_direct_sales(db:Database)->list[dict]:
    return [dict(row) for row in db.query('''SELECT ds.*,c.legal_name AS client_name,c.code AS client_code,
           (SELECT COUNT(*) FROM direct_sale_items dsi WHERE dsi.sale_id=ds.id) AS item_count
           FROM direct_sales ds JOIN clients c ON c.id=ds.client_id
           ORDER BY ds.sold_on DESC,ds.created_at DESC''')]

def client_profile(db:Database, client_id:str)->dict:
    row=db.one('SELECT * FROM clients WHERE id=?',(client_id,))
    if not row: raise KeyError('client not found')
    documents=list_client_documents(db,client_id)
    companies=list_client_companies(db,client_id)
    contacts=[]
    if row['email']: contacts.append({'type':'EMAIL','value':row['email'],'is_primary':1})
    if row['phone']: contacts.append({'type':'PHONE','value':row['phone'],'is_primary':0 if row['email'] else 1})
    fleets=[dict(r) for r in db.query('SELECT * FROM fleets WHERE client_id=? AND archived=0 ORDER BY name',(client_id,))]
    vehicles=[annotate_vehicle(dict(r)) for r in db.query('SELECT * FROM vehicles WHERE client_id=? AND archived=0 ORDER BY plate',(client_id,))]
    subscriptions=list_subscriptions(db,client_id=client_id)
    direct_sales=[dict(r) for r in db.query('SELECT * FROM direct_sales WHERE client_id=? ORDER BY sold_on DESC,created_at DESC',(client_id,))]
    for sale in direct_sales:
        sale['direct_sale_items']=[dict(r) for r in db.query('SELECT * FROM direct_sale_items WHERE sale_id=?',(sale['id'],))]
    media_fields='id,entity_type,entity_id,mime,width,height,sha256,created_at'
    client_media=[dict(r) for r in db.query(f"SELECT {media_fields} FROM media WHERE entity_type='client' AND entity_id=? ORDER BY created_at DESC",(client_id,))]
    vehicle_media={vehicle['id']:[dict(r) for r in db.query(
        f"SELECT {media_fields} FROM media WHERE entity_type='vehicle' AND entity_id=? ORDER BY created_at DESC",(vehicle['id'],))]
        for vehicle in vehicles}
    attachment_ids=[subscription['id'] for subscription in subscriptions]+[vehicle['id'] for vehicle in vehicles]+[fleet['id'] for fleet in fleets]
    attachment_where=["(entity_type='client' AND entity_id=?)"]
    attachment_args=[client_id]
    if attachment_ids:
        placeholders=','.join('?' for _ in attachment_ids)
        attachment_where.append(f"entity_id IN ({placeholders})")
        attachment_args.extend(attachment_ids)
    attachments=[dict(r) for r in db.query(
        'SELECT id,entity_type,entity_id,filename,mime,size_bytes,sha256,origin,url,created_at,updated_at FROM attachments WHERE '+
        ' OR '.join(attachment_where)+' ORDER BY created_at DESC',tuple(attachment_args))]
    subscription_received=int(db.one('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE client_id=? AND reversed_at IS NULL',(client_id,))[0])
    direct_paid=int(db.one("SELECT COALESCE(SUM(total_cents),0) FROM direct_sales WHERE client_id=? AND status='PAID'",(client_id,))[0])
    expenses_paid=int(db.one('''SELECT COALESCE(SUM(d.amount_cents),0) FROM disbursements d
                               JOIN expenses e ON e.id=d.expense_id WHERE e.client_id=? AND d.reversed_at IS NULL''',(client_id,))[0])
    expenses_generated=int(db.one('SELECT COALESCE(SUM(expected_amount_cents),0) FROM expenses WHERE client_id=?',(client_id,))[0])
    generated_total=subscription_received+direct_paid-expenses_generated
    projection=client_projection(db,[client_id])[client_id]
    from .mobility import list_mobility
    mobility=list_mobility(db,client_id=client_id)
    from .mobility import active_subscription_codes
    covered=active_subscription_codes(db)
    for vehicle in vehicles:
        vehicle['subscription_codes']=covered.get(vehicle['id'],[])
        vehicle['subscriptions_count']=len(vehicle['subscription_codes'])
    fleet_meta={f['id']:f for f in mobility['fleets']}
    for fleet in fleets:
        meta=fleet_meta.get(fleet['id'],{})
        fleet.update({k:meta.get(k) for k in ('vehicle_group','vehicle_group_label','vehicles_count','subscriptions_count','company_name')})
    return {'client':dict(row),'documents':documents,'companies':companies,'contacts':contacts,'mobility':mobility,
            'client_media':client_media,'fleets':fleets,'vehicles':vehicles,'vehicle_media':vehicle_media,
            'subscriptions':subscriptions,'attachments':attachments,'direct_sales':direct_sales,
            'summary':{'vehicles_count':len(vehicles),
                       'particular_vehicles_count':sum(1 for vehicle in vehicles if not vehicle.get('fleet_id')),
                       'fleet_vehicles_count':sum(1 for vehicle in vehicles if vehicle.get('fleet_id')),
                       'generated_value_cents':generated_total,
                       'vehicle_breakdown':vehicle_breakdown(db,client_id),
                       'contracted_active_cents':projection['contracted_active_cents'],
                       'realized_revenue_cents':projection['realized_revenue_cents'],
                       'open_purchases_cents':projection['open_purchases_cents'],
                       'active_subscriptions':projection['active_subscriptions']},
            'financial':{'subscription_received_cents':subscription_received,
                         'direct_sales_paid_cents':direct_paid,'client_expenses_paid_cents':expenses_paid,
                         'client_expenses_generated_cents':expenses_generated,'generated_total_cents':generated_total}}


def generate_charge(db:Database, actor:int, sid:str, competence:str)->dict:
    with db.transaction() as con:
        existing=con.execute('SELECT * FROM charges WHERE subscription_id=? AND competence=?',(sid,competence)).fetchone()
        if existing: return dict(existing)
        sub=con.execute('SELECT * FROM subscriptions WHERE id=?',(sid,)).fetchone()
        if not sub: raise KeyError('subscription not found')
        if sub['lifecycle_status']!='ACTIVE': raise ValueError('subscription is not active')
        amount=con.execute('SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM subscription_items WHERE subscription_id=?',(sid,)).fetchone()[0]
        cid=uid(); ts=now(); rec={'id':cid,'subscription_id':sid,'client_id':sub['client_id'],'competence':competence,
             'due_on':due_date(competence,int(sub['due_day'])).isoformat(),'amount_cents':int(amount),'adjustment_cents':0,'status':'OPEN','revision':1,'created_at':ts,'updated_at':ts}
        con.execute('''INSERT INTO charges(id,subscription_id,client_id,competence,due_on,amount_cents,adjustment_cents,status,revision,created_at,updated_at)
                     VALUES(:id,:subscription_id,:client_id,:competence,:due_on,:amount_cents,:adjustment_cents,:status,:revision,:created_at,:updated_at)''',rec)
        audit(con,actor,'CHARGE_GENERATE','charge',cid,None,rec)
        return rec

def _charge_paid(con, charge_id:str)->int:
    a=con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM payment_allocations WHERE charge_id=? AND active=1',(charge_id,)).fetchone()[0]
    b=con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM credit_allocations WHERE charge_id=? AND active=1',(charge_id,)).fetchone()[0]
    return int(a)+int(b)

def _refresh_charge_status(con, charge_id:str)->str:
    row=con.execute('SELECT amount_cents,adjustment_cents,status FROM charges WHERE id=?',(charge_id,)).fetchone()
    if not row: raise KeyError('charge not found')
    if row['status']=='VOID': return 'VOID'
    total=int(row['amount_cents'])+int(row['adjustment_cents']); paid=_charge_paid(con,charge_id)
    status='PAID' if paid>=total else ('PARTIAL' if paid>0 else 'OPEN')
    con.execute('UPDATE charges SET status=?,updated_at=? WHERE id=?',(status,now(),charge_id))
    return status

def create_payment(db:Database, actor:int, p:dict)->dict:
    client_id=p.get('client_id'); amount=parse_money_api(p.get('amount','0'))
    if not client_id or amount<=0: raise ValueError('client_id and positive amount required')
    allocations=p.get('allocations') or []; allocated=sum(parse_money_api(x.get('amount','0')) for x in allocations)
    if allocated>amount: raise ValueError('allocations exceed payment')
    if allocated<amount and not p.get('create_credit'): raise ValueError('unallocated amount requires create_credit=true')
    pid=uid(); ts=now()
    with db.transaction() as con:
        for x in allocations:
            charge=con.execute('SELECT * FROM charges WHERE id=? AND client_id=?',(x['charge_id'],client_id)).fetchone()
            if not charge: raise ValueError('charge not found for client')
            open_cents=charge['amount_cents']+charge['adjustment_cents']-_charge_paid(con,charge['id'])
            alloc=parse_money_api(x['amount'])
            if alloc<=0 or alloc>open_cents: raise ValueError('allocation exceeds charge balance')
        con.execute('INSERT INTO payments(id,client_id,paid_on,amount_cents,method,notes,created_at) VALUES(?,?,?,?,?,?,?)',
                    (pid,client_id,p.get('paid_on',date.today().isoformat()),amount,p.get('method'),p.get('notes'),ts))
        for x in allocations:
            alloc=parse_money_api(x['amount']); aid=uid()
            con.execute('INSERT INTO payment_allocations(id,payment_id,charge_id,amount_cents,active,created_at) VALUES(?,?,?,?,1,?)',(aid,pid,x['charge_id'],alloc,ts))
        credit_id=None
        if allocated<amount:
            delta=amount-allocated; credit_id=uid()
            con.execute('INSERT INTO credits(id,client_id,origin_payment_id,amount_cents,balance_cents,status,created_at) VALUES(?,?,?,?,?,?,?)',
                        (credit_id,client_id,pid,delta,delta,'OPEN',ts))
        for x in allocations: _refresh_charge_status(con,x['charge_id'])
        rec={'id':pid,'client_id':client_id,'paid_on':p.get('paid_on',date.today().isoformat()),'amount_cents':amount,'allocated_cents':allocated,'credit_id':credit_id}
        audit(con,actor,'PAYMENT_CREATE','payment',pid,None,rec)
        return rec

def apply_credit(db:Database, actor:int, credit_id:str, charge_id:str, amount_value)->dict:
    amount=parse_money_api(amount_value)
    with db.transaction() as con:
        credit=con.execute('SELECT * FROM credits WHERE id=?',(credit_id,)).fetchone(); charge=con.execute('SELECT * FROM charges WHERE id=?',(charge_id,)).fetchone()
        if not credit or not charge or credit['client_id']!=charge['client_id']: raise ValueError('credit/charge mismatch')
        open_cents=charge['amount_cents']+charge['adjustment_cents']-_charge_paid(con,charge_id)
        if amount<=0 or amount>credit['balance_cents'] or amount>open_cents: raise ValueError('invalid credit allocation')
        caid=uid(); applied=date.today().isoformat()
        con.execute('INSERT INTO credit_allocations(id,credit_id,charge_id,amount_cents,active,applied_on) VALUES(?,?,?,?,1,?)',(caid,credit_id,charge_id,amount,applied))
        con.execute("UPDATE credits SET balance_cents=balance_cents-?,status=CASE WHEN balance_cents-?=0 THEN 'CLOSED' ELSE 'OPEN' END WHERE id=?",(amount,amount,credit_id))
        _refresh_charge_status(con,charge_id)
        rec={'id':caid,'credit_id':credit_id,'charge_id':charge_id,'amount_cents':amount,'applied_on':applied}
        audit(con,actor,'CREDIT_APPLY','credit',credit_id,None,rec)
        return rec

def reverse_payment(db:Database, actor:int, payment_id:str)->dict:
    with db.transaction() as con:
        payment=con.execute('SELECT * FROM payments WHERE id=?',(payment_id,)).fetchone()
        if not payment or payment['reversed_at']: raise ValueError('payment not reversible')
        affected={r[0] for r in con.execute('SELECT charge_id FROM payment_allocations WHERE payment_id=? AND active=1',(payment_id,)).fetchall()}
        ts=now(); con.execute('UPDATE payments SET reversed_at=? WHERE id=?',(ts,payment_id)); con.execute('UPDATE payment_allocations SET active=0 WHERE payment_id=?',(payment_id,))
        credits=con.execute('SELECT * FROM credits WHERE origin_payment_id=?',(payment_id,)).fetchall()
        for c in credits:
            affected.update(r[0] for r in con.execute('SELECT charge_id FROM credit_allocations WHERE credit_id=? AND active=1',(c['id'],)).fetchall())
            con.execute('UPDATE credit_allocations SET active=0,reversed_on=? WHERE credit_id=? AND active=1',(date.today().isoformat(),c['id']))
            con.execute("UPDATE credits SET balance_cents=0,status='REVERSED' WHERE id=?",(c['id'],))
        # AJ-12: a discount granted together with this payment is undone with it.
        for adj in con.execute('SELECT * FROM charge_adjustments WHERE reason=?',(f'Desconto no pagamento {payment_id}',)).fetchall():
            back=-int(adj['amount_cents'])
            con.execute('INSERT INTO charge_adjustments(id,charge_id,kind,amount_cents,reason,effective_on,created_at) VALUES(?,?,?,?,?,?,?)',
                        (uid(),adj['charge_id'],'OTHER',back,f'Estorno do desconto {payment_id}',date.today().isoformat(),ts))
            con.execute('UPDATE charges SET adjustment_cents=adjustment_cents+?,revision=revision+1,updated_at=? WHERE id=?',(back,ts,adj['charge_id']))
            affected.add(adj['charge_id'])
        for charge_id in affected: _refresh_charge_status(con,charge_id)
        rec={'id':payment_id,'reversed_at':ts}; audit(con,actor,'PAYMENT_REVERSE','payment',payment_id,dict(payment),rec); return rec

def create_expense(db:Database, actor:int, p:dict)->dict:
    if not p.get('category') or not p.get('description') or not p.get('competence'): raise ValueError('category, description and competence required')
    eid=uid(); ts=now(); amount=parse_money_api(p.get('expected_amount','0'))
    if amount < 0: raise ValueError('expected amount cannot be negative')
    rec={'id':eid,'category':p['category'],'description':p['description'],'competence':p['competence'],'due_on':p.get('due_on'),'expected_amount_cents':amount,
         'supplier':p.get('supplier'),'client_id':p.get('client_id'),'vehicle_id':p.get('vehicle_id'),'subscription_id':p.get('subscription_id'),'catalog_id':p.get('catalog_id'),
         'recurrence_id':p.get('recurrence_id'),'status':'OPEN','revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute('''INSERT INTO expenses(id,category,description,competence,due_on,expected_amount_cents,supplier,client_id,vehicle_id,subscription_id,catalog_id,recurrence_id,status,revision,created_at,updated_at)
                     VALUES(:id,:category,:description,:competence,:due_on,:expected_amount_cents,:supplier,:client_id,:vehicle_id,:subscription_id,:catalog_id,:recurrence_id,:status,:revision,:created_at,:updated_at)''',rec)
        audit(con,actor,'EXPENSE_CREATE','expense',eid,None,rec)
    return rec

def add_disbursement(db:Database, actor:int, expense_id:str, p:dict)->dict:
    amount=parse_money_api(p.get('amount','0')); did=uid(); ts=now()
    with db.transaction() as con:
        exp=con.execute('SELECT * FROM expenses WHERE id=?',(expense_id,)).fetchone()
        if not exp: raise KeyError('expense not found')
        paid=con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE expense_id=? AND reversed_at IS NULL',(expense_id,)).fetchone()[0]
        if amount<=0 or paid+amount>exp['expected_amount_cents']: raise ValueError('disbursement exceeds expense')
        con.execute('INSERT INTO disbursements(id,expense_id,paid_on,amount_cents,created_at) VALUES(?,?,?,?,?)',(did,expense_id,p.get('paid_on',date.today().isoformat()),amount,ts))
        total=paid+amount; status='PAID' if total==exp['expected_amount_cents'] else 'PARTIAL'
        con.execute('UPDATE expenses SET status=?,updated_at=? WHERE id=?',(status,now(),expense_id))
        rec={'id':did,'expense_id':expense_id,'amount_cents':amount,'expense_status':status}; audit(con,actor,'DISBURSEMENT_CREATE','expense',expense_id,None,rec); return rec

def create_fiscal(db:Database, actor:int, p:dict)->dict:
    # Compatibility seam: R06 owns fiscal -> expense atomicity.
    from .finance import create_fiscal_obligation
    return create_fiscal_obligation(db,actor,p)

def dashboard(db:Database, as_of:date|None=None, year:int|None=None)->dict:
    q=lambda sql,args=(): db.one(sql,args)[0]
    today=as_of or date.today()
    month_start=today.replace(day=1)
    next_month=(date(today.year+1,1,1) if today.month==12 else date(today.year,today.month+1,1))
    year_start=date(today.year,1,1)
    def realized(start:date,end:date)->int:
        dates=(start.isoformat(),end.isoformat())
        payments=q('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE reversed_at IS NULL AND paid_on>=? AND paid_on<?',dates)
        sales=q("SELECT COALESCE(SUM(total_cents),0) FROM direct_sales WHERE status='PAID' AND paid_on>=? AND paid_on<?",dates)
        return int(payments)+int(sales)
    def spent(start:date,end:date)->int:
        return int(q('SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE reversed_at IS NULL AND paid_on>=? AND paid_on<?',
                     (start.isoformat(),end.isoformat())))
    monthly_value=realized(month_start,next_month)
    monthly_spent=spent(month_start,next_month)
    accumulated=realized(year_start,month_start)-spent(year_start,month_start)
    clients_count=int(q('SELECT COUNT(*) FROM clients WHERE archived=0'))
    products_count=int(q('SELECT COUNT(*) FROM catalog WHERE active=1'))
    vehicles_count=int(q('SELECT COUNT(*) FROM vehicles WHERE archived=0'))
    subscription_units=int(q("""SELECT COALESCE(SUM(si.quantity),0) FROM subscription_items si
                              JOIN subscriptions s ON s.id=si.subscription_id WHERE s.lifecycle_status='ACTIVE'"""))
    overview={r['id']:{'client_id':r['id'],'client_name':r['legal_name'],'cars':0,
                       'subscription_daily_cents':0,'subscription_monthly_cents':0,
                       'subscription_annual_cents':0,'purchases_cents':0}
              for r in db.query('SELECT id,legal_name FROM clients WHERE archived=0 ORDER BY legal_name')}
    for row in db.query('SELECT client_id,COUNT(*) AS cars FROM vehicles WHERE archived=0 GROUP BY client_id'):
        if row['client_id'] in overview: overview[row['client_id']]['cars']=int(row['cars'])
    for row in db.query("""SELECT s.client_id,s.billing_cycle,SUM(si.quantity*si.unit_price_cents) AS amount
                           FROM subscriptions s JOIN subscription_items si ON si.subscription_id=s.id
                           WHERE s.lifecycle_status='ACTIVE' GROUP BY s.client_id,s.billing_cycle"""):
        if row['client_id'] in overview and row['billing_cycle'] in {'DAILY','MONTHLY','ANNUAL'}:
            key='subscription_'+row['billing_cycle'].lower()+'_cents'
            overview[row['client_id']][key]=int(row['amount'] or 0)
    for row in db.query("""SELECT client_id,SUM(total_cents) AS amount FROM direct_sales
                           WHERE status<>'CANCELLED' GROUP BY client_id"""):
        if row['client_id'] in overview: overview[row['client_id']]['purchases_cents']=int(row['amount'] or 0)
    active_clients=q("SELECT COUNT(*) FROM clients WHERE archived=0 AND status='ACTIVE'")
    active_vehicles=q('SELECT COUNT(*) FROM vehicles WHERE archived=0')
    active_subscriptions=q("SELECT COUNT(*) FROM subscriptions WHERE lifecycle_status='ACTIVE'")
    charge_total=q("SELECT COALESCE(SUM(amount_cents+adjustment_cents),0) FROM charges WHERE status<>'VOID'")
    payment_total=q('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE reversed_at IS NULL')
    expense_total=q('SELECT COALESCE(SUM(expected_amount_cents),0) FROM expenses')
    disb_total=q('SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE reversed_at IS NULL')
    if year is not None and not (2000 <= int(year) <= 2100):
        raise ValueError('year must be between 2000 and 2100')
    period_start = date(int(year), 1, 1) if year is not None else None
    period_end = date(int(year) + 1, 1, 1) if year is not None else None
    # AJ-01: Receita Geral = realized only (paid, not reversed, paid_on <= today). Forecast is separate.
    period_revenue = realized_revenue(db, period_start, period_end, today)
    general = general_expenses(db, period_start, period_end)  # 2.4.0: pagas e a pagar
    period_expenses = general['total_cents']
    available_years = sorted({
        int(row['year']) for row in db.query("""SELECT substr(paid_on,1,4) AS year FROM payments WHERE reversed_at IS NULL
        UNION SELECT substr(paid_on,1,4) FROM direct_sales WHERE status='PAID' AND paid_on IS NOT NULL
        UNION SELECT substr(paid_on,1,4) FROM disbursements WHERE reversed_at IS NULL""")
        if str(row['year'] or '').isdigit()
    }, reverse=True)
    overdue=q("SELECT COUNT(*) FROM charges c WHERE c.status<>'VOID' AND c.due_on<date('now') AND (c.amount_cents+c.adjustment_cents) > (SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa WHERE pa.charge_id=c.id AND pa.active=1)+(SELECT COALESCE(SUM(ca.amount_cents),0) FROM credit_allocations ca WHERE ca.charge_id=c.id AND ca.active=1)")
    return {'active_clients':active_clients,'active_vehicles':active_vehicles,'active_subscriptions':active_subscriptions,
            'clients_count':clients_count,'products_count':products_count,'vehicles_count':vehicles_count,
            'active_subscription_products':subscription_units,'accumulated_profit_cents':accumulated,
            'monthly_value_cents':monthly_value,'monthly_spent_cents':monthly_spent,
            'real_profit_cents':monthly_value-monthly_spent,'client_overview':list(overview.values()),
            'revenue_expected_cents':charge_total,'revenue_received_cents':payment_total,'expenses_expected_cents':expense_total,
            'expenses_paid_cents':disb_total,'cash_result_cents':payment_total-disb_total,'overdue_charges':overdue,
            'period':{'year':year,'label':str(year) if year is not None else 'Geral','revenue_cents':period_revenue,
                      'expenses_cents':period_expenses,'expenses_paid_cents':general['paid_cents'],
                      'expenses_open_cents':general['open_cents'],'result_cents':period_revenue-period_expenses},
            'month_forecast':month_forecast(db,today),
            'vehicle_breakdown':vehicle_breakdown(db),
            'available_years':available_years,
            'integrations':{'drive':'PREPARED_DISABLED','tracking':'PREPARED_DISABLED','fiscal_official':'PREPARED_DISABLED'}}

def search(db:Database, query:str)->list[dict]:
    q=f"%{query.strip()}%"; results=[]
    for table,cols,label in [('clients',['code','legal_name','trade_name','public_name','document','phone','email'],'client'),('vehicles',['code','plate','type','renavam','tracker_ref','tracker_serial_imei'],'vehicle'),('catalog',['code','name','category'],'catalog')]:
        where=' OR '.join([f"{c} LIKE ?" for c in cols]); rows=db.query(f"SELECT id,{','.join(cols)} FROM {table} WHERE {where} LIMIT 30",tuple(q for _ in cols))
        for row in rows: results.append({'type':label,**dict(row)})
    return results[:50]
