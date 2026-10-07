"""AJ-13 — company expenses (UStracker's own costs), simple and modular.

* An expense has a fixed category, a description, a value, a date and a **Repetição**:
  ``MONTHLY`` (Mensal), ``ANNUAL`` (Anual) or ``ONCE`` (Única). "Competência" is derived from
  the date and no longer typed by the operator.
* A recurring expense is a *template* (``recurrence_id = id``, ``repeat_active = 1``). Its
  next occurrences are generated, idempotently, up to the current month (unique index on
  ``recurrence_id + competence``).
* Every expense enters the final cost when paid (disbursement); "Pagar" is one click.
* A one-off expense (e.g. a tracker/chip bought by the company) can later be converted into
  a direct sale to a client: the cost stays a cost, the sale becomes revenue.
"""
from __future__ import annotations

from datetime import date

from .db import Database
from .money import due_date, parse_money_api
from .services import audit, now, uid

EXPENSE_CATEGORIES = ('Insumos', 'Equipamentos', 'Mensalidades e serviços', 'Pessoal', 'Impostos e taxas',
                      'Marketing', 'Infraestrutura', 'Outros')
REPEAT_LABELS = {'MONTHLY': 'Mensal', 'ANNUAL': 'Anual', 'ONCE': 'Única'}
LEGACY_CATEGORY_LABELS = {'FISCAL': 'Impostos e taxas'}


def _shift(competence: str, months: int) -> str:
    year, month = (int(x) for x in competence[:7].split('-'))
    index = year * 12 + month - 1 + months
    return f'{index // 12:04d}-{index % 12 + 1:02d}'


def _paid(con, expense_id: str) -> int:
    return int(con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM disbursements WHERE expense_id=? AND reversed_at IS NULL',
                           (expense_id,)).fetchone()[0] or 0)


def _insert(con, actor: int, rec: dict, action: str) -> dict:
    con.execute('''INSERT INTO expenses(id,category,description,competence,due_on,expected_amount_cents,supplier,client_id,vehicle_id,
                   subscription_id,catalog_id,recurrence_id,status,revision,created_at,updated_at,repeat,repeat_active)
                   VALUES(:id,:category,:description,:competence,:due_on,:expected_amount_cents,:supplier,:client_id,:vehicle_id,
                   :subscription_id,:catalog_id,:recurrence_id,:status,:revision,:created_at,:updated_at,:repeat,:repeat_active)''', rec)
    audit(con, actor, action, 'expense', rec['id'], None, rec)
    return rec


def _disburse(con, actor: int, exp, paid_on: str, amount: int | None = None) -> dict:
    paid = _paid(con, exp['id'])
    value = int(exp['expected_amount_cents']) - paid if amount is None else amount
    if value <= 0 or paid + value > int(exp['expected_amount_cents']):
        raise ValueError('disbursement exceeds expense')
    did = uid()
    con.execute('INSERT INTO disbursements(id,expense_id,paid_on,amount_cents,created_at) VALUES(?,?,?,?,?)', (did, exp['id'], paid_on, value, now()))
    status = 'PAID' if paid + value == int(exp['expected_amount_cents']) else 'PARTIAL'
    con.execute('UPDATE expenses SET status=?,revision=revision+1,updated_at=? WHERE id=?', (status, now(), exp['id']))
    rec = {'id': did, 'expense_id': exp['id'], 'paid_on': paid_on, 'amount_cents': value, 'expense_status': status}
    audit(con, actor, 'DISBURSEMENT_CREATE', 'expense', exp['id'], None, rec)
    return rec


