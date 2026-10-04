"""C-09 — Lixeira de 14 dias.

Everything deleted *inside* the system goes to the trash first (same transaction as the
deletion). For 14 days it can be restored with one click; after that it is purged for good:
the trash payload is wiped, photo files are erased and the cloud is told to drop them.

Kinds:
* ``expense``  — expense row (only deletable when unpaid)
* ``catalog``  — never-used plan/product + cost components + price history
* ``media``    — photo row; the encrypted files stay on disk until purge
* ``client``   — archived client; restore = unarchive. Clients keep their financial history,
                 so after 14 days they leave the trash but stay archived (never hard-deleted).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import Database
from .paths import resolve_stored_path
from .services import audit, now, uid

RETENTION_DAYS = 14
UTC = timezone.utc
KIND_LABEL = {'expense': 'Despesa', 'catalog': 'Plano/Produto', 'media': 'Foto', 'client': 'Cliente'}


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def put(con, actor: int, kind: str, entity_id: str, label: str, payload: dict, at: datetime | None = None) -> str:
    """Record a deletion. Must be called inside the transaction that performs it."""
    when = at or datetime.now(UTC)
    tid = uid()
    con.execute('''INSERT INTO trash(id,entity_type,entity_id,label,payload,deleted_at,purge_after,actor_slot)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (tid, kind, entity_id, label[:200], json.dumps(payload, ensure_ascii=False, default=str), _iso(when),
                 _iso(when + timedelta(days=RETENTION_DAYS)), actor))
    return tid


def list_trash(db: Database, at: datetime | None = None) -> list[dict]:
    when = at or datetime.now(UTC)
    out = []
    for r in db.query('''SELECT id,entity_type,entity_id,label,deleted_at,purge_after FROM trash
                         WHERE restored_at IS NULL AND purged_at IS NULL ORDER BY deleted_at DESC'''):
        rec = dict(r)
        left = datetime.fromisoformat(rec['purge_after']) - when
        rec['days_left'] = max(0, left.days + (1 if left.seconds > 0 else 0))
        rec['kind_label'] = KIND_LABEL.get(rec['entity_type'], rec['entity_type'])
        out.append(rec)
    return out


def _insert(con, table: str, row: dict):
    cols = list(row)
    con.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", tuple(row[c] for c in cols))


def restore(db: Database, actor: int, trash_id: str) -> dict:
    with db.transaction() as con:
        item = con.execute('SELECT * FROM trash WHERE id=?', (trash_id,)).fetchone()
        if not item:
            raise KeyError('trash item not found')
        if item['restored_at'] or item['purged_at']:
            raise ValueError('trash item is no longer restorable')
        payload = json.loads(item['payload'] or '{}')
        kind = item['entity_type']
        if kind == 'expense':
            _insert(con, 'expenses', payload['row'])
        elif kind == 'catalog':
            row = dict(payload['row'])
            if con.execute('SELECT 1 FROM catalog WHERE code=?', (row['code'],)).fetchone():
                from .catalog import _next_code
                row['code'] = _next_code(con)
            _insert(con, 'catalog', row)
            for comp in payload.get('components', []):
                _insert(con, 'catalog_cost_components', comp)
            for price in payload.get('prices', []):
                _insert(con, 'catalog_prices', price)
        elif kind == 'media':
            _insert(con, 'media', payload['row'])
        elif kind == 'client':
            con.execute("UPDATE clients SET archived=0,status='ACTIVE',revision=revision+1,updated_at=? WHERE id=?", (now(), item['entity_id']))
        else:
            raise ValueError('unknown trash kind')
        con.execute('UPDATE trash SET restored_at=? WHERE id=?', (now(), trash_id))
        audit(con, actor, 'TRASH_RESTORE', kind, item['entity_id'], None, {'trash_id': trash_id})
        return {'id': trash_id, 'entity_type': kind, 'entity_id': item['entity_id'], 'restored': True}


def purge_due(root: Path | str, db: Database, actor: int = 0, at: datetime | None = None) -> dict:
    """Purge items whose 14 days are over. Returns the photo files erased (for the cloud)."""
    when = at or datetime.now(UTC)
    erased_files: list[str] = []
    purged = []
    with db.transaction() as con:
        due = con.execute('''SELECT * FROM trash WHERE restored_at IS NULL AND purged_at IS NULL AND purge_after<=?''', (_iso(when),)).fetchall()
        for item in due:
            payload = json.loads(item['payload'] or '{}')
            if item['entity_type'] == 'media':
                for col in ('variant_path', 'thumb_path', 'original_path'):
                    rel = (payload.get('row') or {}).get(col)
                    if rel:
                        erased_files.append(Path(str(rel).replace('\\', '/')).name)
            con.execute("UPDATE trash SET purged_at=?,payload='{}' WHERE id=?", (_iso(when), item['id']))
            audit(con, actor, 'TRASH_PURGE', item['entity_type'], item['entity_id'], None, {'trash_id': item['id']})
            purged.append(item['id'])
    # files are erased only after the purge is committed
    media_dir = Path(root) / 'UserData' / 'Media' / db.environment
    for name in erased_files:
        (media_dir / name).unlink(missing_ok=True)
    return {'purged': len(purged), 'erased_files': erased_files}


def media_trash_row(row) -> dict:
    return {'row': dict(row)}
