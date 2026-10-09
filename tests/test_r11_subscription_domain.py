import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle, fleet_profile, list_mobility
from ustracker.services import (
    create_catalog,
    create_client,
    create_client_company,
    create_subscription,
    client_profile,
    get_subscription,
    list_subscriptions,
)


class R11SubscriptionDomainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client, self.company, self.fleet, self.vehicle = self._client_graph('A', 'R11-DOC-A', 'RAB1A11')
        self.other_client, self.other_company, self.other_fleet, self.other_vehicle = self._client_graph(
            'B', 'R11-DOC-B', 'RAB1B11'
        )
        self.plan = create_catalog(self.db, 1, {
            'description': 'Plano Mensal R11', 'category': 'Mensal', 'price': '150.00', 'cost': '25.00',
        })
        self.inactive_plan = create_catalog(self.db, 1, {
            'description': 'Plano Inativo R11', 'category': 'Mensal', 'price': '80.00', 'active': False,
        })
        self.one_off = create_catalog(self.db, 1, {
            'description': 'Item Avulso R11', 'category': 'Avulsa', 'price': '50.00',
        })

    def tearDown(self):
        self.tmp.cleanup()

    def _client_graph(self, suffix, document, plate):
        client = create_client(self.db, 1, {
            'legal_name': f'Cliente {suffix}', 'email': f'cliente-{suffix.lower()}@example.test',
            'documents': [{'type': 'RG', 'number': document, 'is_primary': True}],
        })
        company = create_client_company(self.db, 1, client['id'], {
            'legal_name': f'Empresa {suffix}', 'is_primary': True,
        })
        fleet = create_fleet(self.db, 1, {
            'client_id': client['id'], 'client_company_id': company['id'], 'name': f'Frota {suffix}',
        })
        vehicle = create_vehicle(self.db, 1, {
            'client_id': client['id'], 'fleet_id': fleet['id'], 'plate': plate,
            'type': 'Carro', 'brand': 'Marca', 'model': f'Modelo {suffix}', 'year': 2026,
        })
        return client, company, fleet, vehicle

    def _payload(self, **changes):
        payload = {
            'client_id': self.client['id'],
            'start_on': '2026-10-01',
            'due_day': 12,
            'items': [{'catalog_id': self.plan['id'], 'quantity': 2}],
            'target_vehicle_ids': [self.vehicle['id']],
            'target_fleet_ids': [self.fleet['id']],
        }
        payload.update(changes)
        return payload

    def test_creates_mixed_targets_with_snapshot_hydration_and_one_audit(self):
        created = create_subscription(self.db, 7, self._payload())

        self.assertEqual(created['effective_total_cents'], 30000)
        self.assertEqual(created['client_name'], 'Cliente A')
        self.assertEqual(created['items'][0]['unit_price_cents'], 15000)
        self.assertEqual(created['items'][0]['plan_name'], 'Plano Mensal R11')
        self.assertEqual(
            {(target['target_type'], target['target_name']) for target in created['targets']},
            {('VEHICLE', 'RAB1A11')},  # 2.7.0: o veículo da frota já marcado → 1 assinatura
        )
        self.assertEqual(
            self.db.one("SELECT COUNT(*) FROM audit_events WHERE action='SUBSCRIPTION_CREATE' AND entity_id=?", (created['id'],))[0],
            1,
        )

        with self.db.transaction() as con:
            con.execute('UPDATE catalog SET price_cents=99999 WHERE id=?', (self.plan['id'],))
        create_client_company(self.db, 1, self.client['id'], {
            'legal_name': 'Empresa Principal Nova', 'is_primary': True,
        })
        reloaded = get_subscription(self.db, created['id'])
        listed = list_subscriptions(self.db, client_id=self.client['id'])
        profile = client_profile(self.db, self.client['id'])
        mobility = list_mobility(self.db, client_id=self.client['id'])
        fleet_read = fleet_profile(self.db, self.fleet['id'])
        self.assertEqual((reloaded['items'][0]['unit_price_cents'], reloaded['effective_total_cents']), (15000, 30000))
        self.assertEqual([row['id'] for row in listed], [created['id']])
        self.assertEqual(list_subscriptions(self.db, client_id=self.other_client['id']), [])
        self.assertEqual(profile['subscriptions'][0]['effective_total_cents'], 30000)
        self.assertEqual(len(profile['subscriptions'][0]['targets']), 1)
        self.assertEqual(profile['subscriptions'][0]['company_name'], 'Empresa Principal Nova')
        fleet_subscription = mobility['fleets'][0]['subscriptions'][0]
        self.assertEqual(
            (fleet_subscription['client_name'], fleet_subscription['company_name'], fleet_subscription['plan_names'],
             fleet_subscription['effective_total_cents'], fleet_subscription['start_on']),
            ('Cliente A', 'Empresa A', 'Plano Mensal R11', 30000, '2026-10-01'),
        )
        self.assertEqual(fleet_read['subscriptions'][0]['id'], created['id'])
        vehicle_subscription = fleet_read['vehicles'][0]['subscriptions'][0]
        self.assertEqual((vehicle_subscription['id'], vehicle_subscription['target_scope']), (created['id'], 'DIRECT'))

    def test_legacy_vehicle_item_becomes_a_target_without_multiplying_value(self):
        created = create_subscription(self.db, 1, self._payload(
            target_vehicle_ids=[], target_fleet_ids=[],
            items=[{'catalog_id': self.plan['id'], 'vehicle_id': self.vehicle['id'], 'quantity': 1}],
        ))

        self.assertEqual(created['effective_total_cents'], 15000)
        self.assertEqual(created['items'][0]['vehicle_id'], self.vehicle['id'])
        self.assertEqual([(target['target_type'], target['vehicle_id']) for target in created['targets']], [
            ('VEHICLE', self.vehicle['id'])
        ])

    def test_rejects_ineligible_catalog_client_and_mobility_relations(self):
        cases = [
            ('inactive plan', self._payload(items=[{'catalog_id': self.inactive_plan['id']}]), 'active monthly plan'),
            ('one-off item', self._payload(items=[{'catalog_id': self.one_off['id']}]), 'active monthly plan'),
            ('foreign vehicle', self._payload(target_vehicle_ids=[self.other_vehicle['id']]), 'vehicle does not belong'),
            ('foreign fleet', self._payload(target_fleet_ids=[self.other_fleet['id']]), 'fleet does not belong'),
            ('duplicate vehicle', self._payload(target_vehicle_ids=[self.vehicle['id'], self.vehicle['id']]), 'duplicate vehicle target'),
            ('duplicate fleet', self._payload(target_fleet_ids=[self.fleet['id'], self.fleet['id']]), 'duplicate fleet target'),
        ]
        for label, payload, message in cases:
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, message):
                create_subscription(self.db, 1, payload)

        with self.db.transaction() as con:
            con.execute("UPDATE clients SET status='INACTIVE' WHERE id=?", (self.client['id'],))
        with self.assertRaisesRegex(ValueError, 'client is not eligible'):
            create_subscription(self.db, 1, self._payload())

    def test_rejects_fleet_whose_company_relation_is_inconsistent(self):
        with self.db.transaction() as con:
            con.execute('UPDATE fleets SET client_company_id=? WHERE id=?', (self.other_company['id'], self.fleet['id']))

        with self.assertRaisesRegex(ValueError, 'fleet company does not belong'):
            create_subscription(self.db, 1, self._payload(target_vehicle_ids=[]))

    def test_invalid_values_roll_back_every_subscription_write(self):
        cases = [
            self._payload(start_on='not-a-date'),
            self._payload(start_on='2026-10-10', end_on='2026-10-01'),
            self._payload(due_day=0),
            self._payload(due_day=32),
            self._payload(items=[{'catalog_id': self.plan['id'], 'quantity': 0}]),
            self._payload(items=[{'catalog_id': self.plan['id'], 'quantity': 1, 'unit_price': '-0.01'}]),
            self._payload(items=[{'catalog_id': self.plan['id']}, {'catalog_id': 'missing-plan'}]),
        ]

        before = self.db.one('SELECT COUNT(*) FROM subscriptions')[0]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                create_subscription(self.db, 1, payload)
            self.assertEqual(self.db.one('SELECT COUNT(*) FROM subscriptions')[0], before)
            self.assertEqual(self.db.one('SELECT COUNT(*) FROM subscription_items')[0], 0)
            self.assertEqual(self.db.one('SELECT COUNT(*) FROM subscription_targets')[0], 0)


if __name__ == '__main__':
    unittest.main()
