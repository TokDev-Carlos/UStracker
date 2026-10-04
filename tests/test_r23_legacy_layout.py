"""R23 — data written by the 1.001 System+Data install keeps working after promotion (Data -> UserData)."""
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from PIL import Image

from ustracker import media
from ustracker.attachments import load_attachment, store_attachment
from ustracker.db import Database
from ustracker.paths import resolve_stored_path
from ustracker.services import create_client

KEY = b'k' * 32


class LegacyLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'production', b'0' * 32)
        self.client = create_client(self.db, 1, {'legal_name': 'C', 'email': 'c@example.test',
                                                 'documents': [{'type': 'RG', 'number': 'RG-R23-001', 'is_primary': True}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolver_accepts_both_layouts_and_slash_styles(self):
        base = (self.root / 'UserData').resolve()
        for stored in ('Data/Media/production/a.webp.aead', 'UserData/Media/production/a.webp.aead',
                       'UserData\\Media\\production\\a.webp.aead', 'data\\Media\\production\\a.webp.aead'):
            self.assertEqual(resolve_stored_path(self.root, stored), base / 'Media' / 'production' / 'a.webp.aead')
        for bad in ('/etc/passwd', 'C:\\x', '../Data/x', 'Data/../../x', 'System/x', ''):
            with self.assertRaises(ValueError):
                resolve_stored_path(self.root, bad)

    def test_media_and_attachments_stored_with_data_prefix_still_load(self):
        buf = io.BytesIO(); Image.new('RGB', (64, 64), (1, 2, 3)).save(buf, 'PNG')
        rec = media.store(self.root, self.db, 1, KEY, 'client', self.client['id'], buf.getvalue())
        att = store_attachment(self.root, self.db, 1, KEY, 'client', self.client['id'], 'a.pdf', 'application/pdf', b'%PDF-1.4\n%%EOF\n')
        self.assertTrue(rec['variant_path'].startswith('UserData/'))
        with self.db.transaction() as con:  # rewrite rows as the 1.001 install stored them
            con.execute("UPDATE media SET variant_path=replace(variant_path,'UserData/','Data/'),thumb_path=replace(thumb_path,'UserData/','Data/')")
            con.execute("UPDATE attachments SET local_path=replace(local_path,'UserData/','Data/')")
        self.assertGreater(len(media.load(self.root, self.db, KEY, rec['id'], 'thumb')[0]), 10)
        self.assertTrue(load_attachment(self.root, self.db, KEY, att['id'])[0].startswith(b'%PDF'))
        media.remove(self.root, self.db, 1, rec['id'])
        self.assertFalse(any((self.root / 'UserData' / 'Media' / 'production').glob(rec['id'] + '*')))


if __name__ == '__main__':
    unittest.main()
