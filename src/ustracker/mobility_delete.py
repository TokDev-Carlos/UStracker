"""V-01 / V-02 — exclusão de veículos e frotas (sem órfãos) e aviso de placa já cadastrada.

* Excluir um veículo ou uma frota manda o item para a Lixeira (14 dias). Os registros ficam
  arquivados (histórico financeiro preservado); restaurar desarquiva.
* Excluir uma frota: os veículos dela viram "Particular" do mesmo cliente (mode='detach') ou são
  excluídos junto (mode='with_vehicles').
* Arquivar um cliente leva junto as frotas e os veículos dele (nada fica órfão).
* Itens ligados a assinatura ativa/pausada não podem ser excluídos: a mensagem diz qual.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .db import Database
from .services import audit, now, uid

ACTIVE_SUB = "('ACTIVE','PAUSED')"


def normalize_plate(value: Any) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()


class PlateExists(ValueError):
    """A plate is already registered on an active vehicle."""

    def __init__(self, info: dict):
        owner = info.get('client_name') or 'outro cliente'
        super().__init__(f"Placa {info.get('plate')} já cadastrada ({owner})")
        self.info = info


def plate_owner(con, plate: Any, exclude_vehicle_id: str | None = None) -> dict | None:
    norm = normalize_plate(plate)
    if not norm:
        return None
    row = con.execute('''SELECT v.id,v.plate,v.type,v.brand,v.model,v.year,v.code,v.client_id,v.fleet_id,
                                c.legal_name AS client_name,c.code AS client_code,f.name AS fleet_name,
                                (SELECT m.id FROM media m WHERE m.entity_type='vehicle' AND m.entity_id=v.id
                                 ORDER BY m.created_at DESC LIMIT 1) AS media_id
                         FROM vehicles v JOIN clients c ON c.id=v.client_id LEFT JOIN fleets f ON f.id=v.fleet_id
                         WHERE v.archived=0 AND upper(v.plate)=? AND (? IS NULL OR v.id<>?)''',
                      (norm, exclude_vehicle_id, exclude_vehicle_id)).fetchone()
    return dict(row) if row else None


def check_plate(db: Database, plate: Any) -> dict:
    with db.transaction() as con:
        info = plate_owner(con, plate)
    return {'plate': normalize_plate(plate), 'exists': bool(info), 'vehicle': info}


def _subs_blocking(con, *, vehicle_ids: list[str] = (), fleet_ids: list[str] = ()) -> list[str]:
    codes: set[str] = set()
    for vid in vehicle_ids:
        for r in con.execute(f'''SELECT DISTINCT s.code FROM subscriptions s
                                 WHERE s.lifecycle_status IN {ACTIVE_SUB} AND (
                                   EXISTS(SELECT 1 FROM subscription_targets t WHERE t.subscription_id=s.id AND t.vehicle_id=?)
                                   OR EXISTS(SELECT 1 FROM subscription_items i WHERE i.subscription_id=s.id AND i.vehicle_id=?))''', (vid, vid)):
            codes.add(r[0] or 'assinatura')
    for fid in fleet_ids:
        for r in con.execute(f'''SELECT DISTINCT s.code FROM subscriptions s JOIN subscription_targets t ON t.subscription_id=s.id
                                 WHERE s.lifecycle_status IN {ACTIVE_SUB} AND t.fleet_id=?''', (fid,)):
            codes.add(r[0] or 'assinatura')
    return sorted(codes)


def _archive_vehicle_rows(con, vehicle_ids: list[str], ts: str):
    today = ts[:10]
    for vid in vehicle_ids:
        con.execute('UPDATE vehicles SET archived=1,revision=revision+1,updated_at=? WHERE id=?', (ts, vid))
        con.execute('UPDATE ownerships SET effective_to=? WHERE vehicle_id=? AND effective_to IS NULL', (today, vid))


def _vehicle_label(row) -> str:
    return ' '.join(str(x) for x in (row['plate'], row['brand'], row['model']) if x)


def delete_vehicle(db: Database, actor: int, vehicle_id: str) -> dict:
    from .trash import put as trash_put
    ts = now()
    with db.transaction() as con:
        row = con.execute('SELECT * FROM vehicles WHERE id=? AND archived=0', (vehicle_id,)).fetchone()
        if not row:
            raise KeyError('vehicle not found')
        blocking = _subs_blocking(con, vehicle_ids=[vehicle_id])
        if blocking:
            raise ValueError('Veículo está em assinatura ativa (' + ', '.join(blocking) + '). Encerre ou retire o veículo da assinatura antes de excluir.')
        before = dict(row)
        _archive_vehicle_rows(con, [vehicle_id], ts)
        trash_id = trash_put(con, actor, 'vehicle', vehicle_id, _vehicle_label(row), {'vehicles': [vehicle_id], 'fleet_id': row['fleet_id']})
        audit(con, actor, 'VEHICLE_DELETE', 'vehicle', vehicle_id, before, {'archived': 1})
    return {'id': vehicle_id, 'deleted': True, 'trash_id': trash_id}


def delete_fleet(db: Database, actor: int, fleet_id: str, mode: str = 'detach') -> dict:
    from .trash import put as trash_put
    mode = (mode or 'detach').strip().lower()
    if mode not in ('detach', 'with_vehicles'):
        raise ValueError('mode must be detach or with_vehicles')
    ts = now()
    with db.transaction() as con:
        fleet = con.execute('SELECT * FROM fleets WHERE id=? AND archived=0', (fleet_id,)).fetchone()
        if not fleet:
            raise KeyError('fleet not found')
        vehicle_ids = [r[0] for r in con.execute('SELECT id FROM vehicles WHERE fleet_id=? AND archived=0', (fleet_id,))]
        blocking = _subs_blocking(con, fleet_ids=[fleet_id], vehicle_ids=vehicle_ids if mode == 'with_vehicles' else [])
        if blocking:
            raise ValueError('Frota está em assinatura ativa (' + ', '.join(blocking) + '). Encerre a assinatura antes de excluir.')
        detached: list[str] = []
        archived: list[str] = []
        if mode == 'with_vehicles':
            _archive_vehicle_rows(con, vehicle_ids, ts)
            archived = vehicle_ids
        else:
            for vid in vehicle_ids:
                con.execute('UPDATE vehicles SET fleet_id=NULL,revision=revision+1,updated_at=? WHERE id=?', (ts, vid))
                con.execute('UPDATE ownerships SET effective_to=? WHERE vehicle_id=? AND effective_to IS NULL', (ts[:10], vid))
                con.execute('INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',
                            (uid(), vid, fleet['client_id'], None, ts[:10], ts))
            detached = vehicle_ids
        con.execute('UPDATE fleets SET archived=1,revision=revision+1,updated_at=? WHERE id=?', (ts, fleet_id))
        trash_id = trash_put(con, actor, 'fleet', fleet_id, str(fleet['name']),
                  {'fleets': [fleet_id], 'vehicles': archived, 'detached': detached})
        audit(con, actor, 'FLEET_DELETE', 'fleet', fleet_id, dict(fleet), {'archived': 1, 'mode': mode})
    return {'id': fleet_id, 'deleted': True, 'trash_id': trash_id, 'vehicles_deleted': len(archived), 'vehicles_detached': len(detached)}


def cascade_client_archive(con, client_id: str, ts: str) -> dict:
    """Called inside archive_clients: take the client's fleets and vehicles along."""
    vehicle_ids = [r[0] for r in con.execute('SELECT id FROM vehicles WHERE client_id=? AND archived=0', (client_id,))]
    fleet_ids = [r[0] for r in con.execute('SELECT id FROM fleets WHERE client_id=? AND archived=0', (client_id,))]
    _archive_vehicle_rows(con, vehicle_ids, ts)
    for fid in fleet_ids:
        con.execute('UPDATE fleets SET archived=1,revision=revision+1,updated_at=? WHERE id=?', (ts, fid))
    return {'vehicles': vehicle_ids, 'fleets': fleet_ids}


