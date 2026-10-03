from __future__ import annotations

import re
from contextlib import closing
from datetime import date
from typing import Any

from .db import Database
from .services import audit, now, uid
from .vehicle_types import CATEGORY_KEYS, annotate_vehicle, breakdown_from_rows, category_label, ensure_vehicle_fits_fleet, fleet_group_label, normalize_vehicle_category, validate_fleet_group

STANDARD_VEHICLE_TYPES = ('Carro', 'Caminhão', 'Embarcação', 'Aeronave')
DEFAULT_FLEET_MAX_ACTIVE = 100


def _rowdict(row) -> dict:
    return dict(row) if row is not None else {}


def _normalize_plate(value: Any) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()


def _fleet_limit(con) -> int:
    row = con.execute("SELECT value FROM meta WHERE key='fleet_max_active'").fetchone()
    try:
        value = int(row[0]) if row else DEFAULT_FLEET_MAX_ACTIVE
    except (TypeError, ValueError):
        value = DEFAULT_FLEET_MAX_ACTIVE
    return max(1, value)


def _company_for_client(con, client_id: str, company_id: str):
    return con.execute(
        'SELECT * FROM client_companies WHERE id=? AND client_id=? AND archived=0',
        (company_id, client_id),
    ).fetchone()


def _validate_fleet_for_client(con, fleet_id: str, client_id: str, *, require_company: bool = True, vehicle_type: Any = None):
    fleet = con.execute('SELECT * FROM fleets WHERE id=? AND archived=0', (fleet_id,)).fetchone()
    if not fleet or fleet['client_id'] != client_id:
        raise ValueError('fleet does not belong to client')
    if require_company and not fleet['client_company_id']:
        raise ValueError('fleet must be linked to a client company')
    if vehicle_type is not None:
        ensure_vehicle_fits_fleet(fleet['vehicle_group'], vehicle_type)
    return fleet


def _validate_vehicle_type(value: Any) -> str:
    result = str(value or '').strip()
    if not result:
        raise ValueError('type required')
    if len(result) > 80:
        raise ValueError('type is too long')
    return result


def _validate_year(value: Any) -> int:
    try:
        year = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('year required') from exc
    if year < 1900 or year > date.today().year + 1:
        raise ValueError('invalid year')
    return year


def create_fleet(db: Database, actor: int, p: dict) -> dict:
    client_id = str(p.get('client_id') or '').strip()
    company_id = str(p.get('client_company_id') or '').strip()
    name = str(p.get('name') or '').strip()
    if not client_id or not name:
        raise ValueError('client_id and name required')
    if not company_id:
        raise ValueError('client_company_id required')
    fid = uid()
    ts = now()
    with db.transaction() as con:
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0', (client_id,)).fetchone():
            raise ValueError('client not found')
        if not _company_for_client(con, client_id, company_id):
            raise ValueError('company does not belong to client')
        rec = {
            'id': fid,
            'client_id': client_id,
            'client_company_id': company_id,
            'name': name,
            'vehicle_group': validate_fleet_group(p.get('vehicle_group')),
            'sector_or_unit': str(p.get('sector_or_unit') or '').strip() or None,
            'archived': 0,
            'revision': 1,
            'created_at': ts,
            'updated_at': ts,
        }
        con.execute(
            'INSERT INTO fleets(id,client_id,client_company_id,name,vehicle_group,sector_or_unit,archived,revision,created_at,updated_at) '
            'VALUES(:id,:client_id,:client_company_id,:name,:vehicle_group,:sector_or_unit,:archived,:revision,:created_at,:updated_at)',
            rec,
        )
        audit(con, actor, 'FLEET_CREATE', 'fleet', fid, None, rec)
        return rec


