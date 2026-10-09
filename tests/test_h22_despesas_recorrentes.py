"""H-22 (2.8.0) — Despesas: Abrir mostra os meses da recorrente; pagar retroativo em lote e adiantado (até 12 meses);
Excluir recorrente pergunta "só esta" ou "esta e as próximas" (tudo vai para a Lixeira)."""
import os, sys, tempfile, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.expenses import create_company_expense, delete_expense, expense_rows, expense_series, pay_expense_months, run_recurring_expenses
from ustracker.trash import list_trash, restore

TODAY = date(2026, 10, 9)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.tpl = create_company_expense(self.db, 1, {'category': 'Mensalidades e serviços', 'description': 'Plataforma GPS', 'amount': '50,00',
                                                       'repeat': 'MONTHLY', 'date': '2026-07-05'}, as_of=TODAY)

    def tearDown(self):
        self.tmp.cleanup()

    def series(self):
        return {m['competence']: m for m in expense_series(self.db, self.tpl['id'], as_of=TODAY)['months']}

    def comps(self):
        return sorted(r['competence'] for r in expense_rows(self.db) if r['recurrence_id'] == self.tpl['id'])


class Serie(Base):
    def test_series_shows_past_current_and_12_future_months(self):
        s = self.series()
        self.assertEqual(min(s), '2026-07'); self.assertEqual(max(s), '2027-10')
        self.assertEqual(len(s), 16)
        self.assertEqual(s['2026-07']['status'], 'OPEN'); self.assertTrue(s['2026-07']['expense_id'])
        self.assertEqual(s['2026-11']['status'], 'FUTURE'); self.assertIsNone(s['2026-11']['expense_id'])
        self.assertEqual(s['2026-11']['due_on'], '2026-11-05')

    def test_any_month_of_the_series_opens_the_same_series(self):
        occ = [r for r in expense_rows(self.db) if r['competence'] == '2026-09'][0]
        self.assertEqual(expense_series(self.db, occ['id'], as_of=TODAY)['template_id'], self.tpl['id'])

    def test_one_off_has_no_series(self):
        one = create_company_expense(self.db, 1, {'category': 'Outros', 'description': 'X', 'amount': '10,00', 'repeat': 'ONCE', 'date': '2026-10-01'}, as_of=TODAY)
        self.assertEqual(expense_series(self.db, one['id'], as_of=TODAY)['months'], [])


class PagarMeses(Base):
    def test_retroactive_batch_with_each_due_date(self):
        out = pay_expense_months(self.db, 1, self.tpl['id'], {'competences': ['2026-07', '2026-08', '2026-09'], 'paid_on': 'DUE'}, as_of=TODAY)
        self.assertEqual(out['paid'], 3)
        s = self.series()
        for comp, day in (('2026-07', '2026-07-05'), ('2026-08', '2026-08-05'), ('2026-09', '2026-09-05')):
            self.assertEqual((s[comp]['status'], s[comp]['paid_on']), ('PAID', day))
        self.assertEqual(s['2026-10']['status'], 'OPEN')

    def test_pay_future_months_in_advance(self):
        pay_expense_months(self.db, 1, self.tpl['id'], {'competences': ['2026-10', '2026-11', '2026-12'], 'paid_on': '2026-10-09'}, as_of=TODAY)
        s = self.series()
        self.assertEqual([s[c]['status'] for c in ('2026-10', '2026-11', '2026-12')], ['PAID'] * 3)
        self.assertEqual(s['2026-12']['paid_on'], '2026-10-09')
        self.assertEqual(run_recurring_expenses(self.db, 1, date(2026, 12, 2))['created'], 0, 'não duplica o mês pago adiantado')

    def test_limit_of_12_months_and_no_future_payment_date(self):
        with self.assertRaises(ValueError):
            pay_expense_months(self.db, 1, self.tpl['id'], {'competences': ['2027-11'], 'paid_on': '2026-10-09'}, as_of=TODAY)
        with self.assertRaises(ValueError):
            pay_expense_months(self.db, 1, self.tpl['id'], {'competences': ['2026-10'], 'paid_on': '2026-10-20'}, as_of=TODAY)

    def test_already_paid_month_is_skipped_atomically(self):
        pay_expense_months(self.db, 1, self.tpl['id'], {'competences': ['2026-08'], 'paid_on': 'DUE'}, as_of=TODAY)
        out = pay_expense_months(self.db, 1, self.tpl['id'], {'competences': ['2026-08', '2026-09'], 'paid_on': 'DUE'}, as_of=TODAY)
        self.assertEqual(out['paid'], 1)


class Excluir(Base):
    def occ(self, comp):
        return [r for r in expense_rows(self.db) if r['competence'] == comp and r['recurrence_id'] == self.tpl['id']][0]

    def test_only_this_month_does_not_come_back(self):
        delete_expense(self.db, 1, self.occ('2026-08')['id'], scope='ONE')
        self.assertEqual(self.comps(), ['2026-07', '2026-09', '2026-10'])
        run_recurring_expenses(self.db, 1, date(2026, 11, 2))
        self.assertNotIn('2026-08', self.comps(), 'o mês excluído não volta')
        self.assertNotIn('2026-08', self.series())

    def test_only_this_on_the_first_month_keeps_the_repetition(self):
        delete_expense(self.db, 1, self.tpl['id'], scope='ONE')
        rows = [r for r in expense_rows(self.db) if r['description'] == 'Plataforma GPS']
        self.assertEqual(sorted(r['competence'] for r in rows), ['2026-08', '2026-09', '2026-10'])
        self.assertEqual(len({r['recurrence_id'] for r in rows}), 1)
        self.assertEqual(run_recurring_expenses(self.db, 1, date(2026, 11, 2))['created'], 1, 'a repetição continua')

    def test_this_and_next_stops_the_repetition(self):
        delete_expense(self.db, 1, self.occ('2026-09')['id'], scope='FORWARD')
        self.assertEqual(self.comps(), ['2026-07', '2026-08'])
        self.assertEqual(run_recurring_expenses(self.db, 1, date(2027, 1, 2))['created'], 0)
        self.assertEqual(len([t for t in list_trash(self.db) if t['entity_type'] == 'expense']), 2)

    def test_restore_from_trash_brings_the_month_back(self):
        delete_expense(self.db, 1, self.occ('2026-08')['id'], scope='ONE')
        item = [t for t in list_trash(self.db) if t['entity_type'] == 'expense'][0]
        restore(self.db, 1, item['id'])
        self.assertIn('2026-08', self.comps())
        run_recurring_expenses(self.db, 1, date(2026, 11, 2))
        self.assertEqual(self.comps().count('2026-08'), 1)


if __name__ == '__main__':
    unittest.main()
