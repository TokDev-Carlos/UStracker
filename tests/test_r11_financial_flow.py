import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.commercial import commercial_snapshot
from ustracker.db import Database
from ustracker.finance import finance_snapshot
from ustracker.mobility import create_fleet, create_vehicle
from ustracker.overview import client_activity_overview
from ustracker.services import (
    create_catalog,
    create_client,
    create_client_company,
    create_payment,
    create_subscription,
    dashboard,
    generate_charge,
    reverse_payment,
)


class R11FinancialFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {
            'legal_name': 'Cliente Financeiro R11', 'email': 'financeiro-r11@example.test',
            'documents': [{'type': 'RG', 'number': 'R11-FINANCE', 'is_primary': True}],
        })
        company = create_client_company(self.db, 1, self.client['id'], {
            'legal_name': 'Empresa Financeira R11', 'is_primary': True,
        })
        fleet = create_fleet(self.db, 1, {
            'client_id': self.client['id'], 'client_company_id': company['id'], 'name': 'Frota Financeira R11',
        })
        self.vehicle = create_vehicle(self.db, 1, {
            'client_id': self.client['id'], 'fleet_id': fleet['id'], 'plate': 'FIN1A11',
            'type': 'Carro', 'brand': 'Marca', 'model': 'Modelo', 'year': 2026,
        })
        self.plan = create_catalog(self.db, 1, {
            'description': 'Plano Financeiro R11', 'category': 'Mensal', 'price': '125.00',
        })

    def tearDown(self):
        self.tmp.cleanup()

    def test_payment_flows_once_to_finance_and_overview_then_reversal_removes_it(self):
        subscription = create_subscription(self.db, 1, {
            'client_id': self.client['id'], 'start_on': '2026-10-01',
            'items': [{'catalog_id': self.plan['id'], 'quantity': 1}],
            'target_vehicle_ids': [self.vehicle['id']],
        })
        charge = generate_charge(self.db, 1, subscription['id'], '2026-10')
        payment = create_payment(self.db, 1, {
            'client_id': self.client['id'], 'paid_on': '2026-10-05', 'amount': '125.00',
            'method': 'PIX', 'allocations': [{'charge_id': charge['id'], 'amount': '125.00'}],
        })

        finance = finance_snapshot(self.db)
        commercial = commercial_snapshot(self.db)
        overview = client_activity_overview(self.db)[0]
        summary = dashboard(self.db)
        self.assertEqual(finance['realized_received_cents'], 12500)
        self.assertEqual([row['id'] for row in finance['active_payments']], [payment['id']])
        self.assertEqual([row['id'] for row in commercial['payments']], [payment['id']])
        self.assertEqual((overview['received_cents'], overview['value_generated_cents']), (12500, 12500))
        self.assertEqual(summary['revenue_received_cents'], 12500)
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM payments')[0], 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM payment_allocations WHERE active=1')[0], 1)

        reverse_payment(self.db, 1, payment['id'])

        finance = finance_snapshot(self.db)
        commercial = commercial_snapshot(self.db)
        overview = client_activity_overview(self.db)[0]
        summary = dashboard(self.db)
        self.assertEqual((finance['realized_received_cents'], finance['active_payments']), (0, []))
        self.assertEqual(commercial['payments'], [])
        self.assertEqual((overview['received_cents'], overview['value_generated_cents']), (0, 0))
        self.assertEqual(summary['revenue_received_cents'], 0)
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM payments')[0], 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM payment_allocations WHERE active=1')[0], 0)


if __name__ == '__main__':
    unittest.main()
