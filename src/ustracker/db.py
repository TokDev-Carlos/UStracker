from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 3

SCHEMA_SQL = r'''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor_slot INTEGER NOT NULL,
 action TEXT NOT NULL, entity_type TEXT, entity_id TEXT, before_json TEXT, after_json TEXT,
 previous_hash TEXT, event_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients(
 id TEXT PRIMARY KEY, legal_name TEXT NOT NULL, trade_name TEXT, public_name TEXT,
 document TEXT, email TEXT, phone TEXT, address TEXT, notes TEXT,
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE','BLOCKED','CANCELLED')),
 archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_document ON clients(document) WHERE document IS NOT NULL AND document<>'';
CREATE TABLE IF NOT EXISTS fleets(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), name TEXT NOT NULL,
 sector_or_unit TEXT, archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vehicles(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), fleet_id TEXT REFERENCES fleets(id),
 plate TEXT NOT NULL, type TEXT NOT NULL, renavam TEXT, tracker_ref TEXT, tracker_serial_imei TEXT,
 installed_on TEXT, tracking_status TEXT NOT NULL DEFAULT 'UNTRACKED', notes TEXT,
 archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_vehicles_plate_active ON vehicles(upper(plate)) WHERE archived=0;
CREATE TABLE IF NOT EXISTS ownerships(
 id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicles(id), client_id TEXT NOT NULL REFERENCES clients(id),
 fleet_id TEXT REFERENCES fleets(id), effective_from TEXT NOT NULL, effective_to TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog(
 id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT, category TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('PLAN','ITEM')), billing_interval_months INTEGER NOT NULL DEFAULT 1,
 price_cents INTEGER NOT NULL DEFAULT 0, cost_cents INTEGER NOT NULL DEFAULT 0, notes TEXT,
 public INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog_prices(
 id TEXT PRIMARY KEY, catalog_id TEXT NOT NULL REFERENCES catalog(id), effective_from TEXT NOT NULL,
 price_cents INTEGER NOT NULL, cost_cents INTEGER NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(catalog_id,effective_from)
);
CREATE TABLE IF NOT EXISTS subscriptions(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), signed_on TEXT NOT NULL,
 start_on TEXT NOT NULL, end_on TEXT, due_day INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),
 billing_interval_months INTEGER NOT NULL DEFAULT 1, billing_cycle TEXT NOT NULL DEFAULT 'MONTHLY',
 renewal_mode TEXT NOT NULL DEFAULT 'MANUAL',
 lifecycle_status TEXT NOT NULL CHECK(lifecycle_status IN ('ACTIVE','PAUSED','CANCELLED','ENDED')),
 revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscription_items(
 id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
 catalog_id TEXT REFERENCES catalog(id), vehicle_id TEXT REFERENCES vehicles(id), description TEXT NOT NULL,
 quantity INTEGER NOT NULL DEFAULT 1, unit_price_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS direct_sales(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), sold_on TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN', paid_on TEXT, total_cents INTEGER NOT NULL DEFAULT 0,
 notes TEXT, revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS direct_sale_items(
 id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES direct_sales(id) ON DELETE CASCADE,
 catalog_id TEXT REFERENCES catalog(id), vehicle_id TEXT REFERENCES vehicles(id),
 description TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1, unit_price_cents INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_direct_sales_client ON direct_sales(client_id,sold_on,status);
CREATE INDEX IF NOT EXISTS ix_direct_sales_paid ON direct_sales(paid_on,status);
CREATE INDEX IF NOT EXISTS ix_direct_sale_items_sale ON direct_sale_items(sale_id);
CREATE TABLE IF NOT EXISTS charges(
 id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL REFERENCES subscriptions(id), client_id TEXT NOT NULL REFERENCES clients(id),
 competence TEXT NOT NULL, due_on TEXT NOT NULL, amount_cents INTEGER NOT NULL, adjustment_cents INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL DEFAULT 'OPEN', revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(subscription_id,competence)
);
CREATE TABLE IF NOT EXISTS charge_adjustments(
 id TEXT PRIMARY KEY, charge_id TEXT NOT NULL REFERENCES charges(id), kind TEXT NOT NULL, amount_cents INTEGER NOT NULL,
 reason TEXT NOT NULL, effective_on TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), paid_on TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0), method TEXT, notes TEXT, reversed_at TEXT,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_allocations(
 id TEXT PRIMARY KEY, payment_id TEXT NOT NULL REFERENCES payments(id), charge_id TEXT NOT NULL REFERENCES charges(id),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0), active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS credits(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), origin_payment_id TEXT REFERENCES payments(id),
 amount_cents INTEGER NOT NULL, balance_cents INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS credit_allocations(
 id TEXT PRIMARY KEY, credit_id TEXT NOT NULL REFERENCES credits(id), charge_id TEXT NOT NULL REFERENCES charges(id),
 amount_cents INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, applied_on TEXT NOT NULL, reversed_on TEXT
);
CREATE TABLE IF NOT EXISTS expenses(
 id TEXT PRIMARY KEY, category TEXT NOT NULL, description TEXT NOT NULL, competence TEXT NOT NULL, due_on TEXT,
 expected_amount_cents INTEGER NOT NULL, supplier TEXT, client_id TEXT REFERENCES clients(id), vehicle_id TEXT REFERENCES vehicles(id),
 subscription_id TEXT REFERENCES subscriptions(id), catalog_id TEXT REFERENCES catalog(id), recurrence_id TEXT,
 status TEXT NOT NULL DEFAULT 'OPEN', revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_expense_recurrence_comp ON expenses(recurrence_id,competence) WHERE recurrence_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS disbursements(
 id TEXT PRIMARY KEY, expense_id TEXT NOT NULL REFERENCES expenses(id), paid_on TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0), reversed_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fiscal_obligations(
 id TEXT PRIMARY KEY, competence TEXT NOT NULL, description TEXT NOT NULL, amount_cents INTEGER,
 due_on TEXT, status TEXT NOT NULL DEFAULT 'OPEN', external_ref TEXT, expense_id TEXT REFERENCES expenses(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media(
 id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, variant_path TEXT NOT NULL,
 thumb_path TEXT NOT NULL, original_path TEXT, mime TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL,
 sha256 TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stations(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, fingerprint TEXT, is_writer INTEGER NOT NULL DEFAULT 0,
 generation INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operations(
 operation_id TEXT PRIMARY KEY, actor_slot INTEGER NOT NULL, route TEXT NOT NULL, payload_hash TEXT NOT NULL,
 response_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DONE', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_clients_name ON clients(legal_name,trade_name,public_name);
CREATE INDEX IF NOT EXISTS ix_vehicles_plate ON vehicles(plate);
CREATE INDEX IF NOT EXISTS ix_charges_client_due ON charges(client_id,due_on,status);
CREATE INDEX IF NOT EXISTS ix_payments_client_date ON payments(client_id,paid_on);
CREATE INDEX IF NOT EXISTS ix_expenses_competence ON expenses(competence);
'''


