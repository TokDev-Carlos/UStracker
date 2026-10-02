import os
import json
import sys
import tempfile
import unittest
import importlib.util
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.services import create_catalog, create_client, create_subscription, dashboard


class R2BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {
            'legal_name': 'Cliente R2', 'email': 'cliente@example.test',
            'documents': [{'type': 'RG', 'number': 'TEST001', 'is_primary': True}],
        })
        self.plan_catalog = create_catalog(self.db, 1, {
            'description': 'Plano R2', 'category': 'Mensal', 'price': '120.00', 'cost': '0.00',
        })
        self.catalog = create_catalog(self.db, 1, {
            'description': 'Produto R2', 'category': 'Avulsa', 'price': '120.00', 'cost': '0.00',
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema3_migrates_annual_legacy_subscription(self):
        create_subscription(self.db, 1, {
            'client_id': self.client['id'], 'start_on': '2026-01-01',
            'billing_interval_months': 12,
            'items': [{'catalog_id': self.plan_catalog['id'], 'quantity': 1}],
        })
        with self.db.transaction() as con:
            con.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
        upgraded = Database(Path(self.tmp.name), 'test', b'0' * 32)
        row = upgraded.one('SELECT billing_cycle FROM subscriptions')
        self.assertEqual(row[0], 'ANNUAL')
        self.assertEqual(upgraded.one("SELECT value FROM meta WHERE key='schema_version'")[0], '8')
        self.assertIsNotNone(upgraded.one("SELECT name FROM sqlite_master WHERE name='direct_sales'"))

    def test_package_metadata_is_synchronized_from_canonical_version(self):
        root = Path(__file__).parents[1]
        version = json.loads((root / 'VERSION.json').read_text(encoding='utf-8'))
        current = json.loads((root / 'current.json').read_text(encoding='utf-8'))
        self.assertEqual((version['schema_version'], current['schema_version']), (8, 8))
        canonical = (root / 'version.md').read_text(encoding='utf-8').strip()
        self.assertEqual((version['version'], current['version']), (canonical, canonical))

    @unittest.skipUnless(importlib.util.find_spec('sqlcipher3'), 'sqlcipher3 unavailable in this environment')
    def test_schema3_alters_actual_legacy_table_without_billing_cycle(self):
        import sqlcipher3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_dir = root / 'UserData' / 'Test'
            db_dir.mkdir(parents=True)
            con = sqlcipher3.connect(str(db_dir / 'ustracker.db'))
            con.execute(f"PRAGMA key=\"x'{(b'0' * 32).hex()}'\"")
            con.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            con.execute("INSERT INTO meta VALUES('schema_version','2')")
            con.execute('''CREATE TABLE subscriptions(
                id TEXT PRIMARY KEY, client_id TEXT NOT NULL, signed_on TEXT NOT NULL,
                start_on TEXT NOT NULL, end_on TEXT, due_day INTEGER NOT NULL,
                billing_interval_months INTEGER NOT NULL DEFAULT 1,
                renewal_mode TEXT NOT NULL DEFAULT 'MANUAL', lifecycle_status TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )''')
            con.execute("INSERT INTO subscriptions(id,client_id,signed_on,start_on,due_day,billing_interval_months,lifecycle_status,created_at,updated_at) VALUES('legacy','client','2025-01-01','2025-01-01',10,12,'ACTIVE','2025-01-01','2025-01-01')")
            con.commit()
            con.close()
            upgraded = Database(root, 'test', b'0' * 32)
            self.assertEqual(upgraded.one("SELECT billing_cycle FROM subscriptions WHERE id='legacy'")[0], 'ANNUAL')

    def test_direct_sale_tracks_items_total_and_status(self):
        from ustracker.services import create_direct_sale, set_direct_sale_status, list_direct_sales
        sale = create_direct_sale(self.db, 1, {
            'client_id': self.client['id'], 'sold_on': '2026-05-03',
            'items': [{'catalog_id': self.catalog['id'], 'quantity': 2}],
        })
        self.assertEqual(sale['total_cents'], 24000)
        self.assertEqual(sale['items'][0]['description'], 'Produto R2')
        paid = set_direct_sale_status(self.db, 1, sale['id'], {
            'status': 'PAID', 'paid_on': '2026-05-04', 'expected_revision': 1,
        })
        self.assertEqual((paid['status'], paid['paid_on'], paid['revision']), ('PAID', '2026-05-04', 2))
        self.assertEqual(list_direct_sales(self.db)[0]['item_count'], 1)
        with self.assertRaises(ValueError):
            set_direct_sale_status(self.db, 1, sale['id'], {'status': 'OPEN', 'expected_revision': 1})

    def test_direct_sale_rejects_vehicle_from_other_client(self):
        from ustracker.services import create_direct_sale, create_vehicle
        other = create_client(self.db, 1, {'legal_name': 'Outro Cliente', 'phone': '21999990000', 'documents': [{'type': 'RG', 'number': 'TEST002', 'is_primary': True}]})
        vehicle = create_vehicle(self.db, 1, {
            'client_id': other['id'], 'plate': 'ABC1234', 'type': 'Carro', 'brand': 'Marca', 'model': 'Modelo', 'year': 2026,
        })
        with self.assertRaises(ValueError):
            create_direct_sale(self.db, 1, {
                'client_id': self.client['id'], 'sold_on': '2026-05-03',
                'items': [{'catalog_id': self.catalog['id'], 'vehicle_id': vehicle['id'], 'quantity': 1}],
            })

    def test_dashboard_uses_realized_month_and_prior_months_only(self):
        from ustracker.services import create_direct_sale
        create_subscription(self.db, 1, {
            'client_id': self.client['id'], 'start_on': '2026-01-01',
            'billing_cycle': 'MONTHLY',
            'items': [{'catalog_id': self.plan_catalog['id'], 'quantity': 2}],
        })
        create_direct_sale(self.db, 1, {
            'client_id': self.client['id'], 'sold_on': '2026-04-15',
            'status': 'PAID', 'paid_on': '2026-05-01',
            'items': [{'catalog_id': self.catalog['id'], 'quantity': 1}],
        })
        with self.db.transaction() as con:
            con.execute("INSERT INTO payments(id,client_id,paid_on,amount_cents,created_at) VALUES('p1',?,'2026-04-09',5000,'2026-04-09')", (self.client['id'],))
            con.execute("INSERT INTO payments(id,client_id,paid_on,amount_cents,reversed_at,created_at) VALUES('p2',?,'2026-05-02',9000,'2026-05-03','2026-05-02')", (self.client['id'],))
            con.execute("INSERT INTO expenses(id,category,description,competence,expected_amount_cents,created_at,updated_at) VALUES('e1','X','Gasto','2026-05',10000,'2026-05-01','2026-05-01')")
            con.execute("INSERT INTO disbursements(id,expense_id,paid_on,amount_cents,created_at) VALUES('d1','e1','2026-05-03',3000,'2026-05-03')")
        result = dashboard(self.db, as_of=date(2026, 5, 15))
        self.assertEqual((result['monthly_value_cents'], result['monthly_spent_cents'], result['real_profit_cents']), (12000, 3000, 9000))
        self.assertEqual(result['accumulated_profit_cents'], 5000)
        self.assertEqual(result['active_subscription_products'], 2)
        self.assertEqual(result['client_overview'][0]['subscription_monthly_cents'], 24000)
        self.assertEqual(dashboard(self.db, as_of=date(2027, 1, 1))['accumulated_profit_cents'], 0)

    def test_subscription_daily_cycle_is_stored_with_legacy_zero(self):
        rec = create_subscription(self.db, 1, {
            'client_id': self.client['id'], 'start_on': '2026-05-01',
            'billing_cycle': 'DAILY',
            'items': [{'catalog_id': self.plan_catalog['id'], 'quantity': 1}],
        })
        self.assertEqual((rec['billing_cycle'], rec['billing_interval_months']), ('DAILY', 0))

    def test_client_profile_collects_related_records_and_paid_totals(self):
        from ustracker.services import client_profile, create_direct_sale, create_vehicle
        vehicle = create_vehicle(self.db, 1, {
            'client_id': self.client['id'], 'plate': 'DEF5678', 'type': 'Carro', 'brand': 'Marca', 'model': 'Modelo', 'year': 2026,
        })
        create_subscription(self.db, 1, {
            'client_id': self.client['id'], 'start_on': '2026-05-01',
            'items': [{'catalog_id': self.plan_catalog['id'], 'quantity': 1}],
        })
        create_direct_sale(self.db, 1, {
            'client_id': self.client['id'], 'sold_on': '2026-05-01', 'status': 'PAID',
            'items': [{'catalog_id': self.catalog['id'], 'quantity': 1}],
        })
        with self.db.transaction() as con:
            con.execute("INSERT INTO payments(id,client_id,paid_on,amount_cents,created_at) VALUES('profile-payment',?,'2026-05-01',2000,'2026-05-01')", (self.client['id'],))
            con.execute("INSERT INTO expenses(id,category,description,competence,expected_amount_cents,client_id,created_at,updated_at) VALUES('profile-expense','X','Gasto','2026-05',1000,?,'2026-05-01','2026-05-01')", (self.client['id'],))
            con.execute("INSERT INTO disbursements(id,expense_id,paid_on,amount_cents,created_at) VALUES('profile-disb','profile-expense','2026-05-01',1000,'2026-05-01')")
        profile = client_profile(self.db, self.client['id'])
        self.assertEqual(profile['vehicles'][0]['id'], vehicle['id'])
        self.assertEqual(len(profile['subscriptions'][0]['subscription_items']), 1)
        self.assertEqual(len(profile['direct_sales'][0]['direct_sale_items']), 1)
        self.assertEqual(profile['financial'], {
            'subscription_received_cents': 2000,
            'direct_sales_paid_cents': 12000,
            'client_expenses_paid_cents': 1000,
            'client_expenses_generated_cents': 1000,
            'generated_total_cents': 13000,
        })
        with self.assertRaises(KeyError):
            client_profile(self.db, 'missing-client')


if __name__ == '__main__':
    unittest.main()
