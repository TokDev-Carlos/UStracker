"""H-06 (2.4.0) — Financeiro › Recebimentos: cartões Total Recebido e Total Não Pago."""
import os, sys, tempfile, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.billing import receivables_summary, register_subscription_payment
from ustracker.db import Database
from ustracker.services import create_catalog, create_client, create_direct_sale, create_subscription, reverse_payment

TODAY = date(2026, 10, 3)


class Receivables(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Cliente', 'email': 'c@example.test',
                                                 'documents': [{'type': 'RG', 'number': 'RG-H06-001', 'is_primary': True}]})
        plan = create_catalog(self.db, 1, {'description': 'Plano 100', 'category': 'Mensal', 'price': '100.00', 'cost': '0.00'})
        self.sub = create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-08-01', 'due_day': 10,
                                                    'items': [{'catalog_id': plan['id'], 'quantity': 1}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_received_and_unpaid(self):
        s = receivables_summary(self.db, TODAY)
        self.assertEqual((s['received_cents'], s['unpaid_cents']), (0, 20000), 'ago e set vencidos')
        pay = register_subscription_payment(self.db, 1, {'subscription_id': self.sub['id'], 'months': 1}, as_of=TODAY)
        s = receivables_summary(self.db, TODAY)
        self.assertEqual((s['received_cents'], s['unpaid_cents']), (10000, 10000))
        create_direct_sale(self.db, 1, {'client_id': self.client['id'], 'sold_on': '2026-10-01',
                                        'items': [{'description': 'Instalação', 'quantity': 1, 'unit_price': '50.00'}]})
        self.assertEqual(receivables_summary(self.db, TODAY)['unpaid_cents'], 15000, 'compra direta em aberto entra')
        reverse_payment(self.db, 1, pay['payment']['id'] if 'payment' in pay else pay['id'])
        s = receivables_summary(self.db, TODAY)
        self.assertEqual(s['received_cents'], 0)


if __name__ == '__main__':
    unittest.main()
