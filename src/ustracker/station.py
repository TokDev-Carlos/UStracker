from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import Database

UTC = timezone.utc


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _state_file(root: Path) -> Path:
    path = Path(root) / 'UserData' / 'State' / 'station.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def local_identity(root: Path | str) -> dict:
    root = Path(root)
    path = _state_file(root)
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('id') and data.get('fingerprint'):
            return data
    machine = os.environ.get('COMPUTERNAME') or platform.node() or 'Station'
    raw = f'{machine}|{uuid.getnode()}'.encode('utf-8')
    data = {
        'id': str(uuid.uuid4()),
        'name': machine[:80],
        'fingerprint': hashlib.sha256(raw).hexdigest(),
        'created_at': _now(),
    }
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return data


def ensure_station(root: Path | str, db: Database) -> dict:
    ident = local_identity(root)
    row = db.one('SELECT * FROM stations WHERE id=?', (ident['id'],))
    if row:
        return dict(row)
    with db.transaction() as con:
        row = con.execute('SELECT * FROM stations WHERE id=?', (ident['id'],)).fetchone()
        if row:
            return dict(row)
        active_count = int(con.execute("SELECT COUNT(*) FROM stations WHERE status='ACTIVE'").fetchone()[0])
        if active_count >= 3:
            raise RuntimeError('maximum three active stations registered for this dataset')
        has_writer = int(con.execute("SELECT COUNT(*) FROM stations WHERE is_writer=1 AND status='ACTIVE'").fetchone()[0]) > 0
        generation = max(1, int(con.execute('SELECT COALESCE(MAX(generation),0) FROM stations').fetchone()[0]))
        transfer = con.execute("SELECT value FROM settings WHERE key='transfer_generation'").fetchone()
        writer = 1 if (not has_writer and (active_count == 0 or transfer is not None)) else 0
        if transfer is not None and writer:
            generation = int(transfer[0])
        ts = _now()
        con.execute(
            'INSERT INTO stations(id,name,fingerprint,is_writer,generation,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
            (ident['id'], ident['name'], ident['fingerprint'], writer, generation, 'ACTIVE', ts, ts),
        )
        if transfer is not None and writer:
            con.execute("DELETE FROM settings WHERE key='transfer_generation'")
        return dict(con.execute('SELECT * FROM stations WHERE id=?', (ident['id'],)).fetchone())


def require_writer(root: Path | str, db: Database) -> dict:
    station = ensure_station(root, db)
    if db.environment == 'production' and not bool(station['is_writer']):
        raise PermissionError(
            f"station '{station['name']}' is read-only for this dataset; perform an explicit station transfer first"
        )
    return station


def list_stations(root: Path | str, db: Database) -> dict:
    current = ensure_station(root, db)
    rows = [dict(r) for r in db.query('SELECT * FROM stations ORDER BY created_at')]
    return {'current_station_id': current['id'], 'items': rows}


def relinquish_writer(root: Path | str, db: Database) -> dict:
    current = require_writer(root, db)
    if db.environment != 'production':
        raise ValueError('station transfer applies only to production')
    with db.transaction() as con:
        generation = max(1, int(con.execute('SELECT COALESCE(MAX(generation),1) FROM stations').fetchone()[0]))
        con.execute(
            "UPDATE stations SET is_writer=0,status='TRANSFERRED',updated_at=? WHERE id=?",
            (_now(), current['id']),
        )
        con.execute(
            "INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES('transfer_generation',?,?)",
            (str(generation + 1), _now()),
        )
    return {'station_id': current['id'], 'generation': generation + 1, 'writer_relinquished': True}


def reclaim_writer_after_failed_transfer(root: Path | str, db: Database) -> None:
    ident = local_identity(root)
    with db.transaction() as con:
        con.execute('UPDATE stations SET is_writer=0')
        con.execute(
            "UPDATE stations SET is_writer=1,status='ACTIVE',updated_at=? WHERE id=?",
            (_now(), ident['id']),
        )
        con.execute("DELETE FROM settings WHERE key='transfer_generation'")


def claim_pending_writer(root: Path | str, db: Database, confirmation: str) -> dict:
    if db.environment != 'production':
        raise ValueError('writer claim applies only to production')
    current = ensure_station(root, db)
    writers = int(db.one("SELECT COUNT(*) FROM stations WHERE is_writer=1 AND status='ACTIVE'")[0])
    if writers:
        if current['is_writer']:
            return current
        raise PermissionError('another station is still the designated writer')
    if confirmation != 'ASSUMIR ESCRITA':
        raise ValueError('exact confirmation ASSUMIR ESCRITA required')
    with db.transaction() as con:
        generation_row = con.execute("SELECT value FROM settings WHERE key='transfer_generation'").fetchone()
        generation = int(generation_row[0]) if generation_row else max(
            1, int(con.execute('SELECT COALESCE(MAX(generation),1) FROM stations').fetchone()[0]) + 1
        )
        con.execute('UPDATE stations SET is_writer=0')
        con.execute(
            "UPDATE stations SET is_writer=1,generation=?,status='ACTIVE',updated_at=? WHERE id=?",
            (generation, _now(), current['id']),
        )
        con.execute("DELETE FROM settings WHERE key='transfer_generation'")
    return dict(db.one('SELECT * FROM stations WHERE id=?', (current['id'],)))


def emergency_takeover(root: Path | str, db: Database, confirmation: str, reason: str) -> dict:
    if db.environment != 'production':
        raise ValueError('emergency takeover applies only to production')
    if confirmation != 'ASSUMIR EMERGENCIA' or len(str(reason).strip()) < 10:
        raise ValueError('exact confirmation ASSUMIR EMERGENCIA and a detailed reason are required')
    current = ensure_station(root, db)
    with db.transaction() as con:
        generation = max(1, int(con.execute('SELECT COALESCE(MAX(generation),1) FROM stations').fetchone()[0])) + 1
        con.execute(
            "UPDATE stations SET is_writer=0,status=CASE WHEN id=? THEN 'ACTIVE' ELSE 'REVOKED' END,updated_at=?",
            (current['id'], _now()),
        )
        con.execute(
            "UPDATE stations SET is_writer=1,generation=?,status='ACTIVE',updated_at=? WHERE id=?",
            (generation, _now(), current['id']),
        )
        con.execute("DELETE FROM settings WHERE key='transfer_generation'")
        con.execute(
            "INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES('last_emergency_takeover',?,?)",
            (json.dumps({'generation': generation, 'reason': str(reason)[:500]}, ensure_ascii=False), _now()),
        )
    return dict(db.one('SELECT * FROM stations WHERE id=?', (current['id'],)))
