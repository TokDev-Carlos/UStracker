"""AJ-04 — logical public codes.

UUIDs remain the technical identity (PK/FK/API). Each client receives an immutable
public code (CLI-0001) and dependent entities receive a per-client sequence
(CLI-0001-V01, -F01, -A01, -C01, -R01). Charges derive their display code from the
subscription code and competence, so they need no stored column.

Codes are issued by SQLite triggers so every insertion path (current services,
compatibility seams and restore of older databases) gets a code inside the same
transaction. Numbers are never reused: counters only grow and every issued code
stays registered in ``logical_codes`` (retired codes keep their row).
"""
from __future__ import annotations

from datetime import datetime, timezone

# entity table -> (kind letter, entity_type label)
DEPENDENT_KINDS = {
    'vehicles': ('V', 'vehicle'),
    'fleets': ('F', 'fleet'),
    'subscriptions': ('A', 'subscription'),
    'direct_sales': ('C', 'direct_sale'),
    'payments': ('R', 'payment'),
}
CODE_TABLES = ('clients',) + tuple(DEPENDENT_KINDS)

TABLES_SQL = '''
CREATE TABLE IF NOT EXISTS logical_codes(
 code TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 client_id TEXT, issued_at TEXT NOT NULL, retired_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_logical_codes_entity ON logical_codes(entity_id,retired_at);
CREATE TABLE IF NOT EXISTS code_counters(
 scope TEXT NOT NULL, kind TEXT NOT NULL, last_value INTEGER NOT NULL,
 PRIMARY KEY(scope,kind)
);
'''


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_trigger() -> str:
    return '''
CREATE TRIGGER IF NOT EXISTS trg_code_issue_clients AFTER INSERT ON clients
WHEN NEW.code IS NULL
BEGIN
 INSERT INTO code_counters(scope,kind,last_value) VALUES('GLOBAL','CLI',1)
  ON CONFLICT(scope,kind) DO UPDATE SET last_value=last_value+1;
 INSERT INTO logical_codes(code,entity_type,entity_id,client_id,issued_at)
  VALUES('CLI-'||printf('%04d',(SELECT last_value FROM code_counters WHERE scope='GLOBAL' AND kind='CLI')),
         'client',NEW.id,NEW.id,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
 UPDATE clients SET code='CLI-'||printf('%04d',(SELECT last_value FROM code_counters WHERE scope='GLOBAL' AND kind='CLI'))
  WHERE id=NEW.id;
END;
'''


def _dependent_trigger(table: str, kind: str, entity_type: str) -> str:
    code_expr = (f"(SELECT code FROM clients WHERE id=NEW.client_id)||'-{kind}'||"
                 f"printf('%02d',(SELECT last_value FROM code_counters WHERE scope=NEW.client_id AND kind='{kind}'))")
    return f'''
CREATE TRIGGER IF NOT EXISTS trg_code_issue_{table} AFTER INSERT ON {table}
WHEN NEW.code IS NULL
BEGIN
 INSERT INTO code_counters(scope,kind,last_value) VALUES(NEW.client_id,'{kind}',1)
  ON CONFLICT(scope,kind) DO UPDATE SET last_value=last_value+1;
 INSERT INTO logical_codes(code,entity_type,entity_id,client_id,issued_at)
  VALUES({code_expr},'{entity_type}',NEW.id,NEW.client_id,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
 UPDATE {table} SET code={code_expr} WHERE id=NEW.id;
END;
'''


def _immutability_trigger(table: str) -> str:
    # A code may only change to a code already registered (active) for the same entity.
    # The vehicle transfer trigger registers the new code first; any other change aborts.
    return f'''
CREATE TRIGGER IF NOT EXISTS trg_code_immutable_{table} BEFORE UPDATE OF code ON {table}
WHEN OLD.code IS NOT NULL AND NEW.code IS NOT OLD.code
 AND NOT EXISTS(SELECT 1 FROM logical_codes lc WHERE lc.code=NEW.code AND lc.entity_id=NEW.id AND lc.retired_at IS NULL)
BEGIN
 SELECT RAISE(ABORT,'logical code is immutable');
END;
'''


