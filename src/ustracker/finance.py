from __future__ import annotations

from .db import Database
from .money import parse_money_api
from .services import audit, now, uid


def _insert_fiscal_expense(con, fiscal, actor:int):
    if fiscal['amount_cents'] is None:
        raise ValueError('fiscal obligation has no amount to post as expense')
    if fiscal['expense_id']:
        existing=con.execute('SELECT * FROM expenses WHERE id=?',(fiscal['expense_id'],)).fetchone()
        if not existing: raise RuntimeError('fiscal obligation references a missing expense')
        return dict(existing)
    eid=uid(); ts=now()
    rec={
        'id':eid,'category':'FISCAL','description':fiscal['description'],'competence':fiscal['competence'],
        'due_on':fiscal['due_on'],'expected_amount_cents':int(fiscal['amount_cents']),'supplier':None,
        'client_id':None,'vehicle_id':None,'subscription_id':None,'catalog_id':None,
        'recurrence_id':None,'status':'OPEN','revision':1,'created_at':ts,'updated_at':ts,
    }
    con.execute('''INSERT INTO expenses(id,category,description,competence,due_on,expected_amount_cents,supplier,client_id,vehicle_id,subscription_id,catalog_id,recurrence_id,status,revision,created_at,updated_at)
                   VALUES(:id,:category,:description,:competence,:due_on,:expected_amount_cents,:supplier,:client_id,:vehicle_id,:subscription_id,:catalog_id,:recurrence_id,:status,:revision,:created_at,:updated_at)''',rec)
    con.execute('UPDATE fiscal_obligations SET expense_id=?,updated_at=? WHERE id=?',(eid,ts,fiscal['id']))
    audit(con,actor,'FISCAL_EXPENSE_LINK','fiscal',fiscal['id'],None,{'expense_id':eid,'amount_cents':rec['expected_amount_cents']})
    return rec


def create_fiscal_obligation(db:Database,actor:int,p:dict)->dict:
    if not p.get('competence') or not p.get('description'): raise ValueError('competence and description required')
    amount=parse_money_api(p['amount']) if p.get('amount') not in (None,'') else None
    if amount is not None and amount < 0: raise ValueError('fiscal amount cannot be negative')
    fid=uid(); ts=now()
    rec={'id':fid,'competence':p['competence'],'description':str(p['description']).strip(),'amount_cents':amount,
         'due_on':p.get('due_on') or None,'status':p.get('status','OPEN'),'external_ref':p.get('external_ref') or None,
         'expense_id':None,'created_at':ts,'updated_at':ts}
    with db.transaction() as con:
        con.execute('''INSERT INTO fiscal_obligations(id,competence,description,amount_cents,due_on,status,external_ref,expense_id,created_at,updated_at)
                       VALUES(:id,:competence,:description,:amount_cents,:due_on,:status,:external_ref,:expense_id,:created_at,:updated_at)''',rec)
        if amount is not None:
            expense=_insert_fiscal_expense(con,rec,actor)
            rec['expense_id']=expense['id']
        audit(con,actor,'FISCAL_CREATE','fiscal',fid,None,rec)
        return rec


def ensure_fiscal_expense(db:Database,actor:int,fiscal_id:str)->dict:
    with db.transaction() as con:
        fiscal=con.execute('SELECT * FROM fiscal_obligations WHERE id=?',(fiscal_id,)).fetchone()
        if not fiscal: raise KeyError('fiscal obligation not found')
        return _insert_fiscal_expense(con,dict(fiscal),actor)


def finance_snapshot(db:Database)->dict:
    payments=[dict(r) for r in db.query('SELECT p.*,c.legal_name AS client_name,c.code AS client_code FROM payments p LEFT JOIN clients c ON c.id=p.client_id ORDER BY p.paid_on DESC,p.created_at DESC')]
    active_payments=[payment for payment in payments if not payment.get('reversed_at')]
    realized_received=sum(int(payment['amount_cents']) for payment in active_payments)
    realized_expenses=int(db.one(
        'SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE reversed_at IS NULL'
    )[0])
    return {
        'payments':payments,
        'active_payments':active_payments,
        'realized_received_cents':realized_received,
        'realized_expenses_cents':realized_expenses,
        'cash_result_cents':realized_received-realized_expenses,
        'expenses':[dict(r) for r in db.query('SELECT * FROM expenses ORDER BY competence DESC,created_at DESC')],
        'fiscal':[dict(r) for r in db.query('SELECT * FROM fiscal_obligations ORDER BY competence DESC,created_at DESC')],
        'charges':[dict(r) for r in db.query("SELECT ch.*,s.code||'/'||substr(ch.competence,1,7) AS code FROM charges ch LEFT JOIN subscriptions s ON s.id=ch.subscription_id WHERE ch.status<>'VOID' ORDER BY ch.due_on DESC,ch.created_at DESC")],
        'disbursements':[dict(r) for r in db.query('SELECT * FROM disbursements ORDER BY paid_on DESC,created_at DESC')],
    }
