"""V-01 sem frota/veículo órfão + exclusão individual; V-02 placa já cadastrada."""
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle, list_mobility
from ustracker.mobility_delete import PlateExists, check_plate, delete_fleet, delete_vehicle
from ustracker.services import archive_clients, create_catalog, create_client, create_client_company, create_subscription
from ustracker.trash import list_trash, restore


class V01V02(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.n = 0
        self.c, self.cc = self._client('Alfa')

    def tearDown(self):
        self.tmp.cleanup()

    def _client(self, name):
        self.n += 1
        c = create_client(self.db, 1, {'legal_name': name, 'email': f'{self.n}@x.test', 'documents': [{'type': 'RG', 'number': f'RG-V01-{self.n}', 'is_primary': True}]})
        return c, create_client_company(self.db, 1, c['id'], {'legal_name': f'Emp {name}', 'is_primary': True})

    def vehicle(self, plate, client=None, fleet=None):
        return create_vehicle(self.db, 1, {'client_id': (client or self.c)['id'], 'plate': plate, 'type': 'Carro', 'brand': 'Fiat', 'model': 'Uno', 'year': 2020, 'fleet_id': fleet or ''})

    def active(self, table):
        return self.db.one(f'SELECT COUNT(*) FROM {table} WHERE archived=0')[0]

    def test_plate_exists_returns_owner(self):
        self.vehicle('ABC1D23')
        other, _ = self._client('Beta')
        with self.assertRaises(PlateExists) as ctx:
            self.vehicle('abc-1d23', client=other)
        self.assertEqual(ctx.exception.info['client_name'], 'Alfa')
        self.assertEqual(ctx.exception.info['plate'], 'ABC1D23')
        out = check_plate(self.db, 'abc 1d23')
        self.assertTrue(out['exists']); self.assertEqual(out['vehicle']['brand'], 'Fiat')
        self.assertFalse(check_plate(self.db, 'ZZZ9Z99')['exists'])

    def test_archive_client_takes_fleets_and_vehicles_and_restores(self):
        fleet = create_fleet(self.db, 1, {'client_id': self.c['id'], 'client_company_id': self.cc['id'], 'name': 'F1', 'vehicle_group': 'CAR'})
        self.vehicle('AAA1A11', fleet=fleet['id']); self.vehicle('BBB2B22')
        archive_clients(self.db, 1, [self.c['id']])
        self.assertEqual(self.active('vehicles'), 0); self.assertEqual(self.active('fleets'), 0)
        lst = list_mobility(self.db)
        self.assertEqual(lst['particulars'], []); self.assertEqual(lst['fleets'], [])
        self.assertFalse(check_plate(self.db, 'AAA1A11')['exists'], 'placa liberada')
        item = [i for i in list_trash(self.db) if i['entity_type'] == 'client'][0]
        restore(self.db, 1, item['id'])
        self.assertEqual(self.active('vehicles'), 2); self.assertEqual(self.active('fleets'), 1)

    def test_delete_vehicle_and_fleet_modes(self):
        fleet = create_fleet(self.db, 1, {'client_id': self.c['id'], 'client_company_id': self.cc['id'], 'name': 'F1', 'vehicle_group': 'CAR'})
        v1 = self.vehicle('AAA1A11', fleet=fleet['id']); v2 = self.vehicle('BBB2B22')
        delete_vehicle(self.db, 1, v2['id'])
        self.assertEqual(self.active('vehicles'), 1)
        self.assertEqual(list_trash(self.db)[0]['kind_label'], 'Veículo')
        out = delete_fleet(self.db, 1, fleet['id'])  # detach: vehicle becomes Particular
        self.assertEqual(out['vehicles_detached'], 1)
        self.assertIsNone(self.db.one('SELECT fleet_id FROM vehicles WHERE id=?', (v1['id'],))[0])
        fleet_item = [i for i in list_trash(self.db) if i['entity_type'] == 'fleet'][0]
        restore(self.db, 1, fleet_item['id'])
        self.assertEqual(self.db.one('SELECT fleet_id FROM vehicles WHERE id=?', (v1['id'],))[0], fleet['id'])
        out = delete_fleet(self.db, 1, fleet['id'], 'with_vehicles')
        self.assertEqual(out['vehicles_deleted'], 1); self.assertEqual(self.active('vehicles'), 0)
        # restoring a vehicle whose plate was reused is refused with a clear message
        veh_item = [i for i in list_trash(self.db) if i['entity_type'] == 'vehicle'][0]
        self.vehicle('BBB2B22')
        with self.assertRaises(ValueError):
            restore(self.db, 1, veh_item['id'])

    def test_active_subscription_blocks_delete(self):
        v = self.vehicle('CCC3C33')
        plan = create_catalog(self.db, 1, {'description': 'P', 'category': 'Mensal', 'price': '10,00'})
        create_subscription(self.db, 1, {'client_id': self.c['id'], 'start_on': '2026-10-01', 'target_vehicle_ids': [v['id']], 'items': [{'catalog_id': plan['id'], 'quantity': 1}]})
        with self.assertRaises(ValueError) as ctx:
            delete_vehicle(self.db, 1, v['id'])
        self.assertIn('assinatura', str(ctx.exception))

if __name__ == '__main__':
    unittest.main()
