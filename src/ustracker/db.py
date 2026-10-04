from __future__ import annotations

import os
import sqlite3
import threading
import unicodedata
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 14


def fold_text(value) -> str:
    text=unicodedata.normalize('NFKD',str(value or ''))
    return ''.join(character for character in text if not unicodedata.combining(character)).casefold()

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
CREATE TABLE IF NOT EXISTS client_documents(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), type TEXT NOT NULL CHECK(type IN ('CPF','RG','CNH')),
 number TEXT NOT NULL, normalized_number TEXT NOT NULL, is_primary INTEGER NOT NULL DEFAULT 0,
 archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_client_documents_type_number_active
 ON client_documents(type,normalized_number) WHERE archived=0;
CREATE INDEX IF NOT EXISTS ix_client_documents_client ON client_documents(client_id,archived,is_primary);
CREATE TABLE IF NOT EXISTS client_companies(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), legal_name TEXT NOT NULL,
 trade_name TEXT, document TEXT, normalized_document TEXT, is_primary INTEGER NOT NULL DEFAULT 0,
 archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_client_companies_client ON client_companies(client_id,archived,is_primary);
CREATE TABLE IF NOT EXISTS fleets(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), client_company_id TEXT REFERENCES client_companies(id), name TEXT NOT NULL,
 sector_or_unit TEXT, archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vehicles(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), fleet_id TEXT REFERENCES fleets(id),
 plate TEXT NOT NULL, type TEXT NOT NULL, brand TEXT, model TEXT, year INTEGER, contracted_on TEXT, review_on TEXT,
 renavam TEXT, tracker_ref TEXT, tracker_serial_imei TEXT, installed_on TEXT, tracking_status TEXT NOT NULL DEFAULT 'UNTRACKED', notes TEXT,
 archived INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_vehicles_plate_active ON vehicles(upper(plate)) WHERE archived=0;
