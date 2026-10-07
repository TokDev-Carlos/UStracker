"""H-07 (2.4.0) — Cliente empresa: documento CNPJ (com dígitos verificadores) e empresa principal automática."""
import os, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database, SCHEMA_VERSION
from ustracker.clients import validate_document, infer_document_type
from ustracker.services import create_client, list_client_documents

CNPJ = '11.222.333/0001-81'


class Cnpj(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)

    def tearDown(self):
        self.tmp.cleanup()

    def test_validate(self):
        self.assertEqual(validate_document({'type': 'cnpj', 'number': CNPJ})['normalized_number'], '11222333000181')
        for bad in ('11.222.333/0001-82', '11111111111111', '1122233300018'):
            with self.assertRaises(ValueError):
                validate_document({'type': 'CNPJ', 'number': bad})
        self.assertEqual(infer_document_type(CNPJ), 'CNPJ')

    def test_company_client_gets_primary_company(self):
        c = create_client(self.db, 1, {'legal_name': 'Transportes Alfa LTDA', 'trade_name': 'Alfa',
                                       'documents': [{'type': 'CNPJ', 'number': CNPJ, 'is_primary': True}],
                                       'phone': '11999990000'})
        docs = list_client_documents(self.db, c['id'])
        self.assertEqual([d['type'] for d in docs], ['CNPJ'])
        with self.db.transaction() as con:
            rows = [dict(r) for r in con.execute('SELECT * FROM client_companies WHERE client_id=? AND archived=0', (c['id'],))]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['legal_name'], rows[0]['trade_name'], rows[0]['normalized_document'], rows[0]['is_primary']),
                         ('Transportes Alfa LTDA', 'Alfa', '11222333000181', 1))
        with self.assertRaises((ValueError, sqlite3.IntegrityError)):  # same CNPJ twice
            create_client(self.db, 1, {'legal_name': 'Outra', 'documents': [{'type': 'CNPJ', 'number': CNPJ}], 'email': 'a@b.c'})

    def test_migration_from_v14_accepts_cnpj(self):
        path = next(Path(self.tmp.name).rglob('*.db'))
        con = sqlite3.connect(path)
        con.executescript("""
            PRAGMA foreign_keys=OFF;
            ALTER TABLE client_documents RENAME TO cd_new;
            CREATE TABLE client_documents(
             id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), type TEXT NOT NULL CHECK(type IN ('CPF','RG','CNH')),
             number TEXT NOT NULL, normalized_number TEXT NOT NULL, is_primary INTEGER NOT NULL DEFAULT 0,
             archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            DROP TABLE cd_new;
            UPDATE meta SET value='14' WHERE key='schema_version';""")
        con.commit(); con.close()
        db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        with db.transaction() as c2:
            self.assertEqual(c2.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], str(SCHEMA_VERSION))
            self.assertIn("'CNPJ'", c2.execute("SELECT sql FROM sqlite_master WHERE name='client_documents'").fetchone()[0])
        create_client(db, 1, {'legal_name': 'Beta SA', 'documents': [{'type': 'CNPJ', 'number': CNPJ}], 'email': 'b@b.c'})


if __name__ == '__main__':
    unittest.main()
