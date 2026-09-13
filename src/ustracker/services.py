from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .db import Database
from .money import due_date, parse_money_api

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

def create_client(db:Database, actor:int, p:dict)->dict:
    if not p.get('legal_name','').strip(): raise ValueError('legal_name required')
    status=p.get('status','ACTIVE')
    if status not in {'ACTIVE','INACTIVE','BLOCKED','CANCELLED'}: raise ValueError('invalid status')
    cid=uid(); ts=now()
    rec={'id':cid,'legal_name':p['legal_name'].strip(),'trade_name':p.get('trade_name'),'public_name':p.get('public_name'),
         'document':p.get('document'),'email':p.get('email'),'phone':p.get('phone'),'address':p.get('address'),'notes':p.get('notes'),
         'status':status,'archived':0,'revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute('INSERT INTO clients VALUES(:id,:legal_name,:trade_name,:public_name,:document,:email,:phone,:address,:notes,:status,:archived,:revision,:created_at,:updated_at)',rec)
        audit(con,actor,'CLIENT_CREATE','client',cid,None,rec)
    return rec

def update_client(db:Database, actor:int, cid:str, p:dict)->dict:
    with db.transaction() as con:
        old=con.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
        if not old: raise KeyError('client not found')
        before=dict(old); allowed={'legal_name','trade_name','public_name','document','email','phone','address','notes','status','archived'}
        if p.get('expected_revision') is not None and int(p['expected_revision']) != int(old['revision']):
            raise ValueError(f"revision conflict: current={old['revision']}")
        fields=[]; values=[]
        for k,v in p.items():
            if k in allowed:
                fields.append(f'{k}=?'); values.append(v)
        if not fields: return before
        fields+=['revision=revision+1','updated_at=?']; values.append(now()); values.append(cid)
        con.execute(f"UPDATE clients SET {','.join(fields)} WHERE id=?",values)
        after=dict(con.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone())
        audit(con,actor,'CLIENT_UPDATE','client',cid,before,after)
        return after

def create_vehicle(db:Database, actor:int, p:dict)->dict:
    if not p.get('client_id') or not p.get('plate') or not p.get('type'): raise ValueError('client_id, plate and type required')
    vid=uid(); ts=now(); plate=re.sub(r'[^A-Za-z0-9]','',p['plate']).upper()
    rec={'id':vid,'client_id':p['client_id'],'fleet_id':p.get('fleet_id') or None,'plate':plate,'type':p['type'],'renavam':p.get('renavam'),
         'tracker_ref':p.get('tracker_ref'),'tracker_serial_imei':p.get('tracker_serial_imei'),'installed_on':p.get('installed_on'),
         'tracking_status':p.get('tracking_status','UNTRACKED'),'notes':p.get('notes'),'archived':0,'revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0',(p['client_id'],)).fetchone(): raise ValueError('client not found')
        if rec['fleet_id']:
            fleet=con.execute('SELECT * FROM fleets WHERE id=? AND archived=0',(rec['fleet_id'],)).fetchone()
            if not fleet or fleet['client_id']!=p['client_id']: raise ValueError('fleet does not belong to client')
        con.execute('''INSERT INTO vehicles(id,client_id,fleet_id,plate,type,renavam,tracker_ref,tracker_serial_imei,installed_on,tracking_status,notes,archived,revision,created_at,updated_at)
                     VALUES(:id,:client_id,:fleet_id,:plate,:type,:renavam,:tracker_ref,:tracker_serial_imei,:installed_on,:tracking_status,:notes,:archived,:revision,:created_at,:updated_at)''',rec)
        con.execute('INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',(uid(),vid,p['client_id'],p.get('fleet_id'),p.get('effective_from',date.today().isoformat()),ts))
        audit(con,actor,'VEHICLE_CREATE','vehicle',vid,None,rec)
    return rec

def create_catalog(db:Database, actor:int, p:dict)->dict:
    required=['code','name','category','kind']
    if any(not p.get(k) for k in required): raise ValueError('code, name, category and kind required')
    if p['kind'] not in {'PLAN','ITEM'}: raise ValueError('invalid kind')
    cid=uid(); ts=now(); price=parse_money_api(p.get('price','0')); cost=parse_money_api(p.get('cost','0'))
    rec={'id':cid,'code':p['code'].strip().upper(),'name':p['name'].strip(),'description':p.get('description'),'category':p['category'],
         'kind':p['kind'],'billing_interval_months':int(p.get('billing_interval_months',1)),'price_cents':price,'cost_cents':cost,
         'notes':p.get('notes'),'public':1 if p.get('public') else 0,'active':1,'revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute('''INSERT INTO catalog(id,code,name,description,category,kind,billing_interval_months,price_cents,cost_cents,notes,public,active,revision,created_at,updated_at)
                     VALUES(:id,:code,:name,:description,:category,:kind,:billing_interval_months,:price_cents,:cost_cents,:notes,:public,:active,:revision,:created_at,:updated_at)''',rec)
        con.execute('INSERT INTO catalog_prices(id,catalog_id,effective_from,price_cents,cost_cents,created_at) VALUES(?,?,?,?,?,?)',(uid(),cid,date.today().isoformat(),price,cost,ts))
        audit(con,actor,'CATALOG_CREATE','catalog',cid,None,rec)
    return rec

def create_subscription(db:Database, actor:int, p:dict)->dict:
    sid=uid(); ts=now(); items=p.get('items') or []
    if not p.get('client_id') or not p.get('start_on') or not items: raise ValueError('client_id, start_on and items required')
    rec={'id':sid,'client_id':p['client_id'],'signed_on':p.get('signed_on',date.today().isoformat()),'start_on':p['start_on'],'end_on':p.get('end_on'),
         'due_day':int(p.get('due_day',10)),'billing_interval_months':int(p.get('billing_interval_months',1)),'renewal_mode':p.get('renewal_mode','MANUAL'),
         'lifecycle_status':p.get('lifecycle_status','ACTIVE'),'revision':1,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute('''INSERT INTO subscriptions(id,client_id,signed_on,start_on,end_on,due_day,billing_interval_months,renewal_mode,lifecycle_status,revision,created_at,updated_at)
                     VALUES(:id,:client_id,:signed_on,:start_on,:end_on,:due_day,:billing_interval_months,:renewal_mode,:lifecycle_status,:revision,:created_at,:updated_at)''',rec)
        for item in items:
            catalog=None
            if item.get('catalog_id'):
                catalog=con.execute('SELECT * FROM catalog WHERE id=?',(item['catalog_id'],)).fetchone()
            description=item.get('description') or (catalog['name'] if catalog else None)
            if not description: raise ValueError('subscription item description required')
            unit=parse_money_api(item['unit_price']) if 'unit_price' in item else int(catalog['price_cents'] if catalog else 0)
            con.execute('INSERT INTO subscription_items(id,subscription_id,catalog_id,vehicle_id,description,quantity,unit_price_cents) VALUES(?,?,?,?,?,?,?)',
                        (uid(),sid,item.get('catalog_id'),item.get('vehicle_id'),description,int(item.get('quantity',1)),unit))
        audit(con,actor,'SUBSCRIPTION_CREATE','subscription',sid,None,rec)
    return rec

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
    fid=uid(); ts=now(); amount=parse_money_api(p['amount']) if p.get('amount') not in (None,'') else None
    if not p.get('competence') or not p.get('description'): raise ValueError('competence and description required')
    rec={'id':fid,'competence':p['competence'],'description':p['description'],'amount_cents':amount,'due_on':p.get('due_on'),'status':p.get('status','OPEN'),'external_ref':p.get('external_ref'),'expense_id':p.get('expense_id'),'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute('''INSERT INTO fiscal_obligations(id,competence,description,amount_cents,due_on,status,external_ref,expense_id,created_at,updated_at)
                     VALUES(:id,:competence,:description,:amount_cents,:due_on,:status,:external_ref,:expense_id,:created_at,:updated_at)''',rec)
        audit(con,actor,'FISCAL_CREATE','fiscal',fid,None,rec)
    return rec

def dashboard(db:Database)->dict:
    q=lambda sql,args=(): db.one(sql,args)[0]
    active_clients=q("SELECT COUNT(*) FROM clients WHERE archived=0 AND status='ACTIVE'")
    active_vehicles=q('SELECT COUNT(*) FROM vehicles WHERE archived=0')
    active_subscriptions=q("SELECT COUNT(*) FROM subscriptions WHERE lifecycle_status='ACTIVE'")
    charge_total=q("SELECT COALESCE(SUM(amount_cents+adjustment_cents),0) FROM charges WHERE status<>'VOID'")
    payment_total=q('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE reversed_at IS NULL')
    expense_total=q('SELECT COALESCE(SUM(expected_amount_cents),0) FROM expenses')
    disb_total=q('SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE reversed_at IS NULL')
    overdue=q("SELECT COUNT(*) FROM charges c WHERE c.status<>'VOID' AND c.due_on<date('now') AND (c.amount_cents+c.adjustment_cents) > (SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa WHERE pa.charge_id=c.id AND pa.active=1)+(SELECT COALESCE(SUM(ca.amount_cents),0) FROM credit_allocations ca WHERE ca.charge_id=c.id AND ca.active=1)")
    return {'active_clients':active_clients,'active_vehicles':active_vehicles,'active_subscriptions':active_subscriptions,
            'revenue_expected_cents':charge_total,'revenue_received_cents':payment_total,'expenses_expected_cents':expense_total,
            'expenses_paid_cents':disb_total,'cash_result_cents':payment_total-disb_total,'overdue_charges':overdue,
            'integrations':{'drive':'PREPARED_DISABLED','tracking':'PREPARED_DISABLED','fiscal_official':'PREPARED_DISABLED'}}

def search(db:Database, query:str)->list[dict]:
    q=f"%{query.strip()}%"; results=[]
    for table,cols,label in [('clients',['legal_name','trade_name','public_name','document','phone','email'],'client'),('vehicles',['plate','type','renavam','tracker_ref','tracker_serial_imei'],'vehicle'),('catalog',['code','name','category'],'catalog')]:
        where=' OR '.join([f"{c} LIKE ?" for c in cols]); rows=db.query(f"SELECT id,{','.join(cols)} FROM {table} WHERE {where} LIMIT 30",tuple(q for _ in cols))
        for row in rows: results.append({'type':label,**dict(row)})
    return results[:50]
