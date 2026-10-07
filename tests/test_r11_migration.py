import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle
from ustracker.services import create_catalog, create_client, create_client_company, create_subscription


class R11MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'test', b'0' * 32)
        self.integrity_error = self.db._module()[0].IntegrityError

    def tearDown(self):
        self.tmp.cleanup()

    def _relationships(self):
        client = create_client(self.db, 1, {
            'legal_name': 'Cliente R11',
            'email': 'r11@example.test',
            'documents': [{'type': 'RG', 'number': 'R11-MIGRATION', 'is_primary': True}],
        })
        company = create_client_company(self.db, 1, client['id'], {
            'legal_name': 'Empresa R11', 'is_primary': True,
        })
        fleet = create_fleet(self.db, 1, {
            'client_id': client['id'], 'client_company_id': company['id'], 'name': 'Frota R11',
        })
        vehicle = create_vehicle(self.db, 1, {
            'client_id': client['id'], 'fleet_id': fleet['id'], 'plate': 'RAB1A11',
            'type': 'Carro', 'brand': 'Marca', 'model': 'Modelo', 'year': 2026,
        })
        plan = create_catalog(self.db, 1, {
            'description': 'Plano Mensal R11', 'category': 'Mensal', 'price': '100.00', 'cost': '0.00',
        })
        subscription = create_subscription(self.db, 1, {
            'client_id': client['id'], 'start_on': '2026-10-01',
            'items': [{'catalog_id': plan['id'], 'quantity': 1}],
        })
        return subscription, vehicle, fleet

    def test_schema8_migrates_to_schema9_reentrantly_and_preserves_legacy_subscription(self):
        subscription, _, _ = self._relationships()
        with self.db.transaction() as con:
            con.execute("UPDATE meta SET value='8' WHERE key='schema_version'")

        first = Database(self.root, 'test', b'0' * 32)
        second = Database(self.root, 'test', b'0' * 32)

        self.assertEqual(second.one("SELECT value FROM meta WHERE key='schema_version'")[0], '15')
        self.assertIsNotNone(second.one("SELECT name FROM sqlite_master WHERE type='table' AND name='subscription_targets'"))
        self.assertEqual(second.one('SELECT id FROM subscriptions WHERE id=?', (subscription['id'],))[0], subscription['id'])
        self.assertEqual(first.one('SELECT COUNT(*) FROM subscription_targets')[0], 0)

    def test_subscription_target_requires_exactly_one_unique_target_and_cascades(self):
        subscription, vehicle, fleet = self._relationships()
        created_at = '2026-10-02T00:00:00+00:00'
        with self.db.transaction() as con:
            con.execute(
                'INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                (uuid.uuid4().hex, subscription['id'], vehicle['id'], None, created_at),
            )
            con.execute(
                'INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                (uuid.uuid4().hex, subscription['id'], None, fleet['id'], created_at),
            )

        for vehicle_id, fleet_id in ((None, None), (vehicle['id'], fleet['id'])):
            with self.assertRaises(self.integrity_error):
                with self.db.transaction() as con:
                    con.execute(
                        'INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                        (uuid.uuid4().hex, subscription['id'], vehicle_id, fleet_id, created_at),
                    )

        with self.assertRaises(self.integrity_error):
            with self.db.transaction() as con:
                con.execute(
                    'INSERT INTO subscription_targets(id,subscription_id,vehicle_id,fleet_id,created_at) VALUES(?,?,?,?,?)',
                    (uuid.uuid4().hex, subscription['id'], vehicle['id'], None, created_at),
                )

        with self.db.transaction() as con:
            con.execute('DELETE FROM subscriptions WHERE id=?', (subscription['id'],))
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM subscription_targets')[0], 0)


if __name__ == '__main__':
    unittest.main()