def restore_mobility(con, payload: dict, *, client_id: str | None = None) -> dict:
    """Undo a deletion recorded by this module (or a client cascade). Plates taken meanwhile stay archived."""
    ts = now()
    today = date.today().isoformat()
    restored, skipped = [], []
    fleet_ids = list(payload.get('fleets') or [])
    vehicle_ids = list(payload.get('vehicles') or [])
    if client_id is not None and 'vehicles' not in payload and 'fleets' not in payload:
        # legacy client trash entry (before V-01): bring back everything archived by the migration
        fleet_ids = [r[0] for r in con.execute('SELECT id FROM fleets WHERE client_id=? AND archived=1', (client_id,))]
        vehicle_ids = [r[0] for r in con.execute('SELECT id FROM vehicles WHERE client_id=? AND archived=1', (client_id,))]
    for fid in fleet_ids:
        con.execute('UPDATE fleets SET archived=0,revision=revision+1,updated_at=? WHERE id=?', (ts, fid))
    for vid in vehicle_ids:
        row = con.execute('SELECT * FROM vehicles WHERE id=?', (vid,)).fetchone()
        if not row or not row['archived']:
            continue
        if plate_owner(con, row['plate'], vid):
            skipped.append(row['plate'])
            continue
        fleet_ok = row['fleet_id'] and con.execute('SELECT 1 FROM fleets WHERE id=? AND archived=0', (row['fleet_id'],)).fetchone()
        fleet_id = row['fleet_id'] if fleet_ok else None
        con.execute('UPDATE vehicles SET archived=0,fleet_id=?,revision=revision+1,updated_at=? WHERE id=?', (fleet_id, ts, vid))
        con.execute('INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',
                    (uid(), vid, row['client_id'], fleet_id, today, ts))
        restored.append(vid)
    for vid in payload.get('detached') or []:
        fid = (payload.get('fleets') or [None])[0]
        row = con.execute('SELECT * FROM vehicles WHERE id=? AND archived=0 AND fleet_id IS NULL', (vid,)).fetchone()
        if row and fid:
            con.execute('UPDATE vehicles SET fleet_id=?,revision=revision+1,updated_at=? WHERE id=?', (fid, ts, vid))
            con.execute('UPDATE ownerships SET effective_to=? WHERE vehicle_id=? AND effective_to IS NULL', (today, vid))
            con.execute('INSERT INTO ownerships(id,vehicle_id,client_id,fleet_id,effective_from,created_at) VALUES(?,?,?,?,?,?)',
                        (uid(), vid, row['client_id'], fid, today, ts))
    return {'vehicles_restored': len(restored), 'plates_in_use': skipped}
