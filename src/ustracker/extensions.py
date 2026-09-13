from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Any, Callable

from .db import Database
from .money import due_date, parse_money_api
from .services import _refresh_charge_status, audit, now, uid


def _payload_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def run_idempotent(
    db: Database,
    actor: int,
    route: str,
    operation_id: str,
    payload: Any,
    fn: Callable[[], Any],
) -> Any:
    operation_id = str(operation_id or '').strip()
    if len(operation_id) < 8 or len(operation_id) > 128:
        raise ValueError('X-Operation-ID is required for mutating operations')
    digest = _payload_hash(payload)
    ts = now()
    with db.transaction() as con:
        existing = con.execute('SELECT * FROM operations WHERE operation_id=?', (operation_id,)).fetchone()
        if existing:
            if existing['route'] != route or existing['payload_hash'] != digest or int(existing['actor_slot']) != int(actor):
                raise ValueError('operation id was already used with different input')
            if existing['status'] == 'DONE':
                return json.loads(existing['response_json'])
            raise RuntimeError('operation is pending from a previous interrupted attempt; reconcile before retry')
        con.execute(
            'INSERT INTO operations(operation_id,actor_slot,route,payload_hash,response_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
            (operation_id, actor, route, digest, '', 'PENDING', ts, ts),
        )
    try:
        result = fn()
    except Exception:
        # A normal application exception implies the domain transaction rolled back.
        # A hard process crash leaves PENDING, deliberately blocking blind replay.
        with db.transaction() as con:
            con.execute("DELETE FROM operations WHERE operation_id=? AND status='PENDING'", (operation_id,))
        raise
    encoded = json.dumps(result, ensure_ascii=False, separators=(',', ':'), default=str)
    with db.transaction() as con:
        con.execute(
            "UPDATE operations SET response_json=?,status='DONE',updated_at=? WHERE operation_id=? AND status='PENDING'",
            (encoded, now(), operation_id),
        )
    return result