def update_fleet(db: Database, actor: int, fleet_id: str, p: dict) -> dict:
    with db.transaction() as con:
        row = con.execute('SELECT * FROM fleets WHERE id=? AND archived=0', (fleet_id,)).fetchone()
        if not row:
            raise KeyError('fleet not found')
        expected = int(p.get('expected_revision', 0))
        if expected <= 0 or int(row['revision']) != expected:
            raise ValueError(f"revision conflict: current={row['revision']}")
        before = dict(row)
        company_id = str(p.get('client_company_id', row['client_company_id']) or '').strip()
        if not company_id:
            raise ValueError('client_company_id required')
        if not _company_for_client(con, row['client_id'], company_id):
            raise ValueError('company does not belong to client')
        name = str(p.get('name', row['name']) or '').strip()
        if not name:
            raise ValueError('name required')
        sector = p.get('sector_or_unit', row['sector_or_unit'])
        group = validate_fleet_group(p.get('vehicle_group', row['vehicle_group']))
        if group != 'MIXED':
            for vehicle in con.execute('SELECT type FROM vehicles WHERE fleet_id=? AND archived=0', (fleet_id,)).fetchall():
                if normalize_vehicle_category(vehicle['type']) != group:
                    raise ValueError('fleet has vehicles of another category')
        ts = now()
        con.execute(
            'UPDATE fleets SET client_company_id=?,name=?,vehicle_group=?,sector_or_unit=?,revision=revision+1,updated_at=? WHERE id=?',
            (company_id, name, group, str(sector).strip() or None if sector is not None else None, ts, fleet_id),
        )
        after = dict(con.execute('SELECT * FROM fleets WHERE id=?', (fleet_id,)).fetchone())
        audit(con, actor, 'FLEET_UPDATE', 'fleet', fleet_id, before, after)
        return after


def create_vehicle(db: Database, actor: int, p: dict) -> dict:
    client_id = str(p.get('client_id') or '').strip()
    plate = _normalize_plate(p.get('plate'))
    vtype = _validate_vehicle_type(p.get('type'))
    brand = str(p.get('brand') or '').strip()
    model = str(p.get('model') or '').strip()
    if not client_id or not plate or not brand or not model:
        raise ValueError('client_id, plate, type, brand, model and year required')
    year = _validate_year(p.get('year'))
    fleet_id = str(p.get('fleet_id') or '').strip() or None
    contracted_on = str(p.get('contracted_on') or p.get('effective_from') or date.today().isoformat()).strip()
    review_on = str(p.get('review_on') or '').strip() or None
    try:
        date.fromisoformat(contracted_on)
        if review_on:
            date.fromisoformat(review_on)
    except ValueError as exc:
        raise ValueError('invalid mobility date') from exc
    vid = uid()
    ts = now()
    with db.transaction() as con:
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0', (client_id,)).fetchone():
            raise ValueError('client not found')
        if fleet_id:
            _validate_fleet_for_client(con, fleet_id, client_id, vehicle_type=vtype)
            active = int(con.execute('SELECT COUNT(*) FROM vehicles WHERE fleet_id=? AND archived=0', (fleet_id,)).fetchone()[0])
            limit = _fleet_limit(con)
            if active >= limit:
                raise ValueError(f'fleet active vehicle limit reached ({limit})')
        rec = {
            'id': vid,
            'client_id': client_id,
            'fleet_id': fleet_id,
            'plate': plate,
            'type': vtype,
            'brand': brand,
            'model': model,
            'year': year,
            'contracted_on': contracted_on,
            'review_on': review_on,
            'renavam': str(p.get('renavam') or '').strip() or None,
            'tracker_ref': str(p.get('tracker_ref') or '').strip() or None,
            'tracker_serial_imei': str(p.get('tracker_serial_imei') or '').strip() or None,
            'installed_on': str(p.get('installed_on') or '').strip() or None,
            'tracking_status': str(p.get('tracking_status') or 'UNTRACKED').strip() or 'UNTRACKED',
            'notes': str(p.get('notes') or '').strip() or None,
            'archived': 0,
            'revision': 1,
            'created_at': ts,
            'updated_at': ts,
        }
        con.execute(
            '''INSERT INTO vehicles(id,client_id,fleet_id,plate,type,brand,model,year,contracted_on,review_on,renavam,tracker_ref,tracker_serial_imei,installed_on,tracking_status,notes,archived,revision,created_at,updated_at)
               VALUES(:id,:client_id,:fleet_id,:plate,:type,:brand,:model,:year,:contracted_on,:review_on,:renavam,:tracker_ref,:tracker_serial_imei,:installed_on,:tracking_status,:notes,:archived,:revision,:created_at,:updated_at)''',
            rec,
        )
        con.execute(
            'INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',
            (uid(), vid, client_id, fleet_id, contracted_on, ts),
        )
        audit(con, actor, 'VEHICLE_CREATE', 'vehicle', vid, None, rec)
        return rec


