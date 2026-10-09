"""AJ-10 — adjust an existing subscription (plan, quantity, monthly value, due day, targets).

Changes affect only charges issued from now on; charges already issued keep their value
(they are history). Everything happens in one transaction with optimistic revision.
"""
from __future__ import annotations

from .db import Database
from .money import parse_money_api
from .services import _hydrate_subscription, audit, now, uid


def amend_subscription(db: Database, actor: int, subscription_id: str, p: dict) -> dict:
    with db.transaction() as con:
        row = con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone()
        if not row:
            raise KeyError('subscription not found')
        expected = int(p.get('expected_revision') or 0)
        if expected <= 0 or int(row['revision']) != expected:
            raise ValueError(f"revision conflict: current={row['revision']}")
        if row['lifecycle_status'] in ('CANCELLED', 'ENDED'):
            raise ValueError('subscription is closed')
        before = _hydrate_subscription(con, row)
        client_id = row['client_id']
        due_day = int(p.get('due_day') or row['due_day'])
        if due_day < 1 or due_day > 31:
            raise ValueError('due_day must be between 1 and 31')
        ts = now()
        if 'items' in p:
            items = p.get('items') or []
            if not items:
                raise ValueError('items required')
            normalized = []
            for item in items:
                catalog_id = str(item.get('catalog_id') or '').strip()
                catalog = con.execute("SELECT * FROM catalog WHERE id=? AND upper(category)='MENSAL' AND (active=1 OR id IN (SELECT catalog_id FROM subscription_items WHERE subscription_id=?))",
                                      (catalog_id, subscription_id)).fetchone()
                if not catalog:
                    raise ValueError('active monthly plan not found')
                quantity = int(item.get('quantity') or 1)
                if quantity <= 0:
                    raise ValueError('quantity must be positive')
                unit = parse_money_api(item['unit_price']) if item.get('unit_price') not in (None, '') else int(catalog['price_cents'])
                if unit < 0:
                    raise ValueError('unit price cannot be negative')
                normalized.append((uid(), subscription_id, catalog_id, None, str(catalog['name']).strip(), quantity, unit))
            con.execute('DELETE FROM subscription_items WHERE subscription_id=?', (subscription_id,))
            con.executemany('INSERT INTO subscription_items(id,subscription_id,catalog_id,vehicle_id,description,quantity,unit_price_cents) VALUES(?,?,?,?,?,?,?)', normalized)
        if 'target_vehicle_ids' in p or 'target_fleet_ids' in p:
            vehicle_ids = [str(v).strip() for v in (p.get('target_vehicle_ids') or []) if str(v).strip()]
            fleet_ids = [str(v).strip() for v in (p.get('target_fleet_ids') or []) if str(v).strip()]
            if len(set(vehicle_ids)) != len(vehicle_ids) or len(set(fleet_ids)) != len(fleet_ids):
                raise ValueError('duplicate target')
            for vehicle_id in vehicle_ids:
                v = con.execute('SELECT client_id FROM vehicles WHERE id=? AND archived=0', (vehicle_id,)).fetchone()
                if not v or v['client_id'] != client_id:
                    raise ValueError('vehicle does not belong to client')
            for fleet_id in fleet_ids:
                f = con.execute('SELECT client_id FROM fleets WHERE id=? AND archived=0', (fleet_id,)).fetchone()
                if not f or f['client_id'] != client_id:
                    raise ValueError('fleet does not belong to client')
            con.execute('DELETE FROM subscription_targets WHERE subscription_id=?', (subscription_id,))
            for vehicle_id in vehicle_ids:
                con.execute('INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)', (uid(), subscription_id, vehicle_id, None, ts))
            for fleet_id in fleet_ids:
                con.execute('INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)', (uid(), subscription_id, None, fleet_id, ts))
        con.execute('UPDATE subscriptions SET due_day=?,revision=revision+1,updated_at=? WHERE id=?', (due_day, ts, subscription_id))
        after = _hydrate_subscription(con, con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone())
        audit(con, actor, 'SUBSCRIPTION_AMEND', 'subscription', subscription_id, before, after)
        from .fleet_split import split_subscription  # 2.7.0: uma assinatura por veículo
        keep = next((t['vehicle_id'] for t in before.get('targets', []) if t.get('vehicle_id')), None)
        extra = split_subscription(con, subscription_id, actor, ts, history=False, keep_vehicle_id=keep)
        if extra:
            after = _hydrate_subscription(con, con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone())
            after['group_ids'] = [subscription_id, *extra]
        return after
