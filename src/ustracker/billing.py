"""AJ-12 — one-click subscription payment.

The operator chooses a subscription, how many months are being paid (overdue first, then
advance months), the payment date (today by default, retroactive allowed, future refused)
and optionally a discount. In ONE transaction the backend:

1. issues the missing monthly charges for the covered competences;
2. applies the discount (DISCOUNT adjustments, latest competence first);
3. records the payment and allocates it oldest competence first;
4. turns any surplus into client credit.

Nothing here changes the realized-revenue rule: the payment counts on ``paid_on`` only.
"""
from __future__ import annotations

from datetime import date

from .db import Database
from .money import due_date, parse_money_api
from .services import _charge_paid, _refresh_charge_status, audit, now, uid

MAX_MONTHS = 36
PAYMENT_METHODS = ('PIX', 'Dinheiro', 'Cartão de crédito', 'Cartão de débito', 'Boleto', 'Transferência', 'Outro')


def _comp(day: date) -> str:
    return day.strftime('%Y-%m')


def _shift(competence: str, months: int) -> str:
    year, month = (int(x) for x in competence[:7].split('-'))
    index = year * 12 + month - 1 + months
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def _monthly_amount(con, subscription_id: str) -> int:
    return int(con.execute('SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM subscription_items WHERE subscription_id=?',
                           (subscription_id,)).fetchone()[0] or 0)


def _charges_by_competence(con, subscription_id: str) -> dict[str, dict]:
    out = {}
    for row in con.execute("SELECT * FROM charges WHERE subscription_id=? AND status<>'VOID'", (subscription_id,)).fetchall():
        rec = dict(row)
        rec['open_cents'] = int(rec['amount_cents']) + int(rec['adjustment_cents']) - _charge_paid(con, rec['id'])
        out[str(rec['competence'])[:7]] = rec
    return out


def _status(con, sub, as_of: date) -> dict:
    sid = sub['id']
    monthly = _monthly_amount(con, sid)
    charges = _charges_by_competence(con, sid)
    start = str(sub['start_on'])[:7]
    current = _comp(as_of)
    # first competence that is not fully paid (gaps included: debt is always paid first)
    next_due = start
    guard = 0
    while guard < 600:
        charge = charges.get(next_due)
        if not charge or charge['status'] != 'PAID':
            break
        next_due = _shift(next_due, 1); guard += 1
    paid_through = None if next_due == start else _shift(next_due, -1)
    overdue = []
    comp = next_due
    while comp < current:
        charge = charges.get(comp)
        if not charge or charge['status'] != 'PAID':
            overdue.append(comp)
        comp = _shift(comp, 1)
    open_cents = sum(c['open_cents'] for c in charges.values() if c['status'] in ('OPEN', 'PARTIAL'))
    return {'subscription_id': sid, 'code': sub['code'], 'client_id': sub['client_id'],
            'lifecycle_status': sub['lifecycle_status'], 'due_day': int(sub['due_day']), 'start_on': sub['start_on'],
            'monthly_cents': monthly, 'paid_through': paid_through, 'next_due': next_due,
            'overdue_months': len(overdue), 'open_charges_cents': open_cents}


def subscription_payment_status(db: Database, subscription_id: str, as_of: date | None = None) -> dict:
    with db.transaction() as con:
        sub = con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone()
        if not sub:
            raise KeyError('subscription not found')
        return _status(con, sub, as_of or date.today())


