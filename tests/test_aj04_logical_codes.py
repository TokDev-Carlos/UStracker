import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle, create_transfer_case, complete_transfer_case
from ustracker.services import (create_catalog, create_client, create_client_company, create_subscription,
                                search_client_entities)


class AJ04LogicalCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'test', b'0' * 32)
        self.n = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _client(self, name):
        self.n += 1
        client = create_client(self.db, 1, {'legal_name': name, 'email': f'{self.n}@example.test',
                                            'documents': [{'type': 'RG', 'number': f'AJ04-{self.n}', 'is_primary': True}]})
        company = create_client_company(self.db, 1, client['id'], {'legal_name': f'Empresa {name}', 'is_primary': True})
        return client, company

    def _vehicle(self, client_id, plate, fleet_id=None):
        return create_vehicle(self.db, 1, {'client_id': client_id, 'fleet_id': fleet_id, 'plate': plate, 'type': 'Carro',
                                           'brand': 'Marca', 'model': 'Modelo', 'year': 2026})

    def _code(self, table, entity_id):
        return self.db.one(f'SELECT code FROM {table} WHERE id=?', (entity_id,))[0]

    def test_codes_are_issued_per_client_and_uuid_is_kept(self):
        a, company = self._client('Alfa')
        b, _ = self._client('Beta')
        self.assertEqual(self._code('clients', a['id']), 'CLI-0001')
        self.assertEqual(self._code('clients', b['id']), 'CLI-0002')
        fleet = create_fleet(self.db, 1, {'client_id': a['id'], 'client_company_id': company['id'], 'name': 'Frota'})
        v1 = self._vehicle(a['id'], 'AAA1A11', fleet['id'])
        v2 = self._vehicle(a['id'], 'AAA1A12')
        vb = self._vehicle(b['id'], 'BBB1B11')
        self.assertEqual(self._code('fleets', fleet['id']), 'CLI-0001-F01')
        self.assertEqual(self._code('vehicles', v1['id']), 'CLI-0001-V01')
        self.assertEqual(self._code('vehicles', v2['id']), 'CLI-0001-V02')
        self.assertEqual(self._code('vehicles', vb['id']), 'CLI-0002-V01')
        self.assertEqual(len(v1['id']), 36)
        plan = create_catalog(self.db, 1, {'description': 'Plano', 'category': 'Mensal', 'price': '10.00', 'cost': '0.00'})
        sub = create_subscription(self.db, 1, {'client_id': a['id'], 'start_on': '2026-10-01',
                                               'items': [{'catalog_id': plan['id'], 'quantity': 1}]})
        self.assertEqual(sub['code'], 'CLI-0001-A01')
        self.assertEqual(sub['client_code'], 'CLI-0001')

    def test_numbers_are_not_reused_after_archive(self):
        a, _ = self._client('Alfa')
        v1 = self._vehicle(a['id'], 'AAA1A11')
        with self.db.transaction() as con:
            con.execute('UPDATE vehicles SET archived=1 WHERE id=?', (v1['id'],))
        v2 = self._vehicle(a['id'], 'AAA1A12')
        self.assertEqual(self._code('vehicles', v2['id']), 'CLI-0001-V02')

    def test_code_is_immutable(self):
        a, _ = self._client('Alfa')
        with self.assertRaises(Exception):
            with self.db.transaction() as con:
                con.execute("UPDATE clients SET code='CLI-9999' WHERE id=?", (a['id'],))
        self.assertEqual(self._code('clients', a['id']), 'CLI-0001')

    def test_transfer_issues_new_code_and_retires_old(self):
        a, _ = self._client('Alfa')
        b, _ = self._client('Beta')
        self._vehicle(b['id'], 'BBB1B11')
        v = self._vehicle(a['id'], 'AAA1A11')
        case = create_transfer_case(self.db, 1, v['id'], {'client_id': b['id'], 'effective_from': '2099-01-01', 'expected_revision': 1})
        complete_transfer_case(self.db, 1, case['id'])
        self.assertEqual(self._code('vehicles', v['id']), 'CLI-0002-V02')
        retired = self.db.one("SELECT retired_at FROM logical_codes WHERE code='CLI-0001-V01'")[0]
        self.assertIsNotNone(retired)
        nxt = self._vehicle(a['id'], 'AAA1A12')
        self.assertEqual(self._code('vehicles', nxt['id']), 'CLI-0001-V02')

    def test_schema9_backfill_is_deterministic_and_reentrant(self):
        a, _ = self._client('Alfa')
        self._client('Beta')
        v = self._vehicle(a['id'], 'AAA1A11')
        with self.db.transaction() as con:
            for t in ('vehicles', 'fleets', 'subscriptions', 'direct_sales', 'payments', 'clients'):
                con.execute(f'DROP TRIGGER IF EXISTS trg_code_immutable_{t}')
                con.execute(f'UPDATE {t} SET code=NULL')
            con.execute('DELETE FROM logical_codes'); con.execute('DELETE FROM code_counters')
            con.execute("UPDATE meta SET value='9' WHERE key='schema_version'")
        Database(self.root, 'test', b'0' * 32)
        again = Database(self.root, 'test', b'0' * 32)
        self.assertEqual(again.one("SELECT value FROM meta WHERE key='schema_version'")[0], '14')
        self.assertEqual(self._code('clients', a['id']), 'CLI-0001')
        self.assertEqual(self._code('vehicles', v['id']), 'CLI-0001-V01')
        self.assertEqual(again.one('SELECT COUNT(*) FROM logical_codes')[0], 3)
        nxt = self._vehicle(a['id'], 'AAA1A12')
        self.assertEqual(self._code('vehicles', nxt['id']), 'CLI-0001-V02')

    def test_search_accepts_logical_codes(self):
        a, _ = self._client('Alfa')
        self._client('Beta')
        self._vehicle(a['id'], 'AAA1A11')
        self.assertEqual([r['id'] for r in search_client_entities(self.db, 'cli-0001')], [a['id']])
        self.assertEqual([r['code'] for r in search_client_entities(self.db, 'CLI-0001-V01')], ['CLI-0001'])


if __name__ == '__main__':
    unittest.main()