def create_company_expense(db: Database, actor: int, p: dict, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    category = str(p.get('category') or '').strip()
    if category not in EXPENSE_CATEGORIES:
        raise ValueError('invalid expense category')
    description = str(p.get('description') or '').strip()
    if not description:
        raise ValueError('description required')
    repeat = str(p.get('repeat') or 'ONCE').upper()
    if repeat not in REPEAT_LABELS:
        raise ValueError('invalid expense repeat')
    amount = parse_money_api(p.get('amount') or '0')
    if amount <= 0:
        raise ValueError('expense amount must be positive')
    day = str(p.get('date') or today.isoformat())[:10]
    date.fromisoformat(day)
    paid = str(p.get('paid', '')).lower() in ('1', 'true', 'on', 'yes')
    if paid and date.fromisoformat(day) > today:
        raise ValueError('a future expense cannot be marked as paid')
    eid = uid(); ts = now()
    rec = {'id': eid, 'category': category, 'description': description, 'competence': day[:7], 'due_on': day,
           'expected_amount_cents': amount, 'supplier': (str(p.get('supplier') or '').strip() or None),
           'client_id': None, 'vehicle_id': None, 'subscription_id': None, 'catalog_id': None,
           'recurrence_id': eid if repeat != 'ONCE' else None, 'status': 'OPEN', 'revision': 1, 'created_at': ts, 'updated_at': ts,
           'repeat': repeat, 'repeat_active': 1 if repeat != 'ONCE' else 0}
    with db.transaction() as con:
        _insert(con, actor, rec, 'EXPENSE_CREATE')
        if paid:
            rec['disbursement'] = _disburse(con, actor, rec, day)
            rec['status'] = rec['disbursement']['expense_status']
        _generate(con, actor, today, only=eid)
    return rec


def _due_occurrences(con, today: date, only: str | None = None):
    current = today.strftime('%Y-%m')
    sql = "SELECT * FROM expenses WHERE repeat IN ('MONTHLY','ANNUAL') AND repeat_active=1 AND recurrence_id=id"
    args: tuple = ()
    if only:
        sql += ' AND id=?'; args = (only,)
    for tpl in con.execute(sql, args).fetchall():
        step = 1 if tpl['repeat'] == 'MONTHLY' else 12
        comp = _shift(tpl['competence'], step)
        guard = 0
        while comp <= current and guard < 240:
            if not con.execute('SELECT 1 FROM expenses WHERE recurrence_id=? AND competence=?', (tpl['id'], comp)).fetchone():
                yield tpl, comp
            comp = _shift(comp, step); guard += 1


def _generate(con, actor: int, today: date, only: str | None = None) -> list[dict]:
    created = []
    for tpl, comp in list(_due_occurrences(con, today, only)):
        try:
            day = int(str(tpl['due_on'] or '01')[-2:])
        except ValueError:
            day = 1
        ts = now()
        rec = {'id': uid(), 'category': tpl['category'], 'description': tpl['description'], 'competence': comp,
               'due_on': due_date(comp, day).isoformat(), 'expected_amount_cents': tpl['expected_amount_cents'], 'supplier': tpl['supplier'],
               'client_id': tpl['client_id'], 'vehicle_id': tpl['vehicle_id'], 'subscription_id': tpl['subscription_id'],
               'catalog_id': tpl['catalog_id'], 'recurrence_id': tpl['id'], 'status': 'OPEN', 'revision': 1, 'created_at': ts,
               'updated_at': ts, 'repeat': tpl['repeat'], 'repeat_active': 0}
        created.append(_insert(con, actor, rec, 'EXPENSE_RECUR_GENERATE'))
    return created


def pending_recurring_count(db: Database, as_of: date | None = None) -> int:
    with db.transaction() as con:
        return sum(1 for _ in _due_occurrences(con, as_of or date.today()))


def run_recurring_expenses(db: Database, actor: int, as_of: date | None = None) -> dict:
    with db.transaction() as con:
        created = _generate(con, actor, as_of or date.today())
    return {'created': len(created), 'items': created}


def pay_expense(db: Database, actor: int, expense_id: str, p: dict | None = None, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    p = p or {}
    paid_on = str(p.get('paid_on') or today.isoformat())[:10]
    if date.fromisoformat(paid_on) > today:
        raise ValueError('payment date cannot be in the future')
    amount = parse_money_api(p['amount']) if p.get('amount') not in (None, '') else None
    with db.transaction() as con:
        exp = con.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
        if not exp:
            raise KeyError('expense not found')
        return _disburse(con, actor, exp, paid_on, amount)


def stop_recurring_expense(db: Database, actor: int, expense_id: str) -> dict:
    with db.transaction() as con:
        exp = con.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
        if not exp:
            raise KeyError('expense not found')
        template_id = exp['recurrence_id'] or exp['id']
        con.execute('UPDATE expenses SET repeat_active=0,revision=revision+1,updated_at=? WHERE id=?', (now(), template_id))
        rec = {'id': template_id, 'repeat_active': 0}
        audit(con, actor, 'EXPENSE_RECUR_STOP', 'expense', template_id, dict(exp), rec)
        return rec


def delete_expense(db: Database, actor: int, expense_id: str) -> dict:
    with db.transaction() as con:
        exp = con.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
        if not exp:
            raise KeyError('expense not found')
        if con.execute('SELECT 1 FROM fiscal_obligations WHERE expense_id=?', (expense_id,)).fetchone():
            raise ValueError('expense linked to fiscal obligation cannot be deleted')
        if exp['converted_sale_id']:
            raise ValueError('expense converted to sale cannot be deleted')
        if exp['recurrence_id'] == exp['id'] and con.execute('SELECT 1 FROM expenses WHERE recurrence_id=? AND id<>?', (expense_id, expense_id)).fetchone():
            raise ValueError('recurring expense has occurrences; stop the repetition instead')
        from .trash import put as trash_put
        # 2.4.0: a paid expense can be deleted too; its payments go to the Lixeira with it (and come back on restore)
        payments = [dict(r) for r in con.execute('SELECT * FROM disbursements WHERE expense_id=?', (expense_id,)).fetchall()]
        trash_put(con, actor, 'expense', expense_id, f"{exp['category']} · {exp['description']}", {'row': dict(exp), 'disbursements': payments})
        con.execute('DELETE FROM disbursements WHERE expense_id=?', (expense_id,))
        con.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
        audit(con, actor, 'EXPENSE_DELETE', 'expense', expense_id, dict(exp), None)
        return {'id': expense_id, 'deleted': True}


def update_expense(db: Database, actor: int, expense_id: str, p: dict) -> dict:
    """2.4.0 — fix a typed expense (paid or not): description, category, value, date, supplier. Status follows the value."""
    with db.transaction() as con:
        exp = con.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
        if not exp:
            raise KeyError('expense not found')
        before = dict(exp)
        rec = {'description': exp['description'], 'category': exp['category'], 'expected_amount_cents': int(exp['expected_amount_cents']),
               'due_on': exp['due_on'], 'competence': exp['competence'], 'supplier': exp['supplier']}
        if 'description' in p:
            rec['description'] = str(p.get('description') or '').strip()
            if not rec['description']:
                raise ValueError('description required')
        if 'category' in p:
            category = str(p.get('category') or '').strip()
            if category not in EXPENSE_CATEGORIES:
                raise ValueError('invalid expense category')
            rec['category'] = category
        if p.get('amount') not in (None, ''):
            rec['expected_amount_cents'] = parse_money_api(p['amount'])
            if rec['expected_amount_cents'] <= 0:
                raise ValueError('expense amount must be positive')
        if p.get('date'):
            day = str(p['date'])[:10]
            date.fromisoformat(day)
            rec['due_on'], rec['competence'] = day, day[:7]
        if 'supplier' in p:
            rec['supplier'] = str(p.get('supplier') or '').strip() or None
        paid = _paid(con, expense_id)
        if paid > rec['expected_amount_cents']:
            raise ValueError('expense value is lower than what was already paid')
        rec['status'] = 'PAID' if paid == rec['expected_amount_cents'] else 'PARTIAL' if paid else 'OPEN'
        con.execute('''UPDATE expenses SET description=?,category=?,expected_amount_cents=?,due_on=?,competence=?,supplier=?,status=?,
                       revision=revision+1,updated_at=? WHERE id=?''',
                    (rec['description'], rec['category'], rec['expected_amount_cents'], rec['due_on'], rec['competence'], rec['supplier'],
                     rec['status'], now(), expense_id))
        audit(con, actor, 'EXPENSE_UPDATE', 'expense', expense_id, before, rec)
        return {'id': expense_id, **rec, 'paid_cents': paid}


def convert_expense_to_sale(db: Database, actor: int, expense_id: str, p: dict, as_of: date | None = None) -> dict:
    """One-off expense → direct sale to a client (same transaction)."""
    today = as_of or date.today()
    client_id = str(p.get('client_id') or '').strip()
    if not client_id:
        raise ValueError('client_id required')
    sold_on = str(p.get('sold_on') or today.isoformat())[:10]
    date.fromisoformat(sold_on)
    with db.transaction() as con:
        exp = con.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone()
        if not exp:
            raise KeyError('expense not found')
        if exp['repeat'] != 'ONCE':
            raise ValueError('only one-off expenses can become a direct sale')
        if exp['converted_sale_id']:
            raise ValueError('expense already converted')
        if not con.execute('SELECT 1 FROM clients WHERE id=?', (client_id,)).fetchone():
            raise ValueError('client not found')
        vehicle_id = p.get('vehicle_id') or None
        if vehicle_id:
            v = con.execute('SELECT client_id FROM vehicles WHERE id=? AND archived=0', (vehicle_id,)).fetchone()
            if not v or v['client_id'] != client_id:
                raise ValueError('vehicle does not belong to client')
        price = parse_money_api(p['price']) if p.get('price') not in (None, '') else int(exp['expected_amount_cents'])
        if price < 0:
            raise ValueError('unit_price cannot be negative')
        sale_id = uid(); ts = now()
        sale = {'id': sale_id, 'client_id': client_id, 'sold_on': sold_on, 'status': 'OPEN', 'paid_on': None, 'total_cents': price,
                'notes': f"Convertida da despesa: {exp['description']}", 'revision': 1, 'created_at': ts, 'updated_at': ts}
        con.execute('''INSERT INTO direct_sales(id,client_id,sold_on,status,paid_on,total_cents,notes,revision,created_at,updated_at)
                       VALUES(:id,:client_id,:sold_on,:status,:paid_on,:total_cents,:notes,:revision,:created_at,:updated_at)''', sale)
        item = {'id': uid(), 'sale_id': sale_id, 'catalog_id': None, 'vehicle_id': vehicle_id, 'description': exp['description'],
                'quantity': 1, 'unit_price_cents': price}
        con.execute('''INSERT INTO direct_sale_items(id,sale_id,catalog_id,vehicle_id,description,quantity,unit_price_cents)
                       VALUES(:id,:sale_id,:catalog_id,:vehicle_id,:description,:quantity,:unit_price_cents)''', item)
        con.execute('UPDATE expenses SET converted_sale_id=?,client_id=?,vehicle_id=COALESCE(?,vehicle_id),revision=revision+1,updated_at=? WHERE id=?',
                    (sale_id, client_id, vehicle_id, ts, expense_id))
        sale['code'] = con.execute('SELECT code FROM direct_sales WHERE id=?', (sale_id,)).fetchone()[0]
        audit(con, actor, 'DIRECT_SALE_CREATE', 'direct_sale', sale_id, None, {**sale, 'items': [item], 'from_expense': expense_id})
        audit(con, actor, 'EXPENSE_CONVERT_SALE', 'expense', expense_id, dict(exp), {'converted_sale_id': sale_id})
        return {**sale, 'items': [item], 'expense_id': expense_id}


def expense_rows(db: Database) -> list[dict]:
    rows = []
    for r in db.query('''SELECT e.*,COALESCE((SELECT SUM(amount_cents) FROM disbursements d WHERE d.expense_id=e.id AND d.reversed_at IS NULL),0) AS paid_cents,
                         ds.code AS sale_code,c.legal_name AS client_name
                         FROM expenses e LEFT JOIN direct_sales ds ON ds.id=e.converted_sale_id LEFT JOIN clients c ON c.id=e.client_id
                         ORDER BY COALESCE(e.due_on,e.competence) DESC,e.created_at DESC'''):
        rec = dict(r)
        rec['category_label'] = LEGACY_CATEGORY_LABELS.get(rec['category'], rec['category'])
        rec['repeat_label'] = REPEAT_LABELS.get(rec.get('repeat') or 'ONCE', 'Única')
        rec['is_template'] = rec['recurrence_id'] == rec['id']
        rec['open_cents'] = int(rec['expected_amount_cents']) - int(rec['paid_cents'])
        rows.append(rec)
    return rows
