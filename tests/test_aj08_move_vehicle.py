import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle, move_vehicle
from ustracker.services import create_catalog, create_client, create_client_company, create_subscription

TODAY = date.today()


class AJ08MoveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.n = 0
        self.a, self.ca = self._client('Alfa')
        self.b, self.cb = self._client('Beta')
        self.fleet_a = create_fleet(self.db, 1, {'client_id': self.a['id'], 'client_company_id': self.ca['id'], 'name': 'Frota A', 'vehicle_group': 'CAR'})
        self.trucks_a = create_fleet(self.db, 1, {'client_id': self.a['id'], 'client_company_id': self.ca['id'], 'name': 'Caminhões', 'vehicle_group': 'TRUCK'})
        self.fleet_b = create_fleet(self.db, 1, {'client_id': self.b['id'], 'client_company_id': self.cb['id'], 'name': 'Frota B'})
        self.v = create_vehicle(self.db, 1, {'client_id': self.a['id'], 'plate': 'AAA1A11', 'type': 'Carro', 'brand': 'M', 'model': 'X', 'year': 2026})

    def tearDown(self):
        self.tmp.cleanup()

    def _client(self, name):
        self.n += 1
        c = create_client(self.db, 1, {'legal_name': name, 'email': f'{self.n}@example.test',
                                       'documents': [{'type': 'RG', 'number': f'RG-AJ08-{self.n}', 'is_primary': True}]})
        return c, create_client_company(self.db, 1, c['id'], {'legal_name': f'Empresa {name}', 'is_primary': True})

    def row(self):
        return self.db.one('SELECT client_id,fleet_id,code FROM vehicles WHERE id=?', (self.v['id'],))

    def test_particular_to_fleet_and_back_same_client(self):
        move_vehicle(self.db, 1, self.v['id'], {'fleet_id': self.fleet_a['id']}, as_of=TODAY)
        self.assertEqual(self.row()['fleet_id'], self.fleet_a['id'])
        move_vehicle(self.db, 1, self.v['id'], {'fleet_id': ''}, as_of=TODAY)
        self.assertIsNone(self.row()['fleet_id'])
        self.assertEqual(self.row()['code'], 'CLI-0001-V01')

    def test_group_mismatch_and_noop_are_refused(self):
        with self.assertRaises(ValueError):
            move_vehicle(self.db, 1, self.v['id'], {'fleet_id': self.trucks_a['id']}, as_of=TODAY)
        with self.assertRaises(ValueError):
            move_vehicle(self.db, 1, self.v['id'], {}, as_of=TODAY)
        with self.assertRaises(ValueError):
            move_vehicle(self.db, 1, self.v['id'], {'fleet_id': self.fleet_a['id'], 'effective_from': (TODAY + timedelta(days=1)).isoformat()}, as_of=TODAY)

    def test_other_client_fleet_reissues_code_and_detaches_subscription(self):
        plan = create_catalog(self.db, 1, {'description': 'P', 'category': 'Mensal', 'price': '10,00'})
        sub = create_subscription(self.db, 1, {'client_id': self.a['id'], 'start_on': '2026-10-01', 'target_vehicle_ids': [self.v['id']],
                                               'items': [{'catalog_id': plan['id'], 'quantity': 1}]})
        result = move_vehicle(self.db, 1, self.v['id'], {'client_id': self.b['id'], 'fleet_id': self.fleet_b['id']}, as_of=TODAY)
        self.assertEqual(result['removed_from_subscriptions'], [sub['code']])
        self.assertEqual(self.row()['client_id'], self.b['id'])
        self.assertEqual(self.row()['code'], 'CLI-0002-V01')
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM ownerships WHERE vehicle_id=? AND effective_to IS NULL', (self.v['id'],))[0], 1)
        self.assertEqual(self.db.one("SELECT COUNT(*) FROM vehicle_transfer_cases WHERE vehicle_id=? AND status='COMPLETED'", (self.v['id'],))[0], 1)


if __name__ == '__main__':
    unittest.main()