def _vehicle_value_sql() -> str:
    return '''COALESCE((SELECT SUM(si.quantity*si.unit_price_cents)
                        FROM subscription_items si JOIN subscriptions s ON s.id=si.subscription_id
                        WHERE si.vehicle_id=v.id AND s.lifecycle_status='ACTIVE'),0)
              + COALESCE((SELECT SUM(di.quantity*di.unit_price_cents)
                          FROM direct_sale_items di JOIN direct_sales ds ON ds.id=di.sale_id
                          WHERE di.vehicle_id=v.id AND ds.status<>'CANCELLED'),0)'''


def _active_subscription_summaries(
    db: Database, *, vehicle_id: str | None = None, fleet_id: str | None = None, active_only: bool = True
) -> list[dict]:
    if not vehicle_id and not fleet_id:
        return []
    status_sql = "s.lifecycle_status='ACTIVE'" if active_only else '1=1'
    context_company_name = None
    if vehicle_id:
        vehicle = db.one('''SELECT v.fleet_id,cc.legal_name AS company_name FROM vehicles v
                            LEFT JOIN fleets f ON f.id=v.fleet_id
                            LEFT JOIN client_companies cc ON cc.id=f.client_company_id
                            WHERE v.id=?''', (vehicle_id,))
        vehicle_fleet_id = vehicle['fleet_id'] if vehicle else None
        context_company_name = vehicle['company_name'] if vehicle else None
        rows = db.query(f'''SELECT DISTINCT s.*,c.legal_name AS client_name,
            (SELECT cc.legal_name FROM client_companies cc WHERE cc.client_id=s.client_id AND cc.archived=0
             ORDER BY cc.is_primary DESC,cc.created_at,cc.id LIMIT 1) AS company_name
            FROM subscriptions s JOIN clients c ON c.id=s.client_id
            WHERE {status_sql} AND (
              EXISTS(SELECT 1 FROM subscription_targets st WHERE st.subscription_id=s.id AND st.vehicle_id=?)
              OR (? IS NOT NULL AND EXISTS(SELECT 1 FROM subscription_targets st WHERE st.subscription_id=s.id AND st.fleet_id=?))
              OR EXISTS(SELECT 1 FROM subscription_items si WHERE si.subscription_id=s.id AND si.vehicle_id=?)
            ) ORDER BY s.start_on DESC,s.created_at DESC''',
            (vehicle_id, vehicle_fleet_id, vehicle_fleet_id, vehicle_id))
    else:
        vehicle_fleet_id = fleet_id
        company = db.one('''SELECT cc.legal_name FROM fleets f LEFT JOIN client_companies cc
                            ON cc.id=f.client_company_id WHERE f.id=?''',(fleet_id,))
        context_company_name = company['legal_name'] if company else None
        rows = db.query(f'''SELECT DISTINCT s.*,c.legal_name AS client_name,
            (SELECT cc.legal_name FROM client_companies cc WHERE cc.client_id=s.client_id AND cc.archived=0
             ORDER BY cc.is_primary DESC,cc.created_at,cc.id LIMIT 1) AS company_name
            FROM subscriptions s JOIN clients c ON c.id=s.client_id
            WHERE {status_sql} AND (
              EXISTS(SELECT 1 FROM subscription_targets st WHERE st.subscription_id=s.id AND st.fleet_id=?)
              OR EXISTS(SELECT 1 FROM subscription_targets st JOIN vehicles v ON v.id=st.vehicle_id
                        WHERE st.subscription_id=s.id AND v.fleet_id=? AND v.archived=0)
              OR EXISTS(SELECT 1 FROM subscription_items si JOIN vehicles v ON v.id=si.vehicle_id
                        WHERE si.subscription_id=s.id AND v.fleet_id=? AND v.archived=0)
            ) ORDER BY s.start_on DESC,s.created_at DESC''', (fleet_id, fleet_id, fleet_id))
    summaries=[]
    for row in rows:
        rec=dict(row)
        items=[dict(item) for item in db.query('''SELECT si.quantity,si.unit_price_cents,si.description,c.name AS plan_name
                                                   FROM subscription_items si LEFT JOIN catalog c ON c.id=si.catalog_id
                                                   WHERE si.subscription_id=? ORDER BY si.rowid''',(rec['id'],))]
        names=[]
        for item in items:
            name=item.get('plan_name') or item.get('description')
            if name and name not in names: names.append(name)
        direct = bool(vehicle_id and (db.one('''SELECT 1 FROM subscription_targets WHERE subscription_id=? AND vehicle_id=?
                                                UNION SELECT 1 FROM subscription_items WHERE subscription_id=? AND vehicle_id=? LIMIT 1''',
                                             (rec['id'],vehicle_id,rec['id'],vehicle_id))))
        fleet_target = bool(vehicle_fleet_id and db.one(
            'SELECT 1 FROM subscription_targets WHERE subscription_id=? AND fleet_id=? LIMIT 1',
            (rec['id'],vehicle_fleet_id)))
        if direct and fleet_target: scope='DIRECT_AND_FLEET'
        elif direct: scope='DIRECT'
        elif fleet_target: scope='FLEET'
        else: scope='FLEET_VEHICLE'
        summaries.append({
            'id':rec['id'],'client_id':rec['client_id'],'client_name':rec['client_name'],
            'company_name':context_company_name or rec['company_name'],'plan_names':', '.join(names),
            'effective_total_cents':sum(int(item['quantity'])*int(item['unit_price_cents']) for item in items),
            'start_on':rec['start_on'],'lifecycle_status':rec['lifecycle_status'],'target_scope':scope,
            'code':rec.get('code'),
        })
    return summaries