def verify_audit_chain(db: Database) -> dict:
    rows = db.query('SELECT * FROM audit_events ORDER BY id')
    previous = ''
    for row in rows:
        before = json.loads(row['before_json']) if row['before_json'] else None
        after = json.loads(row['after_json']) if row['after_json'] else None
        payload = json.dumps(
            {
                'at': row['at'],
                'actor_slot': row['actor_slot'],
                'action': row['action'],
                'entity_type': row['entity_type'],
                'entity_id': row['entity_id'],
                'before': before,
                'after': after,
                'previous_hash': previous,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(',', ':'),
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()
        if row['previous_hash'] != previous or row['event_hash'] != digest:
            return {'ok': False, 'events': len(rows), 'broken_at_id': row['id']}
        previous = digest
    return {'ok': True, 'events': len(rows), 'head_hash': previous}


def create_fleet(db: Database, actor: int, p: dict) -> dict:
    if not p.get('client_id') or not str(p.get('name', '')).strip():
        raise ValueError('client_id and name required')
    if not db.one('SELECT id FROM clients WHERE id=? AND archived=0', (p['client_id'],)):
        raise ValueError('client not found')
    fid = uid()
    ts = now()
    rec = {
        'id': fid,
        'client_id': p['client_id'],
        'name': str(p['name']).strip(),
        'sector_or_unit': p.get('sector_or_unit'),
        'archived': 0,
        'revision': 1,
        'created_at': ts,
        'updated_at': ts,
    }
    with db.transaction() as con:
        con.execute(
            'INSERT INTO fleets(id,client_id,name,sector_or_unit,archived,revision,created_at,updated_at) VALUES(:id,:client_id,:name,:sector_or_unit,:archived,:revision,:created_at,:updated_at)',
            rec,
        )
        audit(con, actor, 'FLEET_CREATE', 'fleet', fid, None, rec)
    return rec


def transfer_vehicle(db: Database, actor: int, vehicle_id: str, p: dict) -> dict:
    new_client = p.get('client_id')
    effective_from = p.get('effective_from') or date.today().isoformat()
    if not new_client:
        raise ValueError('client_id required')
    with db.transaction() as con:
        vehicle = con.execute('SELECT * FROM vehicles WHERE id=?', (vehicle_id,)).fetchone()
        if not vehicle:
            raise KeyError('vehicle not found')
        expected = int(p.get('expected_revision', 0))
        if expected <= 0 or int(vehicle['revision']) != expected:
            raise ValueError(f"revision conflict: current={vehicle['revision']}")
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0', (new_client,)).fetchone():
            raise ValueError('target client not found')
        fleet_id = p.get('fleet_id') or None
        if fleet_id:
            fleet = con.execute('SELECT * FROM fleets WHERE id=? AND archived=0', (fleet_id,)).fetchone()
            if not fleet or fleet['client_id'] != new_client:
                raise ValueError('fleet does not belong to target client')
        before = dict(vehicle)
        open_owner = con.execute(
            'SELECT * FROM ownerships WHERE vehicle_id=? AND effective_to IS NULL ORDER BY effective_from DESC LIMIT 1',
            (vehicle_id,),
        ).fetchone()
        if not open_owner:
            raise ValueError('vehicle has no active ownership record')
        if date.fromisoformat(effective_from) < date.fromisoformat(open_owner['effective_from']):
            raise ValueError('transfer date cannot precede current ownership start date')
        con.execute(
            'UPDATE ownerships SET effective_to=? WHERE id=?',
            (effective_from, open_owner['id']),
        )
        con.execute(
            'INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',
            (uid(), vehicle_id, new_client, fleet_id, effective_from, now()),
        )
        con.execute(
            'UPDATE vehicles SET client_id=?,fleet_id=?,revision=revision+1,updated_at=? WHERE id=?',
            (new_client, fleet_id, now(), vehicle_id),
        )
        after = dict(con.execute('SELECT * FROM vehicles WHERE id=?', (vehicle_id,)).fetchone())
        audit(con, actor, 'VEHICLE_TRANSFER', 'vehicle', vehicle_id, before, after)
        return after


def update_catalog(db: Database, actor: int, catalog_id: str, p: dict) -> dict:
    with db.transaction() as con:
        row = con.execute('SELECT * FROM catalog WHERE id=?', (catalog_id,)).fetchone()
        if not row:
            raise KeyError('catalog item not found')
        expected = int(p.get('expected_revision', 0))
        if expected <= 0 or int(row['revision']) != expected:
            raise ValueError(f"revision conflict: current={row['revision']}")
        before = dict(row)
        price = row['price_cents'] if 'price' not in p else parse_money_api(p['price'])
        cost = row['cost_cents'] if 'cost' not in p else parse_money_api(p['cost'])
        values = {
            'name': p.get('name', row['name']),
            'description': p.get('description', row['description']),
            'category': p.get('category', row['category']),
            'billing_interval_months': int(p.get('billing_interval_months', row['billing_interval_months'])),
            'notes': p.get('notes', row['notes']),
            'public': 1 if p.get('public', bool(row['public'])) else 0,
            'active': 1 if p.get('active', bool(row['active'])) else 0,
            'price_cents': price,
            'cost_cents': cost,
            'id': catalog_id,
            'updated_at': now(),
        }
        con.execute(
            '''UPDATE catalog SET name=:name,description=:description,category=:category,billing_interval_months=:billing_interval_months,
               notes=:notes,public=:public,active=:active,price_cents=:price_cents,cost_cents=:cost_cents,
               revision=revision+1,updated_at=:updated_at WHERE id=:id''',
            values,
        )
        if price != row['price_cents'] or cost != row['cost_cents']:
            effective = p.get('effective_from') or date.today().isoformat()
            con.execute(
                '''INSERT INTO catalog_prices(id,catalog_id,effective_from,price_cents,cost_cents,created_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(catalog_id,effective_from) DO UPDATE SET price_cents=excluded.price_cents,cost_cents=excluded.cost_cents,created_at=excluded.created_at''',
                (uid(), catalog_id, effective, price, cost, now()),
            )
        after = dict(con.execute('SELECT * FROM catalog WHERE id=?', (catalog_id,)).fetchone())
        audit(con, actor, 'CATALOG_UPDATE', 'catalog', catalog_id, before, after)
        return after


def set_subscription_status(db: Database, actor: int, subscription_id: str, p: dict) -> dict:
    status = p.get('lifecycle_status')
    if status not in {'ACTIVE', 'PAUSED', 'CANCELLED', 'ENDED'}:
        raise ValueError('invalid lifecycle_status')
    with db.transaction() as con:
        row = con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone()
        if not row:
            raise KeyError('subscription not found')
        expected = int(p.get('expected_revision', 0))
        if expected <= 0 or int(row['revision']) != expected:
            raise ValueError(f"revision conflict: current={row['revision']}")
        before = dict(row)
        con.execute(
            'UPDATE subscriptions SET lifecycle_status=?,end_on=COALESCE(?,end_on),revision=revision+1,updated_at=? WHERE id=?',
            (status, p.get('end_on'), now(), subscription_id),
        )
        after = dict(con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone())
        audit(con, actor, 'SUBSCRIPTION_STATUS', 'subscription', subscription_id, before, after)
        return after


def add_charge_adjustment(db: Database, actor: int, charge_id: str, p: dict) -> dict:
    kind = str(p.get('kind', 'OTHER')).upper()
    if kind not in {'FEE', 'INTEREST', 'PENALTY', 'DISCOUNT', 'OTHER'}:
        raise ValueError('invalid adjustment kind')
    raw = parse_money_api(p.get('amount', '0'))
    if raw == 0:
        raise ValueError('adjustment amount cannot be zero')
    amount = -abs(raw) if kind == 'DISCOUNT' else abs(raw)
    reason = str(p.get('reason', '')).strip()
    if not reason:
        raise ValueError('adjustment reason required')
    with db.transaction() as con:
        charge = con.execute('SELECT * FROM charges WHERE id=?', (charge_id,)).fetchone()
        if not charge:
            raise KeyError('charge not found')
        resulting_total = int(charge['amount_cents']) + int(charge['adjustment_cents']) + amount
        paid = int(con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM payment_allocations WHERE charge_id=? AND active=1', (charge_id,)).fetchone()[0])
        paid += int(con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM credit_allocations WHERE charge_id=? AND active=1', (charge_id,)).fetchone()[0])
        if resulting_total < 0 or resulting_total < paid:
            raise ValueError('adjustment would reduce charge below already allocated amount')
        aid = uid()
        effective = p.get('effective_on') or date.today().isoformat()
        con.execute(
            'INSERT INTO charge_adjustments(id,charge_id,kind,amount_cents,reason,effective_on,created_at) VALUES(?,?,?,?,?,?,?)',
            (aid, charge_id, kind, amount, reason, effective, now()),
        )
        con.execute(
            'UPDATE charges SET adjustment_cents=adjustment_cents+?,revision=revision+1,updated_at=? WHERE id=?',
            (amount, now(), charge_id),
        )
        _refresh_charge_status(con, charge_id)
        rec = {'id': aid, 'charge_id': charge_id, 'kind': kind, 'amount_cents': amount, 'reason': reason, 'effective_on': effective}
        audit(con, actor, 'CHARGE_ADJUST', 'charge', charge_id, dict(charge), rec)
        return rec


def reverse_disbursement(db: Database, actor: int, disbursement_id: str) -> dict:
    with db.transaction() as con:
        row = con.execute('SELECT * FROM disbursements WHERE id=?', (disbursement_id,)).fetchone()
        if not row or row['reversed_at']:
            raise ValueError('disbursement not reversible')
        ts = now()
        con.execute('UPDATE disbursements SET reversed_at=? WHERE id=?', (ts, disbursement_id))
        exp=con.execute('SELECT * FROM expenses WHERE id=?',(row['expense_id'],)).fetchone()
        paid=int(con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE expense_id=? AND reversed_at IS NULL',(row['expense_id'],)).fetchone()[0])
        status='PAID' if paid>=int(exp['expected_amount_cents']) and int(exp['expected_amount_cents'])>0 else ('PARTIAL' if paid>0 else 'OPEN')
        con.execute('UPDATE expenses SET status=?,updated_at=? WHERE id=?',(status,now(),row['expense_id']))
        rec = {'id': disbursement_id, 'reversed_at': ts, 'expense_status': status}
        audit(con, actor, 'DISBURSEMENT_REVERSE', 'expense', row['expense_id'], dict(row), rec)
        return rec


def generate_recurring_expense(db: Database, actor: int, source_expense_id: str, competence: str) -> dict:
    with db.transaction() as con:
        src = con.execute('SELECT * FROM expenses WHERE id=?', (source_expense_id,)).fetchone()
        if not src:
            raise KeyError('source expense not found')
        recurrence = src['recurrence_id'] or src['id']
        existing = con.execute('SELECT * FROM expenses WHERE recurrence_id=? AND competence=?', (recurrence, competence)).fetchone()
        if existing:
            return dict(existing)
        due_on = None
        if src['due_on']:
            try:
                day = int(str(src['due_on']).split('-')[-1])
                due_on = due_date(competence, day).isoformat()
            except Exception:
                due_on = None
        eid = uid()
        ts = now()
        con.execute(
            '''INSERT INTO expenses(id,category,description,competence,due_on,expected_amount_cents,supplier,client_id,vehicle_id,subscription_id,catalog_id,recurrence_id,status,revision,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (
                eid, src['category'], src['description'], competence, due_on, src['expected_amount_cents'], src['supplier'],
                src['client_id'], src['vehicle_id'], src['subscription_id'], src['catalog_id'], recurrence,
                'OPEN', 1, ts, ts,
            ),
        )
        rec = dict(con.execute('SELECT * FROM expenses WHERE id=?', (eid,)).fetchone())
        audit(con, actor, 'EXPENSE_RECUR_GENERATE', 'expense', eid, None, rec)
        return rec


def dashboard_extended(db: Database) -> dict:
    def scalar(sql: str, args=()) -> int:
        row = db.one(sql, args)
        return int((row[0] if row else 0) or 0)

    today = date.today()
    upcoming = (today + timedelta(days=30)).isoformat()
    overdue_amount = scalar(
        """SELECT COALESCE(SUM(
               (c.amount_cents+c.adjustment_cents)
               -(SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa WHERE pa.charge_id=c.id AND pa.active=1)
               -(SELECT COALESCE(SUM(ca.amount_cents),0) FROM credit_allocations ca WHERE ca.charge_id=c.id AND ca.active=1)
             ),0)
             FROM charges c
             WHERE c.status<>'VOID' AND c.due_on<date('now') AND
               (c.amount_cents+c.adjustment_cents) >
               (SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa WHERE pa.charge_id=c.id AND pa.active=1)+
               (SELECT COALESCE(SUM(ca.amount_cents),0) FROM credit_allocations ca WHERE ca.charge_id=c.id AND ca.active=1)"""
    )
    upcoming_amount = scalar(
        """SELECT COALESCE(SUM(
               (c.amount_cents+c.adjustment_cents)
               -(SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa WHERE pa.charge_id=c.id AND pa.active=1)
               -(SELECT COALESCE(SUM(ca.amount_cents),0) FROM credit_allocations ca WHERE ca.charge_id=c.id AND ca.active=1)
             ),0)
             FROM charges c
             WHERE c.status<>'VOID' AND c.due_on>=date('now') AND c.due_on<=?""",
        (upcoming,),
    )
    open_credits = scalar("SELECT COALESCE(SUM(balance_cents),0) FROM credits WHERE status='OPEN'")
    current_comp = today.strftime('%Y-%m')
    comp_revenue = scalar("SELECT COALESCE(SUM(amount_cents+adjustment_cents),0) FROM charges WHERE competence=? AND status<>'VOID'", (current_comp,))
    comp_expenses = scalar("SELECT COALESCE(SUM(expected_amount_cents),0) FROM expenses WHERE competence=?", (current_comp,))
    plans = [dict(r) for r in db.query(
        """SELECT COALESCE(c.name,si.description) AS name,COUNT(DISTINCT s.id) AS subscriptions
           FROM subscription_items si JOIN subscriptions s ON s.id=si.subscription_id
           LEFT JOIN catalog c ON c.id=si.catalog_id
           WHERE s.lifecycle_status='ACTIVE' GROUP BY COALESCE(c.name,si.description)
           ORDER BY subscriptions DESC,name LIMIT 10"""
    )]
    return {
        'overdue_amount_cents': overdue_amount,
        'upcoming_30d_amount_cents': upcoming_amount,
        'open_credit_balance_cents': open_credits,
        'competence': current_comp,
        'competence_revenue_cents': comp_revenue,
        'competence_expenses_cents': comp_expenses,
        'plan_distribution': plans,
    }
