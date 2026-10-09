import os, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import (create_fleet, create_transfer_case, create_vehicle, list_mobility,
                                mobility_subscription_detail, update_fleet)
from ustracker.services import client_profile, create_catalog, create_client, create_client_company, create_subscription


class AJ05FleetGroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'João', 'email': 'j@example.test',
                                                  'documents': [{'type': 'RG', 'number': 'RG-AJ05-001', 'is_primary': True}]})
        self.company = create_client_company(self.db, 1, self.client['id'], {'legal_name': 'UsLog', 'is_primary': True})
        self.trucks = create_fleet(self.db, 1, {'client_id': self.client['id'], 'client_company_id': self.company['id'],
                                                'name': 'Frota A', 'vehicle_group': 'TRUCK'})
        self.cars = create_fleet(self.db, 1, {'client_id': self.client['id'], 'client_company_id': self.company['id'],
                                              'name': 'Frota B', 'vehicle_group': 'CAR'})
        self.mixed = create_fleet(self.db, 1, {'client_id': self.client['id'], 'client_company_id': self.company['id'], 'name': 'Frota C'})

    def tearDown(self):
        self.tmp.cleanup()

    def _vehicle(self, plate, vtype, fleet=None):
        return create_vehicle(self.db, 1, {'client_id': self.client['id'], 'fleet_id': fleet, 'plate': plate, 'type': vtype,
                                           'brand': 'M', 'model': 'X', 'year': 2024})

    def test_group_is_enforced_and_mixed_accepts_all(self):
        self.assertEqual(self.mixed['vehicle_group'], 'MIXED')
        self._vehicle('TRK0001', 'Caminhão', self.trucks['id'])
        with self.assertRaisesRegex(ValueError, 'does not match fleet group'):
            self._vehicle('CAR0001', 'Carro', self.trucks['id'])
        self._vehicle('CAR0002', 'Carro', self.mixed['id'])
        self._vehicle('BOA0001', 'Lancha', self.mixed['id'])
        with self.assertRaisesRegex(ValueError, 'another category'):
            update_fleet(self.db, 1, self.mixed['id'], {'expected_revision': 1, 'vehicle_group': 'CAR'})
        with self.assertRaises(ValueError):
            create_fleet(self.db, 1, {'client_id': self.client['id'], 'client_company_id': self.company['id'],
                                      'name': 'X', 'vehicle_group': 'NAVE'})

    def test_transfer_into_group_checks_category(self):
        car = self._vehicle('CAR0003', 'Carro')
        with self.assertRaisesRegex(ValueError, 'does not match fleet group'):
            create_transfer_case(self.db, 1, car['id'], {'client_id': self.client['id'], 'fleet_id': self.trucks['id'],
                                                          'expected_revision': 1})

    def test_hierarchy_totals_and_filters(self):
        self._vehicle('TRK0002', 'Caminhão', self.trucks['id'])
        self._vehicle('TRK0003', 'Caminhão', self.trucks['id'])
        self._vehicle('CAR0004', 'Carro', self.cars['id'])
        self._vehicle('CAR0005', 'Carro')
        data = list_mobility(self.db)
        node = data['hierarchy'][0]
        self.assertEqual((node['total'], node['particulars']), (4, 1))
        company = node['companies'][0]
        self.assertEqual(company['total'], 3)
        frota_a = next(f for f in company['fleets'] if f['fleet_name'] == 'Frota A')
        self.assertEqual((frota_a['vehicle_group_label'], frota_a['total'], frota_a['groups'][0]['label']), ('Caminhões', 2, 'Caminhões'))
        self.assertEqual(sum(c['total'] for c in node['companies']) + node['particulars'], node['total'])
        trucks_only = list_mobility(self.db, group='TRUCK')
        self.assertEqual({v['plate'] for v in trucks_only['particulars']}, set())
        self.assertEqual([f['name'] for f in trucks_only['fleets']], ['Frota A'])
        by_company = list_mobility(self.db, company_id=self.company['id'])
        self.assertEqual(by_company['particulars'], [])
        self.assertEqual(client_profile(self.db, self.client['id'])['mobility']['hierarchy'][0]['total'], 4)


class AJ06SubscriptionDetailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Ana', 'email': 'a@example.test',
                                                  'documents': [{'type': 'RG', 'number': 'RG-AJ06-001', 'is_primary': True}]})
        company = create_client_company(self.db, 1, self.client['id'], {'legal_name': 'Empresa', 'is_primary': True})
        self.fleet = create_fleet(self.db, 1, {'client_id': self.client['id'], 'client_company_id': company['id'], 'name': 'F'})
        self.vehicle = create_vehicle(self.db, 1, {'client_id': self.client['id'], 'fleet_id': self.fleet['id'], 'plate': 'AJ6A001',
                                                   'type': 'Carro', 'brand': 'M', 'model': 'X', 'year': 2024})
        self.plan = create_catalog(self.db, 1, {'description': 'Plano', 'category': 'Mensal', 'price': '100.00'})

    def tearDown(self):
        self.tmp.cleanup()

    def test_count_matches_detail_without_duplicates(self):
        create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-10-01',
                                         'items': [{'catalog_id': self.plan['id'], 'quantity': 2}],
                                         'target_vehicle_ids': [self.vehicle['id']], 'target_fleet_ids': [self.fleet['id']]})
        data = list_mobility(self.db)
        fleet = data['fleets'][0]
        self.assertEqual(fleet['subscriptions_count'], 1)
        detail = mobility_subscription_detail(self.db, fleet_id=self.fleet['id'])
        self.assertEqual((detail['active_count'], len(detail['items'])), (1, 1))
        item = detail['items'][0]
        self.assertEqual((item['code'], item['monthly_cents'], item['plans'][0]['quantity']), ('CLI-0001-A01', 20000, 2))
        vdetail = mobility_subscription_detail(self.db, vehicle_id=self.vehicle['id'])
        self.assertEqual((vdetail['active_count'], vdetail['items'][0]['target_scope']), (1, 'DIRECT'))  # 2.7.0: frota com 1 veículo → assinatura do veículo
        self.assertEqual(vdetail['target']['category_label'], 'Carro')


if __name__ == '__main__':
    unittest.main()
