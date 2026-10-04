import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.catalog import list_catalog, remove_catalog_item, update_catalog_item
from ustracker.db import Database
from ustracker.services import create_catalog, create_client, create_subscription


class AJ11CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def test_costs_can_be_added_and_removed_after_creation(self):
        item = create_catalog(self.db, 1, {'description': 'Plano', 'category': 'Mensal', 'price': '100,00', 'cost': '10,00'})
        item = update_catalog_item(self.db, 1, item['id'], {'expected_revision': item['revision'], 'cost_components': [
            {'description': 'Chip', 'amount': '10,00'}, {'description': 'Plataforma', 'amount': '15,00'}]})
        self.assertEqual(item['cost_cents'], 2500)
        item = update_catalog_item(self.db, 1, item['id'], {'expected_revision': item['revision'], 'cost_components': [
            {'description': 'Plataforma', 'amount': '15,00'}]})
        self.assertEqual(item['cost_cents'], 1500)
        self.assertEqual(len(item['cost_components']), 1)

    def test_unused_is_deleted_and_used_is_archived(self):
        unused = create_catalog(self.db, 1, {'description': 'Sem uso', 'category': 'Avulsa', 'price': '5,00'})
        self.assertTrue(remove_catalog_item(self.db, 1, unused['id'])['deleted'])
        used = create_catalog(self.db, 1, {'description': 'Usado', 'category': 'Mensal', 'price': '5,00'})
        client = create_client(self.db, 1, {'legal_name': 'C', 'email': 'c@example.test',
                                            'documents': [{'type': 'RG', 'number': 'RG-AJ11-001', 'is_primary': True}]})
        create_subscription(self.db, 1, {'client_id': client['id'], 'start_on': '2026-10-01', 'items': [{'catalog_id': used['id'], 'quantity': 1}]})
        result = remove_catalog_item(self.db, 1, used['id'])
        self.assertTrue(result['archived'])
        rows = {r['id']: r for r in list_catalog(self.db)}
        self.assertNotIn(unused['id'], rows)
        self.assertEqual(rows[used['id']]['active'], 0)
        self.assertEqual(rows[used['id']]['usage_count'], 1)


if __name__ == '__main__':
    unittest.main()
