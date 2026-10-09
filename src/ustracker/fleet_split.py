"""H-20 (2.7.0) — Frota: cada veículo é uma assinatura.

A frota só agrupa os veículos. Uma assinatura que cobre mais de um veículo (frota marcada ou vários
veículos) vira uma assinatura por veículo, com o mesmo plano, vencimento e situação.

Assinaturas antigas (até a 2.6) que já têm cobranças e pagamentos são divididas com o histórico:
cada mensalidade, desconto e pagamento é repartido entre os veículos, centavo por centavo, e os
totais de cada mês não mudam. Os ids novos são derivados (uuid5) do id original e do veículo, então
a divisão dá o mesmo resultado em qualquer computador. Tudo numa transação.
"""
from __future__ import annotations

import uuid

from .db import Database

NS = uuid.UUID('6f1d1c2e-7a4b-4c55-9a51-2b7e0f20a720')


def derived_id(original_id: str, vehicle_id: str) -> str:
    return str(uuid.uuid5(NS, f'{original_id}:{vehicle_id}'))


def parts(value: int, n: int) -> list[int]:
    """Reparte ``value`` em ``n`` partes inteiras (o resto vai para as primeiras)."""
    sign = -1 if value < 0 else 1
    q, r = divmod(abs(int(value)), n)
    return [sign * (q + (1 if i < r else 0)) for i in range(n)]


def _fill(total: int, caps: list[int]) -> list[int]:
    """Reparte um valor pago entre partes com limite (cada veículo recebe até o que deve; sobra vai ao 1º)."""
    out = parts(total, len(caps))
    pool = 0
    for i, cap in enumerate(caps):
        over = max(0, out[i] - max(cap, 0))
        out[i] -= over; pool += over
    for i, cap in enumerate(caps):
        if pool <= 0:
            break
        room = max(cap, 0) - out[i]
        if room > 0:
            take = min(room, pool); out[i] += take; pool -= take
    out[0] += pool
    return out


def covered_vehicles(con, subscription_id: str) -> list[dict]:
    rows = con.execute('''SELECT DISTINCT v.id,v.plate FROM vehicles v WHERE v.archived=0 AND (
            v.id IN (SELECT vehicle_id FROM subscription_targets WHERE subscription_id=? AND vehicle_id IS NOT NULL)
         OR v.id IN (SELECT vehicle_id FROM subscription_items WHERE subscription_id=? AND vehicle_id IS NOT NULL)
         OR v.fleet_id IN (SELECT fleet_id FROM subscription_targets WHERE subscription_id=? AND fleet_id IS NOT NULL))
        ORDER BY v.plate,v.id''', (subscription_id,) * 3).fetchall()
    return [dict(r) for r in rows]


