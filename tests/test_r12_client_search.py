import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.services import search_client_entities


class R12ClientSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        ts = '2026-10-02T00:00:00+00:00'
        with self.db.transaction() as con:
            for index in range(1005):
                client_id = f'c{index:04d}'
                name = f'Cliente {index:04d}'
                phone = f'1190000{index:04d}'
                if index == 0:
                    name = 'Carlos Ávila'
                if index == 3:
                    phone = '(11) 99999-0003'
                con.execute(
                    '''INSERT INTO clients(id,legal_name,email,phone,status,archived,revision,created_at,updated_at)
                       VALUES(?,?,?,?,?,0,1,?,?)''',
                    (client_id, name, ('carlos@example.test' if index == 0 else f'cliente{index}@example.test'), phone, 'ACTIVE', ts, ts),
                )
                document = 'DOC-ESPECIAL' if index == 2 else f'RG{index:06d}'
                con.execute(
                    '''INSERT INTO client_documents(id,client_id,type,number,normalized_number,is_primary,archived,created_at,updated_at)
                       VALUES(?,?,?,?,?,1,0,?,?)''',
                    (f'd{index:04d}', client_id, 'RG', document, document.replace('-', ''), ts, ts),
                )
            con.execute(
                '''INSERT INTO client_companies(id,client_id,legal_name,is_primary,archived,created_at,updated_at)
                   VALUES('company-special','c0001','Órbita Dados',1,0,?,?)''',
                (ts, ts),
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_search_is_accent_case_and_field_insensitive(self):
        self.assertEqual([row['id'] for row in search_client_entities(self.db, 'CARLOS AVILA')], ['c0000'])
        self.assertEqual([row['id'] for row in search_client_entities(self.db, 'orbita dados')], ['c0001'])
        self.assertEqual([row['id'] for row in search_client_entities(self.db, 'doc-especial')], ['c0002'])
        self.assertEqual([row['id'] for row in search_client_entities(self.db, '99999-0003')], ['c0003'])
        result = search_client_entities(self.db, 'carlos')
        self.assertEqual(result[0]['display_name'], 'Carlos Ávila')
        self.assertIn('primary_document', result[0])
        self.assertIn('primary_company', result[0])

    def test_empty_query_and_limits_are_bounded_with_stable_order(self):
        self.assertEqual(search_client_entities(self.db, ''), [])
        default = search_client_entities(self.db, 'cliente')
        capped = search_client_entities(self.db, 'cliente', limit=1000)
        small = search_client_entities(self.db, 'cliente', limit=3)
        self.assertEqual((len(default), len(capped), len(small)), (20, 30, 3))
        self.assertEqual([row['display_name'] for row in small], ['Cliente 0001', 'Cliente 0002', 'Cliente 0003'])


if __name__ == '__main__':
    unittest.main()