def list_mobility(db: Database, *, client_id: str | None = None, fleet_id: str | None = None, plate: str | None = None,
                  company_id: str | None = None, group: str | None = None) -> dict:
    """Vehicles and fleets organized as Cliente → Empresa → Frota → Grupo (AJ-05).

    ``group`` filters by vehicle category (CAR, TRUCK, BOAT, AIRCRAFT, OTHER); fleets are kept
    when their declared group matches or when they contain matching vehicles (MIXED).
    """
    group = str(group or '').strip().upper() or None
    if group and group not in CATEGORY_KEYS:
        raise ValueError('invalid vehicle group')
    where = ['v.archived=0']
    args: list[Any] = []
    if client_id:
        where.append('v.client_id=?'); args.append(client_id)
    if fleet_id:
        where.append('v.fleet_id=?'); args.append(fleet_id)
    if company_id:
        where.append('f.client_company_id=?'); args.append(company_id)
    if plate:
        where.append('upper(v.plate) LIKE ?'); args.append('%' + _normalize_plate(plate) + '%')
    predicate = ' AND '.join(where)
    value_sql = _vehicle_value_sql()
    rows = [dict(r) for r in db.query(f'''SELECT v.*,c.legal_name AS client_name,c.code AS client_code,f.name AS fleet_name,f.code AS fleet_code,
            f.vehicle_group AS fleet_group,f.client_company_id AS company_id,cc.legal_name AS company_name,
            {value_sql} AS total_value_cents
            FROM vehicles v JOIN clients c ON c.id=v.client_id
            LEFT JOIN fleets f ON f.id=v.fleet_id
            LEFT JOIN client_companies cc ON cc.id=f.client_company_id
            WHERE {predicate} ORDER BY c.legal_name,v.plate''', tuple(args))]
    for row in rows:
        annotate_vehicle(row)
        row['subscriptions'] = _active_subscription_summaries(db, vehicle_id=row['id'])
        row['subscriptions_count'] = len(row['subscriptions'])
    if group:
        rows = [row for row in rows if row['category'] == group]
    particulars = [row for row in rows if not row.get('fleet_id')] if not company_id else []
    fleet_where = ['f.archived=0']
    fleet_args: list[Any] = []
    if client_id:
        fleet_where.append('f.client_id=?'); fleet_args.append(client_id)
    if fleet_id:
        fleet_where.append('f.id=?'); fleet_args.append(fleet_id)
    if company_id:
        fleet_where.append('f.client_company_id=?'); fleet_args.append(company_id)
    fleets = []
    for fleet in db.query(f'''SELECT f.*,c.legal_name AS client_name,c.code AS client_code,cc.legal_name AS company_name
                              FROM fleets f JOIN clients c ON c.id=f.client_id
                              LEFT JOIN client_companies cc ON cc.id=f.client_company_id
                              WHERE {' AND '.join(fleet_where)} ORDER BY c.legal_name,cc.legal_name,f.name''', tuple(fleet_args)):
        rec = dict(fleet)
        matching = [row for row in rows if row.get('fleet_id') == rec['id']]
        if (plate or group) and not matching and not (group and rec.get('vehicle_group') == group and not plate):
            continue
        all_vehicle_rows = [annotate_vehicle(dict(r)) for r in db.query(f'''SELECT v.*, {value_sql} AS total_value_cents
                                                         FROM vehicles v WHERE v.fleet_id=? AND v.archived=0 ORDER BY v.plate''', (rec['id'],))]
        rec['vehicle_group'] = rec.get('vehicle_group') or 'MIXED'
        rec['vehicle_group_label'] = fleet_group_label(rec['vehicle_group'])
        rec['vehicle_breakdown'] = breakdown_from_rows((v.get('type'), 1) for v in all_vehicle_rows)
        rec['vehicles_count'] = len(all_vehicle_rows)
        rec['contracted_on'] = min((v.get('contracted_on') for v in all_vehicle_rows if v.get('contracted_on')), default=None)
        rec['review_on'] = max((v.get('review_on') for v in all_vehicle_rows if v.get('review_on')), default=None)
        rec['total_value_cents'] = sum(int(v.get('total_value_cents') or 0) for v in all_vehicle_rows)
        rec['subscriptions'] = _active_subscription_summaries(db, fleet_id=rec['id'])
        rec['subscriptions_count'] = len(rec['subscriptions'])
        fleets.append(rec)
    with closing(db.connect()) as con:
        limit = _fleet_limit(con)
    return {'particulars': particulars, 'fleets': fleets, 'fleet_limit': limit,
            'vehicle_breakdown': breakdown_from_rows((row.get('type'), 1) for row in rows),
            'hierarchy': mobility_hierarchy(rows, fleets)}


