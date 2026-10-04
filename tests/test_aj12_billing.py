import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.billing import client_payment_options, register_subscription_payment, subscription_payment_status
from ustracker.db import Database
from ustracker.projections import realized_revenue
from ustracker.services import create_catalog, create_client, create_subscription, reverse_payment

TODAY = date(2026, 10, 3)


class AJ12BillingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Cliente Pagamento', 'email': 'p@example.test',
                                                 'documents': [{'type': 'RG', 'number': 'RG-AJ12-001', 'is_primary': True}]})
        plan = create_catalog(self.db, 1, {'description': 'Plano 100', 'category': 'Mensal', 'price': '100.00', 'cost': '0.00'})
        self.sub = create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-08-01', 'due_day': 10,
                                                    'items': [{'catalog_id': plan['id'], 'quantity': 1}]})

    def tearDown(self):
        self.tmp.cleanup()

    def pay(self, **kw):
        p = {'subscription_id': self.sub['id'], 'months': 1}
        p.update(kw)
        return register_subscription_payment(self.db, 1, p, as_of=TODAY)

    def test_status_starts_with_overdue_months(self):
        st = subscription_payment_status(self.db, self.sub['id'], as_of=TODAY)
        self.assertIsNone(st['paid_through'])
        self.assertEqual(st['next_due'], '2026-08')
        self.assertEqual(st['overdue_months'], 2)
        self.assertEqual(st['monthly_cents'], 10000)
        opts = client_payment_options(self.db, self.client['id'], as_of=TODAY)
        self.assertEqual(len(opts['subscriptions']), 1)

    def test_pay_overdue_and_advance_in_one_transaction(self):
        rec = self.pay(months=5, paid_on='2026-09-15')
        self.assertEqual(rec['amount_cents'], 50000)
        self.assertEqual([c['competence'] for c in rec['competences']], ['2026-08', '2026-09', '2026-10', '2026-11', '2026-12'])
        self.assertTrue(all(c['status'] == 'PAID' for c in rec['competences']))
        self.assertEqual(rec['paid_through'], '2026-12')
        self.assertEqual(rec['next_due'], '2027-01')
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM charges WHERE subscription_id=?', (self.sub['id'],))[0], 5)
        # retroactive payment is realized on its date; advance months do not change that rule
        self.assertEqual(realized_revenue(self.db, date(2026, 9, 1), date(2026, 10, 1), TODAY), 50000)

    def test_discount_and_reversal_restore_charges(self):
        rec = self.pay(months=3, discount='30,00')
        self.assertEqual(rec['amount_cents'], 27000)
        self.assertEqual(rec['paid_through'], '2026-10')
        reverse_payment(self.db, 1, rec['id'])
        st = subscription_payment_status(self.db, self.sub['id'], as_of=TODAY)
        self.assertIsNone(st['paid_through'])
        self.assertEqual(st['open_charges_cents'], 30000)

    def test_partial_amount_keeps_rest_open_and_surplus_becomes_credit(self):
        rec = self.pay(months=2, amount='150,00')
        self.assertEqual([c['status'] for c in rec['competences']], ['PAID', 'PARTIAL'])
        self.assertEqual(rec['paid_through'], '2026-08')
        rec2 = self.pay(months=1, amount='80,00')
        self.assertEqual(rec2['credit_cents'], 3000)
        self.assertEqual(rec2['paid_through'], '2026-09')

    def test_future_date_and_atomicity(self):
        with self.assertRaises(ValueError):
            self.pay(paid_on='2026-10-04')
        with self.assertRaises(ValueError):
            self.pay(months=2, discount='500,00')
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM charges')[0], 0)
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM payments')[0], 0)


if __name__ == '__main__':
    unittest.main()