def split_subscription(con, subscription_id: str, actor: int, ts: str, *, history: bool = True, keep_vehicle_id: str | None = None) -> list[str]:
    """Divide uma assinatura que cobre vários veículos. Devolve os ids das assinaturas novas ([] se nada mudou).

    ``history=False`` (ajuste de assinatura): as cobranças já emitidas ficam inteiras na original (são histórico).
    ``keep_vehicle_id``: veículo que continua na assinatura original."""
    from .services import _hydrate_subscription, _refresh_charge_status, audit
    sub = con.execute('SELECT * FROM subscriptions WHERE id=?', (subscription_id,)).fetchone()
    if not sub:
        return []
    vehicles = covered_vehicles(con, subscription_id)
    has_fleet = con.execute('SELECT 1 FROM subscription_targets WHERE subscription_id=? AND fleet_id IS NOT NULL', (subscription_id,)).fetchone()
    if keep_vehicle_id:
        vehicles.sort(key=lambda v: v['id'] != keep_vehicle_id)
    n = len(vehicles)
    if n == 0 or (n == 1 and not has_fleet):
        return []
    before = _hydrate_subscription(con, sub)
    sub_ids = [subscription_id] + [derived_id(subscription_id, v['id']) for v in vehicles[1:]]
    # 1) assinaturas novas (mesmos dados; o código A-xx sai do gatilho)
    base = dict(sub)
    for i in range(1, n):
        rec = dict(base); rec['id'] = sub_ids[i]; rec['code'] = None; rec['revision'] = 1; rec['updated_at'] = ts
        cols = ','.join(rec); marks = ','.join('?' for _ in rec)
        con.execute(f'INSERT INTO subscriptions({cols}) VALUES({marks})', tuple(rec.values()))
    # 2) itens: mesmo plano por veículo
    for item in [dict(r) for r in con.execute('SELECT * FROM subscription_items WHERE subscription_id=? ORDER BY rowid', (subscription_id,)).fetchall()]:
        qty, unit = int(item['quantity']), int(item['unit_price_cents'])
        if qty % n == 0:
            per = [(qty // n, unit)] * n
        else:
            per = [(1, value) for value in parts(qty * unit, n)]
        for i in range(n):
            rec = dict(item); rec['vehicle_id'] = None; rec['quantity'], rec['unit_price_cents'] = per[i]
            if i == 0:
                con.execute('UPDATE subscription_items SET vehicle_id=NULL,quantity=?,unit_price_cents=? WHERE id=?', (*per[0], item['id']))
                continue
            rec['id'] = derived_id(item['id'], vehicles[i]['id']); rec['subscription_id'] = sub_ids[i]
            cols = ','.join(rec); marks = ','.join('?' for _ in rec)
            con.execute(f'INSERT INTO subscription_items({cols}) VALUES({marks})', tuple(rec.values()))
    # 3) alvo: um veículo por assinatura
    con.execute('DELETE FROM subscription_targets WHERE subscription_id=?', (subscription_id,))
    for i, v in enumerate(vehicles):
        con.execute('INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                    (derived_id(subscription_id + ':target', v['id']), sub_ids[i], v['id'], None, ts))
    # 4) histórico: cada mensalidade, desconto e pagamento repartido
    for charge in [dict(r) for r in con.execute('SELECT * FROM charges WHERE subscription_id=? ORDER BY competence', (subscription_id,)).fetchall()] if history else []:
        amounts = parts(int(charge['amount_cents']), n)
        adjusts = parts(int(charge['adjustment_cents']), n)
        charge_ids = [charge['id']] + [derived_id(charge['id'], v['id']) for v in vehicles[1:]]
        for i in range(n):
            if i == 0:
                con.execute('UPDATE charges SET amount_cents=?,adjustment_cents=?,revision=revision+1,updated_at=? WHERE id=?',
                            (amounts[0], adjusts[0], ts, charge['id']))
                continue
            rec = dict(charge); rec.update(id=charge_ids[i], subscription_id=sub_ids[i], amount_cents=amounts[i], adjustment_cents=adjusts[i],
                                           revision=1, updated_at=ts)
            cols = ','.join(rec); marks = ','.join('?' for _ in rec)
            con.execute(f'INSERT INTO charges({cols}) VALUES({marks})', tuple(rec.values()))
        for adj in [dict(r) for r in con.execute('SELECT * FROM charge_adjustments WHERE charge_id=? ORDER BY rowid', (charge['id'],)).fetchall()]:
            shares = parts(int(adj['amount_cents']), n)
            con.execute('UPDATE charge_adjustments SET amount_cents=? WHERE id=?', (shares[0], adj['id']))
            for i in range(1, n):
                if shares[i]:
                    rec = dict(adj); rec.update(id=derived_id(adj['id'], vehicles[i]['id']), charge_id=charge_ids[i], amount_cents=shares[i])
                    cols = ','.join(rec); marks = ','.join('?' for _ in rec)
                    con.execute(f'INSERT INTO charge_adjustments({cols}) VALUES({marks})', tuple(rec.values()))
        caps = [amounts[i] + adjusts[i] for i in range(n)]
        paid = sum(int(con.execute(f'SELECT COALESCE(SUM(amount_cents),0) FROM {t} WHERE charge_id=? AND active=1', (charge['id'],)).fetchone()[0])
                   for t in ('payment_allocations', 'credit_allocations'))
        targets = _fill(paid, caps)
        for table in ('payment_allocations', 'credit_allocations'):
            _move_allocations(con, table, charge['id'], charge_ids, targets)
        for cid in charge_ids:
            _refresh_charge_status(con, cid)
    after = [_hydrate_subscription(con, con.execute('SELECT * FROM subscriptions WHERE id=?', (s,)).fetchone()) for s in sub_ids]
    audit(con, actor, 'SUBSCRIPTION_SPLIT', 'subscription', subscription_id, before,
          {'vehicles': len(vehicles), 'subscriptions': [{'id': a['id'], 'code': a.get('code')} for a in after]})
    return sub_ids[1:]


def _move_allocations(con, table: str, charge_id: str, charge_ids: list[str], targets: list[int]) -> None:
    """Reparte as alocações ativas de ``charge_id`` entre as cobranças por veículo até o alvo de cada uma."""
    rows = [dict(r) for r in con.execute(f'SELECT * FROM {table} WHERE charge_id=? AND active=1 ORDER BY rowid', (charge_id,)).fetchall()]
    for row in rows:
        left = int(row['amount_cents'])
        shares: list[tuple[int, int]] = []
        for i in range(len(charge_ids)):
            take = min(left, max(targets[i], 0))
            if take > 0:
                shares.append((i, take)); targets[i] -= take; left -= take
        if left > 0:
            shares.append((0, left)); targets[0] -= left
        merged: dict[int, int] = {}
        for i, amount in shares:
            merged[i] = merged.get(i, 0) + amount
        keep_i = 0 if 0 in merged else min(merged)
        con.execute(f'UPDATE {table} SET charge_id=?,amount_cents=? WHERE id=?', (charge_ids[keep_i], merged[keep_i], row['id']))
        for i, amount in merged.items():
            if i == keep_i:
                continue
            rec = dict(row); rec.update(id=derived_id(row['id'], charge_ids[i]), charge_id=charge_ids[i], amount_cents=amount)
            cols = ','.join(rec); marks = ','.join('?' for _ in rec)
            con.execute(f'INSERT INTO {table}({cols}) VALUES({marks})', tuple(rec.values()))


def pending(db: Database) -> list[str]:
    """Assinaturas que ainda cobrem mais de um veículo (ou uma frota)."""
    rows = db.query('''SELECT DISTINCT s.id FROM subscriptions s WHERE
            EXISTS(SELECT 1 FROM subscription_targets st WHERE st.subscription_id=s.id AND st.fleet_id IS NOT NULL)
         OR (SELECT COUNT(*) FROM subscription_targets st WHERE st.subscription_id=s.id AND st.vehicle_id IS NOT NULL)>1
         ORDER BY s.created_at,s.id''')
    return [r[0] for r in rows]


def split_all(db: Database, actor: int) -> dict:
    """Divide todas as assinaturas antigas de frota (idempotente: a 2ª vez não faz nada)."""
    from .services import now
    ids = pending(db)
    if not ids:
        return {'split': 0, 'created': 0}
    split = created = 0
    ts = now()
    with db.transaction() as con:
        for sid in ids:
            new = split_subscription(con, sid, actor, ts)
            split += 1 if new else 0
            created += len(new)
    return {'split': split, 'created': created}