def subscription_coverage(con, subscription_id: str) -> dict:
    """H-10 — what one subscription covers: target fleets (with plates), direct vehicles, value per vehicle."""
    fleets = []
    in_fleets: set[str] = set()
    for f in con.execute('''SELECT f.id,f.name,f.code FROM subscription_targets st JOIN fleets f ON f.id=st.fleet_id
                            WHERE st.subscription_id=? ORDER BY f.name''', (subscription_id,)).fetchall():
        vs = con.execute('SELECT id,plate FROM vehicles WHERE fleet_id=? AND archived=0 ORDER BY plate', (f['id'],)).fetchall()
        in_fleets.update(v['id'] for v in vs)
        fleets.append({'id': f['id'], 'name': f['name'], 'code': f['code'], 'plates': [v['plate'] for v in vs]})
    direct = con.execute('''SELECT DISTINCT v.id,v.plate FROM vehicles v WHERE v.archived=0 AND v.id IN (
                             SELECT vehicle_id FROM subscription_targets WHERE subscription_id=? AND vehicle_id IS NOT NULL
                             UNION SELECT vehicle_id FROM subscription_items WHERE subscription_id=? AND vehicle_id IS NOT NULL)
                           ORDER BY v.plate''', (subscription_id, subscription_id)).fetchall()
    extra = [v for v in direct if v['id'] not in in_fleets]
    count = len(in_fleets) + len(extra)
    monthly = _monthly_amount(con, subscription_id)
    return {'fleets': fleets, 'vehicles': [v['plate'] for v in extra], 'vehicle_count': count,
            'monthly_cents': monthly, 'per_vehicle_cents': monthly // count if count else None}


def coverage_history(db: Database, subscription_ids: list[str], *, per_vehicle: bool = False, limit: int = 36) -> list[dict]:
    """H-10 — charges (and their payment) of the subscriptions that cover a vehicle or fleet, newest first."""
    if not subscription_ids:
        return []
    marks = ','.join('?' for _ in subscription_ids)
    with db.transaction() as con:
        counts = {sid: subscription_coverage(con, sid)['vehicle_count'] for sid in subscription_ids} if per_vehicle else {}
        rows = con.execute(f'''SELECT ch.id,ch.subscription_id,s.code AS subscription_code,substr(ch.competence,1,7) AS competence,ch.due_on,
                ch.amount_cents+ch.adjustment_cents AS amount_cents,ch.status,
                (SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa JOIN payments p ON p.id=pa.payment_id
                  WHERE pa.charge_id=ch.id AND pa.active=1 AND p.reversed_at IS NULL) AS paid_cents,
                (SELECT MAX(p.paid_on) FROM payment_allocations pa JOIN payments p ON p.id=pa.payment_id
                  WHERE pa.charge_id=ch.id AND pa.active=1 AND p.reversed_at IS NULL) AS paid_on
              FROM charges ch JOIN subscriptions s ON s.id=ch.subscription_id
              WHERE ch.subscription_id IN ({marks}) AND ch.status<>'VOID'
              ORDER BY ch.competence DESC,s.code LIMIT ?''', (*subscription_ids, limit)).fetchall()
    out = []
    for r in rows:
        rec = dict(r)
        if per_vehicle:
            n = counts.get(rec['subscription_id']) or 0
            rec['share_cents'] = int(rec['amount_cents']) // n if n else None
        out.append(rec)
    return out


def client_payment_options(db: Database, client_id: str, as_of: date | None = None) -> dict:
    """Subscriptions of a client with payment status, for the one-click payment dialog."""
    today = as_of or date.today()
    with db.transaction() as con:
        client = con.execute('SELECT id,code,legal_name FROM clients WHERE id=?', (client_id,)).fetchone()
        if not client:
            raise KeyError('client not found')
        items = []
        for sub in con.execute("SELECT * FROM subscriptions WHERE client_id=? AND lifecycle_status IN ('ACTIVE','PAUSED') ORDER BY code", (client_id,)).fetchall():
            rec = _status(con, sub, today)
            rec['plans'] = [r[0] for r in con.execute('SELECT description FROM subscription_items WHERE subscription_id=? ORDER BY description', (sub['id'],)).fetchall()]
            rec['coverage'] = subscription_coverage(con, sub['id'])
            items.append(rec)
    return {'client': dict(client), 'subscriptions': items, 'methods': list(PAYMENT_METHODS), 'today': today.isoformat()}


def plan_payment(con, sub, months: int, from_competence: str | None, as_of: date) -> dict:
    status = _status(con, sub, as_of)
    first = (from_competence or status['next_due'])[:7]
    charges = _charges_by_competence(con, sub['id'])
    rows = []
    for i in range(months):
        comp = _shift(first, i)
        charge = charges.get(comp)
        if charge and charge['status'] == 'PAID':
            raise ValueError(f'competence {comp} is already paid')
        due = charge['open_cents'] if charge else status['monthly_cents']
        rows.append({'competence': comp, 'charge_id': charge['id'] if charge else None, 'due_cents': int(due)})
    return {'status': status, 'competences': rows, 'total_cents': sum(r['due_cents'] for r in rows)}


def register_subscription_payment(db: Database, actor: int, p: dict, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    sid = str(p.get('subscription_id') or '').strip()
    try:
        months = int(p.get('months') or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError('months must be a number') from exc
    if not sid:
        raise ValueError('subscription_id required')
    if months < 1 or months > MAX_MONTHS:
        raise ValueError(f'months must be between 1 and {MAX_MONTHS}')
    paid_on = str(p.get('paid_on') or today.isoformat())[:10]
    try:
        paid_day = date.fromisoformat(paid_on)
    except ValueError as exc:
        raise ValueError('paid_on must be YYYY-MM-DD') from exc
    if paid_day > today:
        raise ValueError('payment date cannot be in the future')
    discount = parse_money_api(p.get('discount') or '0')
    if discount < 0:
        raise ValueError('discount cannot be negative')
    from_competence = p.get('from_competence') or None
    if from_competence:
        due_date(str(from_competence)[:7], 1)  # validates YYYY-MM
    with db.transaction() as con:
        sub = con.execute('SELECT * FROM subscriptions WHERE id=?', (sid,)).fetchone()
        if not sub:
            raise KeyError('subscription not found')
        plan = plan_payment(con, sub, months, from_competence, today)
        if discount > plan['total_cents']:
            raise ValueError('discount exceeds amount due')
        amount = plan['total_cents'] - discount if p.get('amount') in (None, '') else parse_money_api(p['amount'])
        if amount <= 0:
            raise ValueError('payment amount must be positive')
        ts = now()
        # 1) issue missing charges
        for row in plan['competences']:
            if row['charge_id']:
                continue
            if sub['lifecycle_status'] != 'ACTIVE':
                raise ValueError('subscription is not active')
            cid = uid()
            rec = {'id': cid, 'subscription_id': sid, 'client_id': sub['client_id'], 'competence': row['competence'],
                   'due_on': due_date(row['competence'], int(sub['due_day'])).isoformat(), 'amount_cents': row['due_cents'],
                   'adjustment_cents': 0, 'status': 'OPEN', 'revision': 1, 'created_at': ts, 'updated_at': ts}
            con.execute('''INSERT INTO charges(id,subscription_id,client_id,competence,due_on,amount_cents,adjustment_cents,status,revision,created_at,updated_at)
                           VALUES(:id,:subscription_id,:client_id,:competence,:due_on,:amount_cents,:adjustment_cents,:status,:revision,:created_at,:updated_at)''', rec)
            audit(con, actor, 'CHARGE_GENERATE', 'charge', cid, None, rec)
            row['charge_id'] = cid
        pid = uid()
        # 2) discount, latest competence first
        remaining_discount = discount
        for row in reversed(plan['competences']):
            if remaining_discount <= 0:
                break
            part = min(remaining_discount, row['due_cents'])
            if part <= 0:
                continue
            con.execute('INSERT INTO charge_adjustments(id,charge_id,kind,amount_cents,reason,effective_on,created_at) VALUES(?,?,?,?,?,?,?)',
                        (uid(), row['charge_id'], 'DISCOUNT', -part, f'Desconto no pagamento {pid}', paid_on, ts))
            con.execute('UPDATE charges SET adjustment_cents=adjustment_cents-?,revision=revision+1,updated_at=? WHERE id=?', (part, ts, row['charge_id']))
            row['due_cents'] -= part
            remaining_discount -= part
        # 3) payment + allocations oldest first
        con.execute('INSERT INTO payments(id,client_id,paid_on,amount_cents,method,notes,created_at) VALUES(?,?,?,?,?,?,?)',
                    (pid, sub['client_id'], paid_on, amount, p.get('method') or None, p.get('notes') or None, ts))
        left = amount
        covered = []
        for row in plan['competences']:
            alloc = min(left, row['due_cents'])
            if alloc > 0:
                con.execute('INSERT INTO payment_allocations(id,payment_id,charge_id,amount_cents,active,created_at) VALUES(?,?,?,?,1,?)',
                            (uid(), pid, row['charge_id'], alloc, ts))
                left -= alloc
            status = _refresh_charge_status(con, row['charge_id'])
            covered.append({'competence': row['competence'], 'charge_id': row['charge_id'], 'allocated_cents': max(alloc, 0), 'status': status})
        credit_id = None
        if left > 0:
            credit_id = uid()
            con.execute('INSERT INTO credits(id,client_id,origin_payment_id,amount_cents,balance_cents,status,created_at) VALUES(?,?,?,?,?,?,?)',
                        (credit_id, sub['client_id'], pid, left, left, 'OPEN', ts))
        after = _status(con, sub, today)
        code = con.execute('SELECT code FROM payments WHERE id=?', (pid,)).fetchone()[0]
        rec = {'id': pid, 'code': code, 'client_id': sub['client_id'], 'subscription_id': sid, 'paid_on': paid_on, 'amount_cents': amount,
               'discount_cents': discount, 'months': months, 'competences': covered, 'credit_id': credit_id,
               'credit_cents': left if credit_id else 0, 'paid_through': after['paid_through'], 'next_due': after['next_due']}
        audit(con, actor, 'SUBSCRIPTION_PAYMENT', 'payment', pid, None, rec)
        return rec


def receivables_summary(db: Database, as_of: date | None = None) -> dict:
    """2.4.0 — Financeiro › Recebimentos: Total Recebido (não estornado) e Total Não Pago
    (mensalidades vencidas e não pagas das assinaturas ativas/pausadas + compras diretas em aberto)."""
    today = as_of or date.today()
    with db.transaction() as con:
        received = int(con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE reversed_at IS NULL').fetchone()[0] or 0)
        unpaid = 0
        for sub in con.execute("SELECT * FROM subscriptions WHERE lifecycle_status IN ('ACTIVE','PAUSED')").fetchall():
            st = _status(con, sub, today)
            charges = _charges_by_competence(con, sub['id'])
            comp, current = st['next_due'], _comp(today)
            while comp < current:
                charge = charges.get(comp)
                if not charge:
                    unpaid += int(st['monthly_cents'])
                elif charge['status'] != 'PAID':
                    unpaid += int(charge['open_cents'])
                comp = _shift(comp, 1)
        unpaid += int(con.execute("SELECT COALESCE(SUM(total_cents),0) FROM direct_sales WHERE status='OPEN'").fetchone()[0] or 0)
    return {'received_cents': received, 'unpaid_cents': unpaid}
