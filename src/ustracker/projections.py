"""AJ-03 / AJ-01 — shared commercial and financial read projections.

Client profile, Clients list, Commercial and Visão Geral read these functions so the
same numbers appear everywhere. Rules:

* ``realized_revenue`` = non-reversed payments + PAID direct sales, with ``paid_on`` up to
  ``as_of`` (future-dated values never count as realized).
* ``contracted_active`` = monthly-equivalent value of ACTIVE subscriptions. It is a contract
  value, not revenue: a subscription without payment shows here and not in revenue.
* ``open_purchases`` = OPEN direct sales (contracted, not yet revenue).
* ``month_forecast`` = everything expected for the current competence (charges of the
  competence, active subscriptions still without a charge, and direct sales sold in the
  month). It is informative and never enters ``Resultado``.
"""
from __future__ import annotations

from datetime import date


def _next_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def monthly_equivalent_sql(alias: str = 's') -> str:
    # New subscriptions are monthly (R11). Legacy cycles are converted to a monthly equivalent.
    return (f"CASE {alias}.billing_cycle WHEN 'ANNUAL' THEN CAST(ROUND(SUM(si.quantity*si.unit_price_cents)/12.0) AS INTEGER) "
            f"WHEN 'DAILY' THEN SUM(si.quantity*si.unit_price_cents)*30 "
            f"ELSE SUM(si.quantity*si.unit_price_cents) END")


def client_projection(db, client_ids=None, as_of: date | None = None) -> dict[str, dict]:
    """Per-client projection keyed by client id."""
    today = (as_of or date.today()).isoformat()
    if client_ids is None:
        ids = [row['id'] for row in db.query('SELECT id FROM clients')]
    else:
        ids = list(client_ids)
    out = {cid: {'client_id': cid, 'active_subscriptions': 0, 'contracted_active_cents': 0,
                 'purchases_count': 0, 'open_purchases_cents': 0, 'purchases_paid_cents': 0,
                 'received_cents': 0, 'realized_revenue_cents': 0} for cid in ids}
    if not out:
        return out
    for row in db.query(f'''SELECT s.client_id,s.id,{monthly_equivalent_sql('s')} AS monthly
                            FROM subscriptions s JOIN subscription_items si ON si.subscription_id=s.id
                            WHERE s.lifecycle_status='ACTIVE' GROUP BY s.client_id,s.id,s.billing_cycle'''):
        rec = out.get(row['client_id'])
        if rec is not None:
            rec['contracted_active_cents'] += int(row['monthly'] or 0)
    for row in db.query("SELECT client_id,COUNT(*) AS n FROM subscriptions WHERE lifecycle_status='ACTIVE' GROUP BY client_id"):
        rec = out.get(row['client_id'])
        if rec is not None:
            rec['active_subscriptions'] = int(row['n'])
    for row in db.query('''SELECT client_id,COUNT(*) AS n,
            COALESCE(SUM(CASE WHEN status='OPEN' THEN total_cents ELSE 0 END),0) AS open_value,
            COALESCE(SUM(CASE WHEN status='PAID' AND paid_on<=? THEN total_cents ELSE 0 END),0) AS paid
            FROM direct_sales WHERE status<>'CANCELLED' GROUP BY client_id''', (today,)):
        rec = out.get(row['client_id'])
        if rec is not None:
            rec['purchases_count'] = int(row['n'])
            rec['open_purchases_cents'] = int(row['open_value'] or 0)
            rec['purchases_paid_cents'] = int(row['paid'] or 0)
    for row in db.query('''SELECT client_id,COALESCE(SUM(amount_cents),0) AS total FROM payments
                           WHERE reversed_at IS NULL AND paid_on<=? GROUP BY client_id''', (today,)):
        rec = out.get(row['client_id'])
        if rec is not None:
            rec['received_cents'] = int(row['total'] or 0)
    for rec in out.values():
        rec['realized_revenue_cents'] = rec['received_cents'] + rec['purchases_paid_cents']
    return out


def realized_revenue(db, start: date | None, end: date | None, as_of: date | None = None) -> int:
    """Realized revenue in [start,end) and never after ``as_of`` (default today)."""
    limit = (as_of or date.today()).isoformat()
    clauses, args = ['paid_on<=?'], [limit]
    if start:
        clauses.append('paid_on>=?'); args.append(start.isoformat())
    if end:
        clauses.append('paid_on<?'); args.append(end.isoformat())
    where = ' AND '.join(clauses)
    payments = db.one(f'SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE reversed_at IS NULL AND {where}', tuple(args))[0]
    sales = db.one(f"SELECT COALESCE(SUM(total_cents),0) FROM direct_sales WHERE status='PAID' AND {where}", tuple(args))[0]
    return int(payments or 0) + int(sales or 0)


def realized_expenses(db, start: date | None, end: date | None, as_of: date | None = None) -> int:
    limit = (as_of or date.today()).isoformat()
    clauses, args = ['reversed_at IS NULL', 'paid_on<=?'], [limit]
    if start:
        clauses.append('paid_on>=?'); args.append(start.isoformat())
    if end:
        clauses.append('paid_on<?'); args.append(end.isoformat())
    return int(db.one(f"SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE {' AND '.join(clauses)}", tuple(args))[0] or 0)


def month_forecast(db, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    month_start = today.replace(day=1)
    month_end = _next_month(month_start)
    competence = month_start.strftime('%Y-%m')
    charges = int(db.one("""SELECT COALESCE(SUM(amount_cents+adjustment_cents),0) FROM charges
                            WHERE status<>'VOID' AND substr(competence,1,7)=?""", (competence,))[0] or 0)
    uncharged = 0
    for row in db.query(f'''SELECT s.id,{monthly_equivalent_sql('s')} AS monthly
            FROM subscriptions s JOIN subscription_items si ON si.subscription_id=s.id
            WHERE s.lifecycle_status='ACTIVE' AND s.start_on<? AND (s.end_on IS NULL OR s.end_on='' OR s.end_on>=?)
              AND NOT EXISTS(SELECT 1 FROM charges ch WHERE ch.subscription_id=s.id AND ch.status<>'VOID'
                             AND substr(ch.competence,1,7)=?)
            GROUP BY s.id,s.billing_cycle''', (month_end.isoformat(), month_start.isoformat(), competence)):
        uncharged += int(row['monthly'] or 0)
    sales = int(db.one("""SELECT COALESCE(SUM(total_cents),0) FROM direct_sales
                          WHERE status IN ('OPEN','PAID') AND sold_on>=? AND sold_on<?""",
                       (month_start.isoformat(), month_end.isoformat()))[0] or 0)
    received = realized_revenue(db, month_start, month_end, today)
    total = charges + uncharged + sales
    return {'competence': competence, 'forecast_cents': total, 'charges_cents': charges,
            'uncharged_subscriptions_cents': uncharged, 'direct_sales_cents': sales,
            'received_in_month_cents': received}
