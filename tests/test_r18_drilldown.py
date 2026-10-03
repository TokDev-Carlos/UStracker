import os, sys, tempfile, unittest
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.projections import overview_drilldown
from ustracker.services import add_disbursement, create_client, create_expense, create_payment, dashboard, reverse_payment


class R18DrilldownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Ana', 'email': 'a@example.test',
                                                  'documents': [{'type': 'RG', 'number': 'RG-R18-001', 'is_primary': True}]})

    def tearDown(self):
        self.tmp.cleanup()

    def _pay(self, when, amount):
        return create_payment(self.db, 1, {'client_id': self.client['id'], 'paid_on': when, 'amount': amount, 'create_credit': True})

    def test_components_reconcile_with_cards_across_year_boundary_and_reversal(self):
        self._pay('2025-12-31', '100.00')
        self._pay('2026-01-01', '50.00')
        reversed_one = self._pay('2026-01-02', '30.00')
        reverse_payment(self.db, 1, reversed_one['id'])
        expense = create_expense(self.db, 1, {'category': 'Operação', 'description': 'Chip', 'competence': '2026-01', 'expected_amount': '20.00'})
        add_disbursement(self.db, 1, expense['id'], {'amount': '20.00', 'paid_on': '2026-01-05'})
        as_of = date(2026, 10, 3)
        y2026 = overview_drilldown(self.db, 2026, as_of)
        self.assertEqual(y2026['totals']['revenue_cents'], 5000)
        self.assertEqual(y2026['totals']['expenses_cents'], 2000)
        self.assertEqual(y2026['totals']['result_cents'], 3000)
        self.assertEqual(y2026['reversed_payments_cents'], 3000)
        self.assertEqual([p['period'] for p in y2026['periods']], ['2026-01'])
        self.assertEqual(y2026['expense_categories'][0]['category'], 'Operação')
        card = dashboard(self.db, as_of, 2026)['period']
        self.assertEqual((card['revenue_cents'], card['expenses_cents'], card['result_cents']), (5000, 2000, 3000))
        geral = overview_drilldown(self.db, None, as_of)
        self.assertEqual([p['period'] for p in geral['periods']], ['2025', '2026'])
        self.assertEqual(geral['totals']['revenue_cents'], 15000)

    def test_empty_year_and_invalid_year(self):
        empty = overview_drilldown(self.db, 2030, date(2026, 10, 3))
        self.assertEqual((empty['periods'], empty['totals']['revenue_cents']), ([], 0))
        with self.assertRaises(ValueError):
            overview_drilldown(self.db, 1990)


if __name__ == '__main__':
    unittest.main()
