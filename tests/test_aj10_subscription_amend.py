import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_vehicle
from ustracker.services import create_catalog, create_client, create_subscription, generate_charge
from ustracker.subscription_edit import amend_subscription


class AJ10AmendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'C', 'email': 'c@example.test',
                                                 'documents': [{'type': 'RG', 'number': 'RG-AJ10-001', 'is_primary': True}]})
        self.basic = create_catalog(self.db, 1, {'description': 'Básico', 'category': 'Mensal', 'price': '50,00'})
        self.plus = create_catalog(self.db, 1, {'description': 'Plus', 'category': 'Mensal', 'price': '80,00'})
        self.v1 = create_vehicle(self.db, 1, {'client_id': self.client['id'], 'plate': 'AAA1A11', 'type': 'Carro', 'brand': 'M', 'model': 'X', 'year': 2026})
        self.v2 = create_vehicle(self.db, 1, {'client_id': self.client['id'], 'plate': 'AAA1A12', 'type': 'Carro', 'brand': 'M', 'model': 'Y', 'year': 2026})
        self.sub = create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-09-01', 'target_vehicle_ids': [self.v1['id']],
                                                    'items': [{'catalog_id': self.basic['id'], 'quantity': 1}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_amend_changes_future_value_and_targets_only(self):
        old_charge = generate_charge(self.db, 1, self.sub['id'], '2026-09')
        after = amend_subscription(self.db, 1, self.sub['id'], {'expected_revision': self.sub['revision'], 'due_day': 5,
                                   'items': [{'catalog_id': self.plus['id'], 'quantity': 2}],
                                   'target_vehicle_ids': [self.v1['id'], self.v2['id']]})
        # 2.7.0: dois veículos → duas assinaturas de R$ 80 (a original fica com o veículo que já tinha)
        self.assertEqual(after['effective_total_cents'], 8000)
        self.assertEqual(after['due_day'], 5)
        self.assertEqual([t['vehicle_id'] for t in after['targets']], [self.v1['id']])
        self.assertEqual(len(after['group_ids']), 2)
        self.assertEqual(self.db.one('SELECT amount_cents FROM charges WHERE id=?', (old_charge['id'],))[0], 5000)
        self.assertEqual(generate_charge(self.db, 1, self.sub['id'], '2026-10')['amount_cents'], 8000)
        self.assertEqual(generate_charge(self.db, 1, after['group_ids'][1], '2026-10')['amount_cents'], 8000)

    def test_revision_conflict_is_atomic(self):
        with self.assertRaises(ValueError):
            amend_subscription(self.db, 1, self.sub['id'], {'expected_revision': 99, 'items': [{'catalog_id': self.plus['id']}]})
        with self.assertRaises(ValueError):
            amend_subscription(self.db, 1, self.sub['id'], {'expected_revision': self.sub['revision'],
                               'items': [{'catalog_id': self.plus['id']}], 'target_vehicle_ids': ['nope']})
        self.assertEqual(self.db.one('SELECT catalog_id FROM subscription_items WHERE subscription_id=?', (self.sub['id'],))[0], self.basic['id'])


if __name__ == '__main__':
    unittest.main()