def mobility_hierarchy(vehicles: list[dict], fleets: list[dict]) -> list[dict]:
    """Cliente → Empresa → Frota → Grupo with counts at every level. Totals are sums of children."""
    clients: dict[str, dict] = {}

    def client_node(cid, name, code):
        return clients.setdefault(cid, {'client_id': cid, 'client_name': name, 'client_code': code,
                                        'total': 0, 'particulars': 0, 'companies': {}})

    for fleet in fleets:
        node = client_node(fleet['client_id'], fleet.get('client_name'), fleet.get('client_code'))
        company_key = fleet.get('client_company_id') or ''
        company = node['companies'].setdefault(company_key, {'company_id': company_key or None,
                                                             'company_name': fleet.get('company_name') or 'Sem empresa',
                                                             'total': 0, 'fleets': []})
        company['fleets'].append({'fleet_id': fleet['id'], 'fleet_name': fleet['name'], 'fleet_code': fleet.get('code'),
                                  'vehicle_group': fleet['vehicle_group'], 'vehicle_group_label': fleet['vehicle_group_label'],
                                  'total': 0, 'groups': {}})
    fleet_nodes = {f['fleet_id']: f for n in clients.values() for c in n['companies'].values() for f in c['fleets']}
    for vehicle in vehicles:
        node = client_node(vehicle['client_id'], vehicle.get('client_name'), vehicle.get('client_code'))
        node['total'] += 1
        fleet_node = fleet_nodes.get(vehicle.get('fleet_id'))
        if not fleet_node:
            node['particulars'] += 1
            continue
        fleet_node['total'] += 1
        fleet_node['groups'][vehicle['category']] = fleet_node['groups'].get(vehicle['category'], 0) + 1
        company = next(c for c in node['companies'].values() if fleet_node in c['fleets'])
        company['total'] += 1
    result = []
    for node in clients.values():
        companies = []
        for company in node['companies'].values():
            for fleet in company['fleets']:
                fleet['groups'] = [{'key': key, 'label': category_label(key, True), 'count': fleet['groups'].get(key, 0)}
                                   for key in CATEGORY_KEYS if fleet['groups'].get(key)]
            companies.append(company)
        node['companies'] = companies
        result.append(node)
    return result


