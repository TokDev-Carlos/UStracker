"""C-09 — Lixeira de 14 dias: tudo que é excluído no sistema pode voltar por 14 dias e depois some de vez."""
import io, os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'
from PIL import Image
from ustracker import media
from ustracker.catalog import list_catalog, remove_catalog_item
from ustracker.db import Database
from ustracker.expenses import create_company_expense, delete_expense, expense_rows
from ustracker.services import archive_clients, create_catalog, create_client
from ustracker.trash import list_trash, purge_due, restore

NOW = datetime.now(timezone.utc)


class TrashTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'production', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'Cliente Lixeira', 'email': 'l@x.test', 'documents': [{'type': 'RG', 'number': 'RG-C09-1', 'is_primary': True}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_expense_catalog_media_client_go_to_trash_and_come_back(self):
        e = create_company_expense(self.db, 1, {'category': 'Outros', 'description': 'Errada', 'amount': '9,90', 'repeat': 'ONCE'})
        delete_expense(self.db, 1, e['id'])
        c = create_catalog(self.db, 1, {'description': 'Produto X', 'category': 'Avulsa', 'price': '5,00', 'cost_components': [{'description': 'a', 'amount': '1,00'}, {'description': 'b', 'amount': '2,00'}]})
        remove_catalog_item(self.db, 1, c['id'])
        buf = io.BytesIO(); Image.new('RGB', (32, 32)).save(buf, 'PNG')
        m = media.store(self.root, self.db, 1, b'k' * 32, 'client', self.client['id'], buf.getvalue())
        media.remove(self.root, self.db, 1, m['id'])
        archive_clients(self.db, 1, [self.client['id']])
        items = list_trash(self.db)
        self.assertEqual(sorted(i['entity_type'] for i in items), ['catalog', 'client', 'expense', 'media'])
        self.assertTrue(all(i['days_left'] == 14 for i in items))
        for i in items:
            restore(self.db, 1, i['id'])
        self.assertIn(e['id'], [r['id'] for r in expense_rows(self.db)])
        restored = next(r for r in list_catalog(self.db) if r['id'] == c['id'])
        self.assertEqual(restored['cost_cents'], 300)
        self.assertGreater(len(media.load(self.root, self.db, b'k' * 32, m['id'], 'thumb')[0]), 10)
        self.assertEqual(self.db.one('SELECT archived FROM clients WHERE id=?', (self.client['id'],))[0], 0)
        self.assertEqual(list_trash(self.db), [])

    def test_purge_after_14_days_erases_payload_and_files(self):
        buf = io.BytesIO(); Image.new('RGB', (32, 32)).save(buf, 'PNG')
        m = media.store(self.root, self.db, 1, b'k' * 32, 'client', self.client['id'], buf.getvalue())
        media.remove(self.root, self.db, 1, m['id'])
        self.assertEqual(purge_due(self.root, self.db, 1, at=NOW + timedelta(days=13))['purged'], 0)
        out = purge_due(self.root, self.db, 1, at=NOW + timedelta(days=14, minutes=1))
        self.assertEqual(out['purged'], 1)
        self.assertEqual(len(out['erased_files']), 2)
        self.assertFalse(list((self.root / 'UserData' / 'Media' / 'production').glob(m['id'] + '*')))
        self.assertEqual(self.db.one("SELECT payload FROM trash")[0], '{}')
        tid = self.db.one('SELECT id FROM trash')[0]
        with self.assertRaises(ValueError):
            restore(self.db, 1, tid)

    def test_catalog_code_reused_meanwhile_gets_new_code_on_restore(self):
        c = create_catalog(self.db, 1, {'description': 'A', 'category': 'Avulsa', 'price': '1,00'})
        remove_catalog_item(self.db, 1, c['id'])
        create_catalog(self.db, 1, {'description': 'B', 'category': 'Avulsa', 'price': '1,00'})  # takes the same next code
        restore(self.db, 1, list_trash(self.db)[0]['id'])
        codes = [r['code'] for r in list_catalog(self.db)]
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == '__main__':
    unittest.main()
