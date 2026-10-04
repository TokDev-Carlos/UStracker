import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_vehicle, list_mobility
from ustracker.overview import client_activity_overview
from ustracker.projections import month_forecast
from ustracker.services import (client_profile, create_catalog, create_client, create_direct_sale, create_payment,
                                create_subscription, dashboard, generate_charge, list_clients)
from ustracker.vehicle_types import normalize_vehicle_category


class AJ02VehicleCategoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Alfa', 'email': 'a@example.test',
                                                  'documents': [{'type': 'RG', 'number': 'RG-AJ02-001', 'is_primary': True}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_normalization_maps_equivalents_and_keeps_custom_as_other(self):
        self.assertEqual(normalize_vehicle_category('CAMINHÃO'), 'TRUCK')
        self.assertEqual(normalize_vehicle_category(' lancha '), 'BOAT')
        self.assertEqual(normalize_vehicle_category('Avião'), 'AIRCRAFT')
        self.assertEqual(normalize_vehicle_category('Carro'), 'CAR')
        self.assertEqual(normalize_vehicle_category('Trator'), 'OTHER')

    def test_total_is_exact_sum_of_five_categories_and_type_text_is_kept(self):
        for index, vtype in enumerate(['Carro', 'Carro', 'Caminhão', 'Lancha', 'Aeronave', 'Trator']):
            create_vehicle(self.db, 1, {'client_id': self.client['id'], 'plate': f'AJ0{index}A11', 'type': vtype,
                                        'brand': 'M', 'model': 'X', 'year': 2026})
        breakdown = dashboard(self.db)['vehicle_breakdown']
        counts = {c['key']: c['count'] for c in breakdown['categories']}
        self.assertEqual(counts, {'CAR': 2, 'TRUCK': 1, 'BOAT': 1, 'AIRCRAFT': 1, 'OTHER': 1})
        self.assertEqual(breakdown['total'], sum(counts.values()))
        self.assertEqual([c['key'] for c in breakdown['categories']], ['CAR', 'TRUCK', 'BOAT', 'AIRCRAFT', 'OTHER'])
        self.assertIn('Trator', breakdown['categories'][4]['custom_types'])
        trator = [v for v in list_mobility(self.db)['particulars'] if v['type'] == 'Trator'][0]
        self.assertEqual((trator['category'], trator['category_label']), ('OTHER', 'Outro'))
        self.assertEqual(client_profile(self.db, self.client['id'])['summary']['vehicle_breakdown']['total'], 6)


class AJ03AJ01ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Beta', 'email': 'b@example.test',
                                                  'documents': [{'type': 'RG', 'number': 'RG-AJ03-001', 'is_primary': True}]})
        self.plan = create_catalog(self.db, 1, {'description': 'Plano', 'category': 'Mensal', 'price': '100.00'})
        self.item = create_catalog(self.db, 1, {'description': 'Instalação', 'category': 'Avulsa', 'price': '50.00'})
        self.today = date.today()
        self.month_start = self.today.replace(day=1).isoformat()

    def tearDown(self):
        self.tmp.cleanup()

    def _overview(self):
        return client_activity_overview(self.db)[0]

    def test_unpaid_subscription_is_contracted_and_forecast_but_not_revenue(self):
        create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': self.month_start,
                                         'items': [{'catalog_id': self.plan['id'], 'quantity': 1}]})
        row = self._overview()
        self.assertEqual((row['contracted_active_cents'], row['realized_revenue_cents']), (10000, 0))
        summary = dashboard(self.db)
        self.assertEqual(summary['period']['revenue_cents'], 0)
        self.assertEqual(summary['period']['result_cents'], 0)
        self.assertEqual(summary['month_forecast']['forecast_cents'], 10000)
        self.assertEqual(list_clients(self.db)[0]['contracted_active_cents'], 10000)
        self.assertEqual(client_profile(self.db, self.client['id'])['summary']['contracted_active_cents'], 10000)

    def test_payment_updates_revenue_result_client_and_forecast_is_not_doubled(self):
        sub = create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': self.month_start,
                                               'items': [{'catalog_id': self.plan['id'], 'quantity': 1}]})
        charge = generate_charge(self.db, 1, sub['id'], self.today.strftime('%Y-%m'))
        create_payment(self.db, 1, {'client_id': self.client['id'], 'paid_on': self.today.isoformat(), 'amount': '100.00',
                                    'allocations': [{'charge_id': charge['id'], 'amount': '100.00'}]})
        summary = dashboard(self.db)
        self.assertEqual((summary['period']['revenue_cents'], summary['period']['result_cents']), (10000, 10000))
        self.assertEqual(summary['month_forecast']['forecast_cents'], 10000)
        self.assertEqual(summary['month_forecast']['received_in_month_cents'], 10000)
        self.assertEqual(self._overview()['realized_revenue_cents'], 10000)

    def test_future_payment_and_open_purchase_are_not_realized(self):
        create_payment(self.db, 1, {'client_id': self.client['id'], 'paid_on': '2999-01-01', 'amount': '30.00', 'create_credit': True})
        create_direct_sale(self.db, 1, {'client_id': self.client['id'], 'sold_on': self.today.isoformat(),
                                        'items': [{'catalog_id': self.item['id'], 'quantity': 1}]})
        row = self._overview()
        self.assertEqual((row['realized_revenue_cents'], row['open_purchases_cents']), (0, 5000))
        self.assertEqual(dashboard(self.db)['period']['revenue_cents'], 0)
        self.assertEqual(month_forecast(self.db)['direct_sales_cents'], 5000)


if __name__ == '__main__':
    unittest.main()
