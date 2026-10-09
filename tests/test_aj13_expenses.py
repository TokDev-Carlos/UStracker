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
from ustracker.expenses import (convert_expense_to_sale, create_company_expense, delete_expense, expense_rows, pay_expense,
                                pending_recurring_count, run_recurring_expenses, stop_recurring_expense)
from ustracker.projections import realized_expenses
from ustracker.services import create_client

TODAY = date(2026, 10, 3)


class AJ13ExpenseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, **kw):
        p = {'category': 'Mensalidades e serviços', 'description': 'Plataforma GPS', 'amount': '50,00', 'repeat': 'MONTHLY', 'date': '2026-08-05'}
        p.update(kw)
        return create_company_expense(self.db, 1, p, as_of=TODAY)

    def test_monthly_generates_until_current_month_idempotently(self):
        tpl = self.make(paid='true')
        rows = [r for r in expense_rows(self.db) if r['recurrence_id'] == tpl['id']]
        self.assertEqual(sorted(r['competence'] for r in rows), ['2026-08', '2026-09', '2026-10'])
        self.assertEqual(pending_recurring_count(self.db, TODAY), 0)
        self.assertEqual(run_recurring_expenses(self.db, 1, TODAY)['created'], 0)
        self.assertEqual(run_recurring_expenses(self.db, 1, date(2026, 11, 2))['created'], 1)
        self.assertEqual(realized_expenses(self.db, None, None, TODAY), 5000)

    def test_annual_and_once(self):
        self.make(repeat='ANNUAL', date='2025-09-10', description='Licença')
        self.assertEqual(sorted(r['competence'] for r in expense_rows(self.db) if r['description'] == 'Licença'), ['2025-09', '2026-09'])
        once = self.make(repeat='ONCE', category='Equipamentos', description='Rastreador', amount='120,00', date='2026-10-01')
        self.assertIsNone(once['recurrence_id'])

    def test_pay_stop_and_delete(self):
        tpl = self.make()
        pay = pay_expense(self.db, 1, tpl['id'], as_of=TODAY)
        self.assertEqual(pay['expense_status'], 'PAID')
        with self.assertRaises(ValueError):
            pay_expense(self.db, 1, tpl['id'], as_of=TODAY)
        stop_recurring_expense(self.db, 1, tpl['id'])
        self.assertEqual(run_recurring_expenses(self.db, 1, date(2027, 3, 1))['created'], 0)
        # 2.8.0: o 1º mês de uma recorrente pode ser excluído ("só esta"); os outros meses ficam
        self.assertTrue(delete_expense(self.db, 1, tpl['id'])['deleted'])
        self.assertEqual(sorted(r['competence'] for r in expense_rows(self.db) if r['description'] == 'Plataforma GPS'), ['2026-09', '2026-10'])
        once = self.make(repeat='ONCE', description='Chip')
        self.assertTrue(delete_expense(self.db, 1, once['id'])['deleted'])

    def test_invalid_category_and_future_paid(self):
        with self.assertRaises(ValueError):
            self.make(category='Qualquer')
        with self.assertRaises(ValueError):
            self.make(repeat='ONCE', date='2026-12-01', paid='true')

    def test_convert_once_to_direct_sale(self):
        client = create_client(self.db, 1, {'legal_name': 'Cliente', 'email': 'c@example.test',
                                            'documents': [{'type': 'RG', 'number': 'RG-AJ13-001', 'is_primary': True}]})
        once = self.make(repeat='ONCE', category='Equipamentos', description='Rastreador X', amount='120,00', date='2026-10-01', paid='true')
        sale = convert_expense_to_sale(self.db, 1, once['id'], {'client_id': client['id'], 'price': '250,00'}, as_of=TODAY)
        self.assertEqual(sale['total_cents'], 25000)
        self.assertTrue(sale['code'].startswith('CLI-0001-C'))
        row = next(r for r in expense_rows(self.db) if r['id'] == once['id'])
        self.assertEqual(row['sale_code'], sale['code'])
        with self.assertRaises(ValueError):
            convert_expense_to_sale(self.db, 1, once['id'], {'client_id': client['id']}, as_of=TODAY)
        self.assertEqual(realized_expenses(self.db, None, None, TODAY), 12000)


if __name__ == '__main__':
    unittest.main()