def mobility_subscription_detail(db: Database, *, vehicle_id: str | None = None, fleet_id: str | None = None) -> dict:
    """AJ-06 — full subscription detail for one vehicle or fleet (active first, others collapsed in the UI)."""
    from .projections import monthly_equivalent_sql
    if bool(vehicle_id) == bool(fleet_id):
        raise ValueError('vehicle_id or fleet_id required')
    if vehicle_id:
        target = db.one('''SELECT v.id,v.code,v.type,v.brand,v.model,v.plate,v.client_id,c.legal_name AS client_name,c.code AS client_code
                           FROM vehicles v JOIN clients c ON c.id=v.client_id WHERE v.id=?''', (vehicle_id,))
        if not target: raise KeyError('vehicle not found')
        target = annotate_vehicle(dict(target)); target['kind'] = 'VEHICLE'
    else:
        target = db.one('''SELECT f.id,f.code,f.name,f.vehicle_group,f.client_id,c.legal_name AS client_name,c.code AS client_code,
                           cc.legal_name AS company_name FROM fleets f JOIN clients c ON c.id=f.client_id
                           LEFT JOIN client_companies cc ON cc.id=f.client_company_id WHERE f.id=?''', (fleet_id,))
        if not target: raise KeyError('fleet not found')
        target = dict(target); target['kind'] = 'FLEET'; target['vehicle_group_label'] = fleet_group_label(target.get('vehicle_group'))
    competence = date.today().strftime('%Y-%m')
    items_out = []
    for summary in _active_subscription_summaries(db, vehicle_id=vehicle_id, fleet_id=fleet_id, active_only=False):
        sub = db.one('SELECT * FROM subscriptions WHERE id=?', (summary['id'],))
        plans = [dict(r) for r in db.query('''SELECT COALESCE(c.name,si.description) AS name,si.quantity,si.unit_price_cents,
                                                     si.quantity*si.unit_price_cents AS total_cents
                                              FROM subscription_items si LEFT JOIN catalog c ON c.id=si.catalog_id
                                              WHERE si.subscription_id=? ORDER BY si.rowid''', (summary['id'],))]
        monthly = db.one(f'''SELECT {monthly_equivalent_sql('s')} FROM subscriptions s JOIN subscription_items si ON si.subscription_id=s.id
                              WHERE s.id=? GROUP BY s.id,s.billing_cycle''', (summary['id'],))
        charge = db.one('''SELECT ch.amount_cents+ch.adjustment_cents AS amount_cents,ch.status,ch.due_on,
                                  (SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa WHERE pa.charge_id=ch.id AND pa.active=1)
                                  +(SELECT COALESCE(SUM(ca.amount_cents),0) FROM credit_allocations ca WHERE ca.charge_id=ch.id AND ca.active=1) AS paid_cents
                           FROM charges ch WHERE ch.subscription_id=? AND ch.status<>'VOID' AND substr(ch.competence,1,7)=?''',
                        (summary['id'], competence))
        received = db.one('''SELECT COALESCE(SUM(pa.amount_cents),0) FROM payment_allocations pa JOIN charges ch ON ch.id=pa.charge_id
                             JOIN payments p ON p.id=pa.payment_id
                             WHERE ch.subscription_id=? AND pa.active=1 AND p.reversed_at IS NULL''', (summary['id'],))
        items_out.append({**summary, 'code': sub['code'], 'due_day': sub['due_day'], 'billing_cycle': sub['billing_cycle'],
                          'end_on': sub['end_on'], 'plans': plans, 'monthly_cents': int((monthly[0] if monthly else 0) or 0),
                          'current_charge': dict(charge) if charge else None, 'competence': competence,
                          'received_cents': int((received[0] if received else 0) or 0)})
    items_out.sort(key=lambda x: (x['lifecycle_status'] != 'ACTIVE', x.get('start_on') or ''))
    active = [x for x in items_out if x['lifecycle_status'] == 'ACTIVE']
    return {'target': target, 'items': items_out, 'active_count': len(active),
            'active_monthly_cents': sum(x['monthly_cents'] for x in active)}


