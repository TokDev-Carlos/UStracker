"""H-20 (2.7.0) — Frota: cada veículo é uma assinatura (regra do Carlos, 2026-10-09).

* A frota só agrupa: 4 veículos na frota = 4 assinaturas individuais (mesmo plano, mesmo vencimento).
* Pagar a frota toda de uma vez: UM recibo cobrindo os meses de todos os veículos.
* Dashboard conta as assinaturas individuais.
* Assinaturas antigas (uma cobrindo a frota inteira) são divididas sozinhas: histórico de cobranças e
  pagamentos dividido por veículo, totais de cada mês intactos, sem repetir.
"""
import os, sys, tempfile, unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import fleet_split
from ustracker.billing import client_payment_options, register_fleet_payment, register_subscription_payment, subscription_payment_status
from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle
from ustracker.services import create_catalog, create_client, create_client_company, create_subscription, dashboard, uid
from ustracker.subscription_edit import amend_subscription

TODAY = date(2026, 10, 9)


def active_subs(db, client_id):
    return db.query("SELECT * FROM subscriptions WHERE client_id=? AND lifecycle_status='ACTIVE' ORDER BY code", (client_id,))


def totals(db):
    ch = {r[0]: (r[1], r[2]) for r in db.query("SELECT competence,SUM(amount_cents),SUM(adjustment_cents) FROM charges GROUP BY 1")}
    al = {r[0]: r[1] for r in db.query('''SELECT c.competence,SUM(pa.amount_cents) FROM payment_allocations pa JOIN charges c ON c.id=pa.charge_id
                                           WHERE pa.active=1 GROUP BY 1''')}
    pay = db.one('SELECT COALESCE(SUM(amount_cents),0),COUNT(*) FROM payments')
    return ch, al, tuple(pay)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Transportes', 'email': 't@example.test',
                                                 'documents': [{'type': 'RG', 'number': 'RG-H20-001', 'is_primary': True}]})
        cid = self.client['id']
        company = create_client_company(self.db, 1, cid, {'legal_name': 'Transportes LTDA', 'is_primary': True})
        self.fleet = create_fleet(self.db, 1, {'client_id': cid, 'client_company_id': company['id'], 'name': 'Frota Azul'})
        mk = lambda plate, fleet=None: create_vehicle(self.db, 1, {'client_id': cid, 'fleet_id': fleet, 'plate': plate, 'type': 'Carro',
                                                                    'brand': 'Marca', 'model': 'Modelo', 'year': 2026})
        self.fv = [mk(p, self.fleet['id']) for p in ('FRT1A01', 'FRT1A02', 'FRT1A03', 'FRT1A04')]
        self.solo = mk('SOL1A01')
        self.plan = create_catalog(self.db, 1, {'description': 'Plano 50', 'category': 'Mensal', 'price': '50.00', 'cost': '0.00'})

    def tearDown(self):
        self.tmp.cleanup()

    def new_fleet_sub(self, **extra):
        p = {'client_id': self.client['id'], 'start_on': '2026-10-01', 'due_day': 10,
             'items': [{'catalog_id': self.plan['id'], 'quantity': 4}], 'target_fleet_ids': [self.fleet['id']]}
        p.update(extra)
        return create_subscription(self.db, 1, p)


