"""H-09 (2.4.0) — Assinatura por frota: veículos trazem as assinaturas ativas que já os cobrem (aviso de duplicidade)."""
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.commercial import commercial_snapshot
from ustracker.mobility import create_fleet, create_vehicle, mobility_subscription_detail
from ustracker.billing import client_payment_options, register_subscription_payment
from datetime import date
from ustracker.services import client_profile, create_catalog, create_client, create_client_company, create_subscription


class FleetCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        c = self.client = create_client(self.db, 1, {'legal_name': 'Cliente', 'email': 'c@example.test',
                                                     'documents': [{'type': 'RG', 'number': 'RG-H09-001', 'is_primary': True}]})
        company = create_client_company(self.db, 1, c['id'], {'legal_name': 'Empresa', 'is_primary': True})
        self.fleet = create_fleet(self.db, 1, {'client_id': c['id'], 'client_company_id': company['id'], 'name': 'Frota'})
        mk = lambda plate, fleet=None: create_vehicle(self.db, 1, {'client_id': c['id'], 'fleet_id': fleet, 'plate': plate, 'type': 'Carro', 'brand': 'Marca', 'model': 'Modelo', 'year': 2026})
        self.v1, self.v2, self.solo = mk('HAA1A11', self.fleet['id']), mk('HAA1A12', self.fleet['id']), mk('HAA1A13')
        self.plan = create_catalog(self.db, 1, {'description': 'Plano 50', 'category': 'Mensal', 'price': '50.00', 'cost': '0.00'})
        self.sub = create_subscription(self.db, 1, {'client_id': c['id'], 'start_on': '2026-10-01', 'due_day': 10,
                                                    'items': [{'catalog_id': self.plan['id'], 'quantity': 2}],
                                                    'target_fleet_ids': [self.fleet['id']]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_vehicles_carry_active_subscription_codes(self):
        code = self.sub.get('code') or self.db.one('SELECT code FROM subscriptions WHERE id=?', (self.sub['id'],))[0]
        for vehicles in (commercial_snapshot(self.db)['vehicles'], client_profile(self.db, self.client['id'])['vehicles']):
            by_id = {v['id']: v for v in vehicles}
            self.assertEqual(by_id[self.v1['id']]['subscription_codes'], [code])
            self.assertEqual(by_id[self.v2['id']]['subscription_codes'], [code])
            self.assertEqual(by_id[self.solo['id']]['subscription_codes'], [])

    def test_payment_dialog_shows_what_is_covered(self):
        sub = client_payment_options(self.db, self.client['id'], as_of=date(2026, 10, 3))['subscriptions'][0]
        cov = sub['coverage']
        self.assertEqual([(f['name'], f['plates']) for f in cov['fleets']], [('Frota', ['HAA1A11', 'HAA1A12'])])
        self.assertEqual(cov['vehicles'], [])
        self.assertEqual((cov['vehicle_count'], cov['monthly_cents'], cov['per_vehicle_cents']), (2, 10000, 5000))

    def test_vehicle_and_fleet_history(self):
        register_subscription_payment(self.db, 1, {'subscription_id': self.sub['id'], 'months': 2, 'paid_on': '2026-10-03'}, as_of=date(2026, 10, 3))
        for kwargs in ({'vehicle_id': self.v1['id']}, {'fleet_id': self.fleet['id']}):
            hist = mobility_subscription_detail(self.db, **kwargs)['history']
            self.assertEqual([h['competence'] for h in hist], ['2026-11', '2026-10'])
            self.assertEqual({(h['status'], h['amount_cents'], h['paid_on']) for h in hist}, {('PAID', 10000, '2026-10-03')})
        v_hist = mobility_subscription_detail(self.db, vehicle_id=self.v1['id'])['history']
        self.assertEqual(v_hist[0]['share_cents'], 5000)
        self.assertEqual(mobility_subscription_detail(self.db, vehicle_id=self.solo['id'])['history'], [])


if __name__ == '__main__':
    unittest.main()