def fleet_profile(db: Database, fleet_id: str) -> dict:
    row = db.one('''SELECT f.*,c.legal_name AS client_name,c.code AS client_code,cc.legal_name AS company_name
                    FROM fleets f JOIN clients c ON c.id=f.client_id
                    LEFT JOIN client_companies cc ON cc.id=f.client_company_id
                    WHERE f.id=? AND f.archived=0''', (fleet_id,))
    if not row:
        raise KeyError('fleet not found')
    fleet = dict(row)
    value_sql = _vehicle_value_sql()
    vehicles = [dict(r) for r in db.query(f'''SELECT v.*,{value_sql} AS total_value_cents
                                              FROM vehicles v WHERE v.fleet_id=? AND v.archived=0 ORDER BY v.plate''', (fleet_id,))]
    for vehicle in vehicles:
        annotate_vehicle(vehicle)
        vehicle['subscriptions'] = _active_subscription_summaries(db,vehicle_id=vehicle['id'])
        vehicle['subscriptions_count'] = len(vehicle['subscriptions'])
    fleet['vehicle_group'] = fleet.get('vehicle_group') or 'MIXED'
    fleet['vehicle_group_label'] = fleet_group_label(fleet['vehicle_group'])
    media = [dict(r) for r in db.query("SELECT id,entity_type,entity_id,mime,width,height,sha256,created_at FROM media WHERE entity_type='fleet' AND entity_id=? ORDER BY created_at DESC", (fleet_id,))]
    company = dict(db.one('SELECT * FROM client_companies WHERE id=?', (fleet['client_company_id'],))) if fleet.get('client_company_id') and db.one('SELECT * FROM client_companies WHERE id=?', (fleet['client_company_id'],)) else None
    with closing(db.connect()) as con:
        limit = _fleet_limit(con)
    return {
        'fleet': fleet,
        'company': company,
        'vehicles': vehicles,
        'subscriptions': _active_subscription_summaries(db,fleet_id=fleet_id),
        'media': media,
        'summary': {
            'active_vehicles': len(vehicles),
            'vehicle_breakdown': breakdown_from_rows((v.get('type'), 1) for v in vehicles),
            'vehicle_limit': limit,
            'total_value_cents': sum(int(v.get('total_value_cents') or 0) for v in vehicles),
        },
    }


def create_transfer_case(db: Database, actor: int, vehicle_id: str, p: dict) -> dict:
    target_client = str(p.get('client_id') or '').strip()
    if not target_client:
        raise ValueError('client_id required')
    effective_from = str(p.get('effective_from') or date.today().isoformat()).strip()
    try:
        date.fromisoformat(effective_from)
    except ValueError as exc:
        raise ValueError('invalid effective_from') from exc
    with db.transaction() as con:
        vehicle = con.execute('SELECT * FROM vehicles WHERE id=? AND archived=0', (vehicle_id,)).fetchone()
        if not vehicle:
            raise KeyError('vehicle not found')
        expected = int(p.get('expected_revision', 0))
        if expected <= 0 or int(vehicle['revision']) != expected:
            raise ValueError(f"revision conflict: current={vehicle['revision']}")
        if con.execute("SELECT id FROM vehicle_transfer_cases WHERE vehicle_id=? AND status='PENDING'", (vehicle_id,)).fetchone():
            raise ValueError('vehicle already has a pending transfer')
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0', (target_client,)).fetchone():
            raise ValueError('target client not found')
        target_fleet = str(p.get('fleet_id') or '').strip() or None
        if target_fleet:
            _validate_fleet_for_client(con, target_fleet, target_client, vehicle_type=vehicle['type'])
            active = int(con.execute('SELECT COUNT(*) FROM vehicles WHERE fleet_id=? AND archived=0', (target_fleet,)).fetchone()[0])
            if active >= _fleet_limit(con):
                raise ValueError('fleet active vehicle limit reached')
        case_id = uid(); ts = now()
        rec = {
            'id': case_id,
            'vehicle_id': vehicle_id,
            'from_client_id': vehicle['client_id'],
            'from_fleet_id': vehicle['fleet_id'],
            'to_client_id': target_client,
            'to_fleet_id': target_fleet,
            'effective_from': effective_from,
            'status': 'PENDING',
            'source_revision': int(vehicle['revision']),
            'created_at': ts,
            'updated_at': ts,
            'completed_at': None,
            'cancelled_at': None,
        }
        con.execute('''INSERT INTO vehicle_transfer_cases(id,vehicle_id,from_client_id,from_fleet_id,to_client_id,to_fleet_id,effective_from,status,source_revision,created_at,updated_at,completed_at,cancelled_at)
                       VALUES(:id,:vehicle_id,:from_client_id,:from_fleet_id,:to_client_id,:to_fleet_id,:effective_from,:status,:source_revision,:created_at,:updated_at,:completed_at,:cancelled_at)''', rec)
        audit(con, actor, 'VEHICLE_TRANSFER_PENDING', 'vehicle_transfer_case', case_id, None, rec)
        return rec