CREATE TABLE IF NOT EXISTS ownerships(
 id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicles(id), client_id TEXT NOT NULL REFERENCES clients(id),
 fleet_id TEXT REFERENCES fleets(id), effective_from TEXT NOT NULL, effective_to TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vehicle_transfer_cases(
 id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicles(id),
 from_client_id TEXT NOT NULL REFERENCES clients(id), from_fleet_id TEXT REFERENCES fleets(id),
 to_client_id TEXT NOT NULL REFERENCES clients(id), to_fleet_id TEXT REFERENCES fleets(id),
 effective_from TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','COMPLETED','CANCELLED')),
 source_revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 completed_at TEXT, cancelled_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_vehicle_transfer_pending ON vehicle_transfer_cases(vehicle_id) WHERE status='PENDING';
CREATE INDEX IF NOT EXISTS ix_vehicle_transfer_status ON vehicle_transfer_cases(status,created_at);
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
CREATE TABLE IF NOT EXISTS catalog_cost_components(
 id TEXT PRIMARY KEY, catalog_id TEXT NOT NULL REFERENCES catalog(id) ON DELETE CASCADE,
 description TEXT, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), position INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_catalog_cost_components_catalog ON catalog_cost_components(catalog_id,position,id);
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
CREATE TABLE IF NOT EXISTS subscription_targets(
 id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
 vehicle_id TEXT REFERENCES vehicles(id), fleet_id TEXT REFERENCES fleets(id), created_at TEXT NOT NULL,
 CHECK((vehicle_id IS NOT NULL AND fleet_id IS NULL) OR (vehicle_id IS NULL AND fleet_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_subscription_targets_vehicle
 ON subscription_targets(subscription_id,vehicle_id) WHERE vehicle_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_subscription_targets_fleet
 ON subscription_targets(subscription_id,fleet_id) WHERE fleet_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_subscription_targets_vehicle ON subscription_targets(vehicle_id,subscription_id);
CREATE INDEX IF NOT EXISTS ix_subscription_targets_fleet ON subscription_targets(fleet_id,subscription_id);
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
CREATE TABLE IF NOT EXISTS service_coverage_periods(
 id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), subscription_id TEXT NOT NULL REFERENCES subscriptions(id),
 origin_payment_id TEXT NOT NULL REFERENCES payments(id), start_on TEXT NOT NULL, end_on TEXT NOT NULL,
 cycles INTEGER NOT NULL CHECK(cycles>0), applied_value_cents INTEGER NOT NULL CHECK(applied_value_cents>=0), created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_service_coverage_subscription ON service_coverage_periods(subscription_id,end_on);
CREATE INDEX IF NOT EXISTS ix_service_coverage_payment ON service_coverage_periods(origin_payment_id);
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
CREATE TABLE IF NOT EXISTS attachments(
 id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 client_id TEXT REFERENCES clients(id), subscription_id TEXT REFERENCES subscriptions(id),
 vehicle_id TEXT REFERENCES vehicles(id), fleet_id TEXT REFERENCES fleets(id),
 filename TEXT, mime TEXT, size_bytes INTEGER NOT NULL DEFAULT 0, sha256 TEXT,
 origin TEXT NOT NULL CHECK(origin IN ('LOCAL','LINK')), local_path TEXT, url TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_attachments_local_hash ON attachments(sha256) WHERE origin='LOCAL' AND sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_attachments_entity ON attachments(entity_type,entity_id,created_at);
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
-- R23 performance: foreign-key lookups used by every list screen
CREATE INDEX IF NOT EXISTS ix_subscription_items_sub ON subscription_items(subscription_id);
CREATE INDEX IF NOT EXISTS ix_subscription_items_vehicle ON subscription_items(vehicle_id);
CREATE INDEX IF NOT EXISTS ix_direct_sale_items_vehicle ON direct_sale_items(vehicle_id);
CREATE INDEX IF NOT EXISTS ix_vehicles_client ON vehicles(client_id,archived);
CREATE INDEX IF NOT EXISTS ix_vehicles_fleet ON vehicles(fleet_id,archived);
CREATE INDEX IF NOT EXISTS ix_fleets_client ON fleets(client_id,archived);
CREATE INDEX IF NOT EXISTS ix_subscriptions_client ON subscriptions(client_id,lifecycle_status);
CREATE INDEX IF NOT EXISTS ix_subscriptions_status ON subscriptions(lifecycle_status,start_on);
CREATE INDEX IF NOT EXISTS ix_charges_subscription ON charges(subscription_id,status);
CREATE INDEX IF NOT EXISTS ix_payment_allocations_charge ON payment_allocations(charge_id,active);
CREATE INDEX IF NOT EXISTS ix_payment_allocations_payment ON payment_allocations(payment_id);
CREATE INDEX IF NOT EXISTS ix_credit_allocations_charge ON credit_allocations(charge_id,active);
CREATE INDEX IF NOT EXISTS ix_disbursements_expense ON disbursements(expense_id,reversed_at);
CREATE INDEX IF NOT EXISTS ix_media_entity ON media(entity_type,entity_id);
CREATE INDEX IF NOT EXISTS ix_ownerships_vehicle ON ownerships(vehicle_id,effective_to);
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
        try:
            con.create_function('fold_text',1,fold_text,deterministic=True)
        except TypeError:
            con.create_function('fold_text',1,fold_text)
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
        with closing(self.connect()) as con:
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
            if current_version < 4:
                from .clients import infer_document_type, normalize_document_number
                legacy_clients = con.execute(
                    "SELECT id,document,created_at,updated_at FROM clients "
                    "WHERE document IS NOT NULL AND trim(document)<>''"
                ).fetchall()
                for client in legacy_clients:
                    exists = con.execute(
                        'SELECT 1 FROM client_documents WHERE client_id=? AND archived=0 LIMIT 1',
                        (client['id'],)
                    ).fetchone()
                    if exists:
                        continue
                    number = str(client['document']).strip()
                    normalized = normalize_document_number(number)
                    if not normalized:
                        continue
                    dtype = infer_document_type(number)
                    duplicate = con.execute(
                        'SELECT 1 FROM client_documents WHERE type=? AND normalized_number=? AND archived=0 LIMIT 1',
                        (dtype, normalized)
                    ).fetchone()
                    if duplicate:
                        continue
                    con.execute(
                        'INSERT INTO client_documents(id,client_id,type,number,normalized_number,is_primary,archived,created_at,updated_at) '
                        'VALUES(?,?,?,?,?,1,0,?,?)',
                        (os.urandom(16).hex(), client['id'], dtype, number, normalized, client['created_at'], client['updated_at'])
                    )
            if current_version < 5:
                fleet_cols = {r[1] for r in con.execute("PRAGMA table_info(fleets)").fetchall()}
                if 'client_company_id' not in fleet_cols:
                    con.execute("ALTER TABLE fleets ADD COLUMN client_company_id TEXT REFERENCES client_companies(id)")
                vehicle_cols = {r[1] for r in con.execute("PRAGMA table_info(vehicles)").fetchall()}
                for column, ddl in (
                    ('brand', 'TEXT'), ('model', 'TEXT'), ('year', 'INTEGER'),
                    ('contracted_on', 'TEXT'), ('review_on', 'TEXT')
                ):
                    if column not in vehicle_cols:
                        con.execute(f"ALTER TABLE vehicles ADD COLUMN {column} {ddl}")
                con.execute("""UPDATE fleets SET client_company_id=(
                    SELECT cc.id FROM client_companies cc
                    WHERE cc.client_id=fleets.client_id AND cc.archived=0
                    ORDER BY cc.is_primary DESC,cc.created_at,cc.id LIMIT 1
                ) WHERE client_company_id IS NULL""")
                con.execute("""UPDATE vehicles SET contracted_on=COALESCE(contracted_on,(
                    SELECT MIN(o.effective_from) FROM ownerships o WHERE o.vehicle_id=vehicles.id
                ),substr(created_at,1,10)) WHERE contracted_on IS NULL OR contracted_on=''""")
                con.execute("CREATE INDEX IF NOT EXISTS ix_fleets_company ON fleets(client_company_id,archived)")
                con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('fleet_max_active','100')")
            if current_version < 6:
                # R04: catalog UI becomes Planos/Produtos while legacy physical columns remain compatible.
                con.execute("UPDATE catalog SET category=CASE WHEN kind='PLAN' THEN 'MENSAL' ELSE 'AVULSA' END")
                rows = con.execute('SELECT id,cost_cents,created_at,updated_at FROM catalog').fetchall()
                for row in rows:
                    exists = con.execute('SELECT 1 FROM catalog_cost_components WHERE catalog_id=? LIMIT 1',(row['id'],)).fetchone()
                    if not exists:
                        con.execute(
                            'INSERT INTO catalog_cost_components(id,catalog_id,description,amount_cents,position,created_at,updated_at) VALUES(?,?,?,?,0,?,?)',
                            (os.urandom(16).hex(),row['id'],None,int(row['cost_cents'] or 0),row['created_at'],row['updated_at'])
                        )
            if current_version < 7:
                # R05 is additive: service coverage is distinct from monetary credits.
                pass
            if current_version < 8:
                # R08 attachments are additive; SCHEMA_SQL creates the table and indexes.
                pass
            if current_version < 9:
                # R11 subscription targets are additive; SCHEMA_SQL creates the table and indexes.
                pass
            if current_version < 10:
                # AJ-04 logical public codes: additive columns, registry, deterministic backfill, triggers.
                from .codes import migrate as migrate_logical_codes
                migrate_logical_codes(con)
            if current_version < 11:
                # AJ-05 fleet group: additive column; existing fleets stay MIXED (accept every category).
                fleet_cols = {r[1] for r in con.execute("PRAGMA table_info(fleets)").fetchall()}
                if 'vehicle_group' not in fleet_cols:
                    con.execute("ALTER TABLE fleets ADD COLUMN vehicle_group TEXT NOT NULL DEFAULT 'MIXED'")
                con.execute("CREATE INDEX IF NOT EXISTS ix_fleets_group ON fleets(client_company_id,vehicle_group,archived)")
            if current_version < 12:
                # AJ-13 expenses: repetition (Mensal/Anual/Única), active recurrence flag, conversion to direct sale.
                expense_cols = {r[1] for r in con.execute("PRAGMA table_info(expenses)").fetchall()}
                if 'repeat' not in expense_cols:
                    con.execute("ALTER TABLE expenses ADD COLUMN repeat TEXT NOT NULL DEFAULT 'ONCE'")
                if 'repeat_active' not in expense_cols:
                    con.execute("ALTER TABLE expenses ADD COLUMN repeat_active INTEGER NOT NULL DEFAULT 0")
                if 'converted_sale_id' not in expense_cols:
                    con.execute("ALTER TABLE expenses ADD COLUMN converted_sale_id TEXT")
                # legacy recurrences generated by EXPENSE_RECUR_GENERATE were monthly
                con.execute("UPDATE expenses SET repeat='MONTHLY' WHERE recurrence_id IS NOT NULL AND repeat='ONCE'")
                con.execute("CREATE INDEX IF NOT EXISTS ix_expenses_repeat ON expenses(repeat,repeat_active)")
            if current_version < 13:
                # C-09 Lixeira (14 dias): one row per in-system deletion; payload wiped on purge.
                con.execute('''CREATE TABLE IF NOT EXISTS trash(
                    id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, label TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}', deleted_at TEXT NOT NULL, purge_after TEXT NOT NULL,
                    restored_at TEXT, purged_at TEXT, actor_slot INTEGER)''')
                con.execute("CREATE INDEX IF NOT EXISTS ix_trash_due ON trash(purged_at,restored_at,purge_after)")
            if current_version < 14:
                # V-01: no orphan fleets/vehicles — archived clients take their fleets and vehicles with them.
                ts = datetime.now(timezone.utc).isoformat()
                con.execute("UPDATE vehicles SET archived=1,revision=revision+1,updated_at=? WHERE archived=0 AND client_id IN (SELECT id FROM clients WHERE archived=1)", (ts,))
                con.execute("UPDATE fleets SET archived=1,revision=revision+1,updated_at=? WHERE archived=0 AND client_id IN (SELECT id FROM clients WHERE archived=1)", (ts,))
                con.execute("UPDATE ownerships SET effective_to=? WHERE effective_to IS NULL AND vehicle_id IN (SELECT id FROM vehicles WHERE archived=1)", (ts[:10],))
            # R23: indexes on tables created by migrations (idempotent, every open)
            con.execute("CREATE INDEX IF NOT EXISTS ix_logical_codes_client ON logical_codes(client_id,code)")
            con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            con.commit()

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
        with closing(self.connect()) as con:
            return con.execute(sql, args).fetchall()

    def one(self, sql: str, args=()):
        with closing(self.connect()) as con:
            return con.execute(sql, args).fetchone()