VEHICLE_TRANSFER_TRIGGER = '''
CREATE TRIGGER IF NOT EXISTS trg_code_vehicle_transfer AFTER UPDATE OF client_id ON vehicles
WHEN OLD.client_id IS NOT NEW.client_id
BEGIN
 INSERT INTO code_counters(scope,kind,last_value) VALUES(NEW.client_id,'V',1)
  ON CONFLICT(scope,kind) DO UPDATE SET last_value=last_value+1;
 UPDATE logical_codes SET retired_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
  WHERE entity_id=NEW.id AND retired_at IS NULL;
 INSERT INTO logical_codes(code,entity_type,entity_id,client_id,issued_at)
  VALUES((SELECT code FROM clients WHERE id=NEW.client_id)||'-V'||
         printf('%02d',(SELECT last_value FROM code_counters WHERE scope=NEW.client_id AND kind='V')),
         'vehicle',NEW.id,NEW.client_id,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
 UPDATE vehicles SET code=(SELECT code FROM clients WHERE id=NEW.client_id)||'-V'||
         printf('%02d',(SELECT last_value FROM code_counters WHERE scope=NEW.client_id AND kind='V'))
  WHERE id=NEW.id;
END;
'''


def triggers_sql() -> str:
    parts = [_client_trigger()]
    for table, (kind, entity_type) in DEPENDENT_KINDS.items():
        parts.append(_dependent_trigger(table, kind, entity_type))
    for table in CODE_TABLES:
        parts.append(_immutability_trigger(table))
    parts.append(VEHICLE_TRANSFER_TRIGGER)
    return '\n'.join(parts)


def _bump(con, scope: str, kind: str) -> int:
    con.execute('INSERT INTO code_counters(scope,kind,last_value) VALUES(?,?,1) '
                'ON CONFLICT(scope,kind) DO UPDATE SET last_value=last_value+1', (scope, kind))
    return int(con.execute('SELECT last_value FROM code_counters WHERE scope=? AND kind=?', (scope, kind)).fetchone()[0])


def migrate(con) -> None:
    """Schema 10: additive columns, registry, deterministic backfill and triggers. Reentrant."""
    con.executescript(TABLES_SQL)
    for table in CODE_TABLES:
        cols = {r[1] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
        if 'code' not in cols:
            con.execute(f'ALTER TABLE {table} ADD COLUMN code TEXT')
        con.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_code ON {table}(code) WHERE code IS NOT NULL')
    ts = _now()
    # Deterministic backfill: creation date, UUID as tie-breaker. Only NULL codes are filled.
    for row in con.execute('SELECT id FROM clients WHERE code IS NULL ORDER BY created_at,id').fetchall():
        code = f"CLI-{_bump(con, 'GLOBAL', 'CLI'):04d}"
        con.execute('INSERT INTO logical_codes(code,entity_type,entity_id,client_id,issued_at) VALUES(?,?,?,?,?)',
                    (code, 'client', row[0], row[0], ts))
        con.execute('UPDATE clients SET code=? WHERE id=?', (code, row[0]))
    for table, (kind, entity_type) in DEPENDENT_KINDS.items():
        rows = con.execute(f'''SELECT t.id,t.client_id,c.code FROM {table} t JOIN clients c ON c.id=t.client_id
                               WHERE t.code IS NULL ORDER BY c.code,t.created_at,t.id''').fetchall()
        for row in rows:
            code = f"{row[2]}-{kind}{_bump(con, row[1], kind):02d}"
            con.execute('INSERT INTO logical_codes(code,entity_type,entity_id,client_id,issued_at) VALUES(?,?,?,?,?)',
                        (code, entity_type, row[0], row[1], ts))
            con.execute(f'UPDATE {table} SET code=? WHERE id=?', (code, row[0]))
    con.executescript(triggers_sql())


def charge_code(subscription_code: str | None, competence: str | None) -> str | None:
    if not subscription_code or not competence:
        return None
    return f'{subscription_code}/{str(competence)[:7]}'


def entity_code(con_or_db, entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    query = getattr(con_or_db, 'one', None)
    sql = 'SELECT code FROM logical_codes WHERE entity_id=? ORDER BY retired_at IS NOT NULL,issued_at DESC LIMIT 1'
    row = query(sql, (entity_id,)) if query else con_or_db.execute(sql, (entity_id,)).fetchone()
    return row[0] if row else None


def resolve_entity_ref(db, entity_type: str | None, value: str | None) -> str | None:
    """Accept a logical code (CLI-0001-V01) where an entity UUID is expected. UUIDs pass through."""
    text = str(value or '').strip()
    if not text.upper().startswith('CLI-'):
        return value
    row = db.one('SELECT entity_id,entity_type FROM logical_codes WHERE upper(code)=upper(?) AND retired_at IS NULL', (text,))
    if not row:
        raise ValueError('logical code not found')
    if entity_type and row['entity_type'] != entity_type:
        raise ValueError('logical code does not match entity type')
    return row['entity_id']
