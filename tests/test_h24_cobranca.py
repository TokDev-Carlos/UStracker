"""H-24 (2.8.0) — Cobrança: régua de lembretes (3 dias antes, no dia, 3 e 7 dias depois), envio em 1 clique
(WhatsApp/e-mail com a mensagem e o PIX prontos), registro do envio e inadimplência."""
import os, sys, tempfile, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import collections_ as col
from ustracker.billing import register_subscription_payment
from ustracker.db import Database
from ustracker.mobility import create_vehicle
from ustracker.services import create_catalog, create_client, create_subscription


class Cobranca(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        with self.db.transaction() as con:
            for k, v in (('company_display_name', 'USTracker Rastreadores'), ('pix_key', 'financeiro@ustracker.com.br'), ('pix_city', 'Sao Paulo')):
                con.execute("INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,datetime('now'))", (k, v))
        self.plan = create_catalog(self.db, 1, {'description': 'Plano 50', 'category': 'Mensal', 'price': '50.00'})
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, name, due_day, start='2026-10-01', phone='11988887777'):
        self.n += 1
        c = create_client(self.db, 1, {'legal_name': name, 'phone': phone, 'email': f'c{self.n}@x.com',
                                       'documents': [{'type': 'RG', 'number': f'RG-H24-{self.n}', 'is_primary': True}]})
        v = create_vehicle(self.db, 1, {'client_id': c['id'], 'plate': f'COB{self.n}A1{self.n}', 'type': 'Carro', 'brand': 'M', 'model': 'X', 'year': 2024})
        s = create_subscription(self.db, 1, {'client_id': c['id'], 'start_on': start, 'due_day': due_day,
                                             'items': [{'catalog_id': self.plan['id'], 'quantity': 1}], 'target_vehicle_ids': [v['id']]})
        return c, s

    def test_ruler_stages(self):
        today = date(2026, 10, 10)
        a, _ = self.client('Antes', 13)                    # vence em 3 dias
        b, _ = self.client('Hoje', 10)                     # vence hoje
        c, _ = self.client('Tres', 7)                      # 3 dias de atraso
        d, _ = self.client('Sete', 1, start='2026-09-01')  # 09/01 vencida há 39 dias
        e, _ = self.client('Dois', 8)                      # 2 dias de atraso: entre etapas, não lembra hoje
        q = {r['client_id']: r['stage'] for r in col.reminder_queue(self.db, today)}
        self.assertEqual(q, {a['id']: 'BEFORE', b['id']: 'TODAY', c['id']: 'LATE3', d['id']: 'LATE7'})
        self.assertNotIn(e['id'], q)

    def test_message_has_name_value_due_and_pix(self):
        c, _ = self.client('Joana Prado', 10)
        m = col.reminder_message(self.db, c['id'], date(2026, 10, 10))
        self.assertEqual(m['stage'], 'TODAY')
        self.assertIn('Joana', m['text']); self.assertIn('R$ 50,00', m['text']); self.assertIn('vence hoje', m['text'])
        self.assertIn(m['pix_code'], m['text']); self.assertTrue(m['pix_code'].startswith('000201'))
        self.assertEqual(m['whatsapp'], '5511988887777')
        self.assertTrue(m['whatsapp_url'].startswith('https://wa.me/5511988887777?text='))
        self.assertTrue(m['email_url'].startswith('mailto:'))

    def test_reminder_sent_leaves_the_queue_until_next_stage(self):
        c, _ = self.client('Tres', 7)
        today = date(2026, 10, 10)
        col.mark_reminded(self.db, 1, c['id'], {'stage': 'LATE3', 'channel': 'WHATSAPP'}, today)
        self.assertEqual(col.reminder_queue(self.db, today), [])
        self.assertEqual([r['stage'] for r in col.reminder_queue(self.db, date(2026, 10, 14))], ['LATE7'])
        hist = col.reminder_history(self.db, c['id'])
        self.assertEqual((hist[0]['stage'], hist[0]['channel']), ('LATE3', 'WHATSAPP'))

    def test_payment_removes_from_queue_and_overdue(self):
        c, s = self.client('Sete', 1, start='2026-09-01')
        today = date(2026, 10, 10)
        self.assertEqual(len(col.overdue(self.db, today)['items']), 1)
        register_subscription_payment(self.db, 1, {'subscription_id': s['id'], 'months': 2, 'paid_on': '2026-10-10'}, as_of=today)
        self.assertEqual(col.reminder_queue(self.db, today), [])
        self.assertEqual(col.overdue(self.db, today)['items'], [])

    def test_overdue_summary(self):
        today = date(2026, 10, 10)
        self.client('Em dia', 20)
        d, _ = self.client('Sete', 1, start='2026-09-01')
        out = col.overdue(self.db, today)
        [row] = out['items']
        self.assertEqual((row['client_id'], row['months'], row['overdue_cents'], row['since'], row['days']), (d['id'], 2, 10000, '2026-09-01', 39))
        self.assertEqual((out['summary']['clients'], out['summary']['active_clients'], out['summary']['overdue_cents']), (1, 2, 10000))
        self.assertEqual(out['summary']['clients_pct'], 50.0)


if __name__ == '__main__':
    unittest.main()