def list_transfer_cases(db: Database, vehicle_id: str | None = None) -> list[dict]:
    if vehicle_id:
        rows = db.query('SELECT * FROM vehicle_transfer_cases WHERE vehicle_id=? ORDER BY created_at DESC', (vehicle_id,))
    else:
        rows = db.query('SELECT * FROM vehicle_transfer_cases ORDER BY created_at DESC')
    return [dict(r) for r in rows]


def cancel_transfer_case(db: Database, actor: int, case_id: str) -> dict:
    with db.transaction() as con:
        row = con.execute('SELECT * FROM vehicle_transfer_cases WHERE id=?', (case_id,)).fetchone()
        if not row:
            raise KeyError('transfer case not found')
        if row['status'] != 'PENDING':
            raise ValueError('transfer case is not pending')
        before = dict(row); ts = now()
        con.execute("UPDATE vehicle_transfer_cases SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=?", (ts, ts, case_id))
        after = dict(con.execute('SELECT * FROM vehicle_transfer_cases WHERE id=?', (case_id,)).fetchone())
        audit(con, actor, 'VEHICLE_TRANSFER_CANCEL', 'vehicle_transfer_case', case_id, before, after)
        return after


def complete_transfer_case(db: Database, actor: int, case_id: str) -> dict:
    with db.transaction() as con:
        case = con.execute('SELECT * FROM vehicle_transfer_cases WHERE id=?', (case_id,)).fetchone()
        if not case:
            raise KeyError('transfer case not found')
        if case['status'] != 'PENDING':
            raise ValueError('transfer case is not pending')
        vehicle = con.execute('SELECT * FROM vehicles WHERE id=? AND archived=0', (case['vehicle_id'],)).fetchone()
        if not vehicle:
            raise KeyError('vehicle not found')
        if int(vehicle['revision']) != int(case['source_revision']):
            raise ValueError(f"revision conflict: current={vehicle['revision']}")
        if not con.execute('SELECT id FROM clients WHERE id=? AND archived=0', (case['to_client_id'],)).fetchone():
            raise ValueError('target client not found')
        if case['to_fleet_id']:
            _validate_fleet_for_client(con, case['to_fleet_id'], case['to_client_id'], vehicle_type=vehicle['type'])
            active = int(con.execute('SELECT COUNT(*) FROM vehicles WHERE fleet_id=? AND archived=0', (case['to_fleet_id'],)).fetchone()[0])
            if active >= _fleet_limit(con):
                raise ValueError('fleet active vehicle limit reached')
        owner = con.execute("SELECT * FROM ownerships WHERE vehicle_id=? AND effective_to IS NULL ORDER BY effective_from DESC LIMIT 1", (vehicle['id'],)).fetchone()
        if not owner:
            raise ValueError('vehicle has no active ownership record')
        if date.fromisoformat(case['effective_from']) < date.fromisoformat(owner['effective_from']):
            raise ValueError('transfer date cannot precede current ownership start date')
        before_vehicle = dict(vehicle); before_case = dict(case); ts = now()
        con.execute('UPDATE ownerships SET effective_to=? WHERE id=?', (case['effective_from'], owner['id']))
        con.execute('INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',
                    (uid(), vehicle['id'], case['to_client_id'], case['to_fleet_id'], case['effective_from'], ts))
        con.execute('UPDATE vehicles SET client_id=?,fleet_id=?,revision=revision+1,updated_at=? WHERE id=?',
                    (case['to_client_id'], case['to_fleet_id'], ts, vehicle['id']))
        con.execute("UPDATE vehicle_transfer_cases SET status='COMPLETED',completed_at=?,updated_at=? WHERE id=?", (ts, ts, case_id))
        after_vehicle = dict(con.execute('SELECT * FROM vehicles WHERE id=?', (vehicle['id'],)).fetchone())
        after_case = dict(con.execute('SELECT * FROM vehicle_transfer_cases WHERE id=?', (case_id,)).fetchone())
        audit(con, actor, 'VEHICLE_TRANSFER_COMPLETE', 'vehicle_transfer_case', case_id, before_case, after_case)
        audit(con, actor, 'VEHICLE_TRANSFER', 'vehicle', vehicle['id'], before_vehicle, after_vehicle)
        return {'case': after_case, 'vehicle': after_vehicle}


def transfer_vehicle_compat(db: Database, actor: int, vehicle_id: str, p: dict) -> dict:
    case = create_transfer_case(db, actor, vehicle_id, p)
    return complete_transfer_case(db, actor, case['id'])['vehicle']