class Database:
    def __init__(self, root: Path, environment: str, key: bytes):
        self.root = Path(root)
        self.environment = environment
        self.key = key
        self.db_dir = self.root / 'UserData' / environment.capitalize()
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.db_dir / 'ustracker.db'
        self._lock = threading.RLock()
        self._ensure_schema()

    def _module(self):
        try:
            import sqlcipher3 as dbapi  # type: ignore
            return dbapi, True
        except Exception:
            if os.getenv('USTRACKER_DEV_PLAINTEXT') == '1':
                return sqlite3, False
            raise RuntimeError('sqlcipher3 0.6.2 is required in production runtime')

    def connect(self):
        dbapi, cipher = self._module()
        con = dbapi.connect(str(self.path), timeout=5)
        try:
            con.row_factory = dbapi.Row
        except Exception:
            pass
        if cipher:
            con.execute(f"PRAGMA key=\"x'{self.key.hex()}'\"")
            row = con.execute('PRAGMA cipher_version').fetchone()
            if not row or not row[0]:
                con.close()
                raise RuntimeError('SQLCipher cipher_version unavailable')
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA synchronous=FULL')
        con.execute('PRAGMA journal_mode=DELETE')
        con.execute('PRAGMA busy_timeout=5000')
        return con

    def _ensure_schema(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA_SQL)
            current = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            current_version = int(current[0]) if current else 0
            if current_version > SCHEMA_VERSION:
                raise RuntimeError('database schema is newer than this application')
            if current_version < 2:
                cols = {r[1] for r in con.execute("PRAGMA table_info(operations)").fetchall()}
                if 'status' not in cols:
                    con.execute("ALTER TABLE operations ADD COLUMN status TEXT NOT NULL DEFAULT 'DONE'")
                if 'updated_at' not in cols:
                    con.execute("ALTER TABLE operations ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
                    con.execute("UPDATE operations SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL")
            if current_version < 3:
                cols = {r[1] for r in con.execute("PRAGMA table_info(subscriptions)").fetchall()}
                if 'billing_cycle' not in cols:
                    con.execute("ALTER TABLE subscriptions ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT 'MONTHLY'")
                con.execute("""UPDATE subscriptions SET billing_cycle=CASE
                    WHEN billing_interval_months >= 12 THEN 'ANNUAL' ELSE 'MONTHLY' END""")
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    @contextmanager
    def transaction(self) -> Iterator:
        with self._lock:
            con = self.connect()
            try:
                con.execute('BEGIN IMMEDIATE')
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def query(self, sql: str, args=()):
        with self.connect() as con:
            return con.execute(sql, args).fetchall()

    def one(self, sql: str, args=()):
        with self.connect() as con:
            return con.execute(sql, args).fetchone()