class NovaAssinaturaDeFrota(Base):
    def test_fleet_of_4_creates_4_individual_subscriptions(self):
        self.new_fleet_sub()
        subs = active_subs(self.db, self.client['id'])
        self.assertEqual(len(subs), 4)
        covered = set()
        for s in subs:
            targets = self.db.query('SELECT vehicle_id,fleet_id FROM subscription_targets WHERE subscription_id=?', (s['id'],))
            self.assertEqual(len(targets), 1); self.assertIsNone(targets[0]['fleet_id'])
            covered.add(targets[0]['vehicle_id'])
            self.assertEqual(subscription_payment_status(self.db, s['id'], TODAY)['monthly_cents'], 5000)
            self.assertEqual(s['due_day'], 10)
        self.assertEqual(covered, {v['id'] for v in self.fv})
        self.assertEqual(dashboard(self.db, as_of=TODAY)['active_subscriptions'], 4)

    def test_fleet_plus_loose_vehicle(self):
        self.new_fleet_sub(items=[{'catalog_id': self.plan['id'], 'quantity': 5}], target_vehicle_ids=[self.solo['id']])
        self.assertEqual(len(active_subs(self.db, self.client['id'])), 5)

    def test_single_vehicle_stays_one(self):
        create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-10-01', 'items': [{'catalog_id': self.plan['id'], 'quantity': 1}],
                                         'target_vehicle_ids': [self.solo['id']]})
        self.assertEqual(len(active_subs(self.db, self.client['id'])), 1)

    def test_amend_adding_the_fleet_splits_too(self):
        sub = create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-10-01', 'items': [{'catalog_id': self.plan['id'], 'quantity': 1}],
                                               'target_vehicle_ids': [self.solo['id']]})
        amend_subscription(self.db, 1, sub['id'], {'expected_revision': sub['revision'], 'items': [{'catalog_id': self.plan['id'], 'quantity': 5}],
                                                   'target_vehicle_ids': [self.solo['id']], 'target_fleet_ids': [self.fleet['id']]})
        subs = active_subs(self.db, self.client['id'])
        self.assertEqual(len(subs), 5)
        self.assertEqual({subscription_payment_status(self.db, s['id'], TODAY)['monthly_cents'] for s in subs}, {5000})


class PagarFrotaToda(Base):
    def test_options_show_the_fleet_as_one_choice(self):
        self.new_fleet_sub()
        opts = client_payment_options(self.db, self.client['id'], as_of=TODAY)
        self.assertEqual(len(opts['subscriptions']), 4)
        [fleet] = opts['fleets']
        self.assertEqual((fleet['fleet_id'], fleet['name'], fleet['vehicle_count'], fleet['monthly_cents']), (self.fleet['id'], 'Frota Azul', 4, 20000))
        self.assertEqual(fleet['plates'], ['FRT1A01', 'FRT1A02', 'FRT1A03', 'FRT1A04'])
        self.assertEqual(fleet['next_due'], '2026-10')

    def test_one_receipt_pays_every_vehicle(self):
        self.new_fleet_sub()
        rec = register_fleet_payment(self.db, 1, {'fleet_id': self.fleet['id'], 'months': 2, 'paid_on': '2026-10-09', 'method': 'PIX'}, as_of=TODAY)
        self.assertEqual(rec['amount_cents'], 40000)
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM payments')[0], 1, 'um recibo só')
        for s in active_subs(self.db, self.client['id']):
            self.assertEqual(subscription_payment_status(self.db, s['id'], TODAY)['paid_through'], '2026-11')
        self.assertEqual(len(rec['subscriptions']), 4)

    def test_partial_amount_pays_oldest_first(self):
        self.new_fleet_sub()
        register_fleet_payment(self.db, 1, {'fleet_id': self.fleet['id'], 'months': 2, 'paid_on': '2026-10-09', 'amount': '200.00'}, as_of=TODAY)
        for s in active_subs(self.db, self.client['id']):
            st = subscription_payment_status(self.db, s['id'], TODAY)
            self.assertEqual(st['paid_through'], '2026-10', 'outubro de todos pago; novembro fica em aberto')

    def test_discount(self):
        self.new_fleet_sub()
        rec = register_fleet_payment(self.db, 1, {'fleet_id': self.fleet['id'], 'months': 1, 'paid_on': '2026-10-09', 'discount': '20.00'}, as_of=TODAY)
        self.assertEqual(rec['amount_cents'], 18000)
        for s in active_subs(self.db, self.client['id']):
            self.assertEqual(subscription_payment_status(self.db, s['id'], TODAY)['paid_through'], '2026-10')

    def test_fleet_without_active_subscription(self):
        with self.assertRaises(ValueError):
            register_fleet_payment(self.db, 1, {'fleet_id': self.fleet['id'], 'months': 1, 'paid_on': '2026-10-09'}, as_of=TODAY)


