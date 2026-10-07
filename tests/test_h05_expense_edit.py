"""H-05 (2.4.0) — Gerente edita e exclui despesas pagas e a pagar (pagamentos vão juntos para a Lixeira)."""
import os, sys, tempfile, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.expenses import create_company_expense, delete_expense, expense_rows, pay_expense, update_expense
from ustracker.projections import realized_expenses
from ustracker import trash

TODAY = date(2026, 10, 3)


class ExpenseEdit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def row(self, eid):
        return next(r for r in expense_rows(self.db) if r['id'] == eid)

    def test_edit_paid_expense_and_status_follows(self):
        e = create_company_expense(self.db, 1, {'category': 'Insumos', 'description': 'Chip', 'amount': '50,00', 'repeat': 'ONCE',
                                                'date': '2026-10-01', 'paid': 'true'}, as_of=TODAY)
        self.assertEqual(self.row(e['id'])['status'], 'PAID')
        out = update_expense(self.db, 1, e['id'], {'description': 'Chip M2M', 'amount': '80,00', 'category': 'Equipamentos', 'date': '2026-09-20'})
        r = self.row(e['id'])
        self.assertEqual((r['description'], r['expected_amount_cents'], r['category'], r['due_on'], r['competence']),
                         ('Chip M2M', 8000, 'Equipamentos', '2026-09-20', '2026-09'))
        self.assertEqual(r['status'], 'PARTIAL', 'pagou 50 de 80'); self.assertEqual(out['status'], 'PARTIAL')
        update_expense(self.db, 1, e['id'], {'amount': '50,00'})
        self.assertEqual(self.row(e['id'])['status'], 'PAID')
        with self.assertRaises(ValueError):  # less than what was already paid
            update_expense(self.db, 1, e['id'], {'amount': '10,00'})
        with self.assertRaises(ValueError):
            update_expense(self.db, 1, e['id'], {'category': 'Inexistente'})

    def test_delete_paid_expense_goes_to_trash_with_payments_and_restores(self):
        e = create_company_expense(self.db, 1, {'category': 'Insumos', 'description': 'Chip', 'amount': '50,00', 'repeat': 'ONCE',
                                                'date': '2026-10-01', 'paid': 'true'}, as_of=TODAY)
        self.assertEqual(realized_expenses(self.db, None, None, TODAY), 5000)
        delete_expense(self.db, 1, e['id'])
        self.assertFalse([r for r in expense_rows(self.db) if r['id'] == e['id']])
        self.assertEqual(realized_expenses(self.db, None, None, TODAY), 0, 'o pagamento sai junto')
        item = self.db.one("SELECT id FROM trash WHERE entity_id=?", (e['id'],))
        trash.restore(self.db, 1, item['id'])
        self.assertEqual(self.row(e['id'])['status'], 'PAID')
        self.assertEqual(realized_expenses(self.db, None, None, TODAY), 5000, 'pagamento volta com a restauração')


if __name__ == '__main__':
    unittest.main()
