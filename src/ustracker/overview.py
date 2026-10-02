from __future__ import annotations

import unicodedata

from .db import Database


def _fold(value) -> str:
    text=unicodedata.normalize('NFKD',str(value or ''))
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def client_activity_overview(db:Database,query:str='')->list[dict]:
    clients=[dict(r) for r in db.query('SELECT id,legal_name,trade_name,public_name,status FROM clients WHERE archived=0 ORDER BY legal_name')]
    needle=_fold(query).strip()
    if needle:
        clients=[c for c in clients if any(needle in _fold(c.get(k)) for k in ('legal_name','trade_name','public_name'))]
    ids={c['id'] for c in clients}
    rows={c['id']:{'client_id':c['id'],'client_name':c['legal_name'],'vehicles_count':0,'active_subscriptions':0,
                      'purchases_count':0,'purchases_paid_cents':0,'received_cents':0,'value_generated_cents':0,'status':c['status']} for c in clients}
    if not rows:return []
    for r in db.query('SELECT client_id,COUNT(*) AS n FROM vehicles WHERE archived=0 GROUP BY client_id'):
        if r['client_id'] in ids: rows[r['client_id']]['vehicles_count']=int(r['n'])
    for r in db.query("SELECT client_id,COUNT(*) AS n FROM subscriptions WHERE lifecycle_status='ACTIVE' GROUP BY client_id"):
        if r['client_id'] in ids: rows[r['client_id']]['active_subscriptions']=int(r['n'])
    for r in db.query("SELECT client_id,COUNT(*) AS n,COALESCE(SUM(CASE WHEN status='PAID' THEN total_cents ELSE 0 END),0) AS paid FROM direct_sales WHERE status<>'CANCELLED' GROUP BY client_id"):
        if r['client_id'] in ids:
            rows[r['client_id']]['purchases_count']=int(r['n']); rows[r['client_id']]['purchases_paid_cents']=int(r['paid'] or 0)
    for r in db.query('SELECT client_id,COALESCE(SUM(amount_cents),0) AS total FROM payments WHERE reversed_at IS NULL GROUP BY client_id'):
        if r['client_id'] in ids: rows[r['client_id']]['received_cents']=int(r['total'] or 0)
    for rec in rows.values():
        rec['value_generated_cents']=rec['received_cents']+rec['purchases_paid_cents']
    return [rows[c['id']] for c in clients]