class DividirAssinaturasAntigas(Base):
    def legacy(self, quantity=4, price=5000):
        """Assinatura no formato antigo (até a 2.6): uma só cobrindo a frota inteira."""
        sid = uid(); ts = '2026-09-01T00:00:00+00:00'
        with self.db.transaction() as con:
            con.execute('''INSERT INTO subscriptions(id,client_id,signed_on,start_on,due_day,billing_interval_months,billing_cycle,lifecycle_status,revision,created_at,updated_at)
                           VALUES(?,?,?,?,10,1,'MONTHLY','ACTIVE',1,?,?)''', (sid, self.client['id'], '2026-09-01', '2026-09-01', ts, ts))
            con.execute('INSERT INTO subscription_items(id,subscription_id,catalog_id,description,quantity,unit_price_cents) VALUES(?,?,?,?,?,?)',
                        (uid(), sid, self.plan['id'], 'Plano 50', quantity, price))
            con.execute('INSERT INTO subscription_targets(id,subscription_id,fleet_id,created_at) VALUES(?,?,?,?)', (uid(), sid, self.fleet['id'], ts))
        return sid

    def test_split_keeps_every_month_total_and_payment(self):
        sid = self.legacy()
        register_subscription_payment(self.db, 1, {'subscription_id': sid, 'months': 2, 'paid_on': '2026-10-05', 'discount': '10.01'}, as_of=TODAY)
        register_subscription_payment(self.db, 1, {'subscription_id': sid, 'months': 1, 'paid_on': '2026-10-06', 'amount': '150.00'}, as_of=TODAY)
        before = totals(self.db)
        out = fleet_split.split_all(self.db, 0)
        self.assertEqual(out['split'], 1); self.assertEqual(out['created'], 3)
        self.assertEqual(totals(self.db), before, 'nenhum centavo muda')
        subs = active_subs(self.db, self.client['id'])
        self.assertEqual(len(subs), 4)
        for s in subs:
            st = subscription_payment_status(self.db, s['id'], TODAY)
            self.assertEqual(st['monthly_cents'], 5000)
            self.assertEqual(st['paid_through'], '2026-10', 'set e out pagos para todos; nov parcial')
            nov = self.db.one("SELECT status FROM charges WHERE subscription_id=? AND competence='2026-11'", (s['id'],))[0]
            self.assertEqual(nov, 'PARTIAL')
        self.assertEqual(self.db.one("SELECT COUNT(*) FROM subscription_targets WHERE fleet_id IS NOT NULL")[0], 0)
        self.assertEqual(fleet_split.split_all(self.db, 0)['split'], 0, 'não repete')
        self.assertTrue(self.db.one("SELECT 1 FROM audit_events WHERE action='SUBSCRIPTION_SPLIT'"))

    def test_split_is_the_same_on_every_computer(self):
        sid = self.legacy()
        fleet_split.split_all(self.db, 0)
        ids = {r[0] for r in self.db.query('SELECT id FROM subscriptions')}
        expected = {sid} | {fleet_split.derived_id(sid, v['id']) for v in self.fv[1:]}
        self.assertEqual(ids, expected)

    def test_odd_quantity_keeps_the_monthly_total(self):
        self.legacy(quantity=1, price=10001)   # valor total digitado à mão
        fleet_split.split_all(self.db, 0)
        subs = active_subs(self.db, self.client['id'])
        self.assertEqual(sum(subscription_payment_status(self.db, s['id'], TODAY)['monthly_cents'] for s in subs), 10001)


if __name__ == '__main__':
    unittest.main()
