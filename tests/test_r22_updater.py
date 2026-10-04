import json, os, sys, tempfile, unittest, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from ustracker.apply_update import apply
from ustracker.update import build_signed_package


class R22UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / 'Instalação Portátil'
        (self.root / 'Trust').mkdir(parents=True)
        (self.root / 'frontend').mkdir()
        (self.root / 'version.md').write_text('1.003\n', encoding='utf-8')
        (self.root / 'VERSION.json').write_text(json.dumps({'version': '1.003', 'schema_version': 9}), encoding='utf-8')
        (self.root / 'frontend' / 'app.js').write_text('old', encoding='utf-8')
        (self.root / 'UserData').mkdir()
        (self.root / 'UserData' / 'keep.txt').write_text('dados', encoding='utf-8')
        self.key = Ed25519PrivateKey.generate()
        (self.root / 'Trust' / 'update_public_key.pem').write_bytes(self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.base = base

    def tearDown(self):
        self.tmp.cleanup()

    def _package(self, *, schema=11, to='1.004', from_version='1.003', key=None, extra=None, name='pkg.usup'):
        src = self.base / ('src-' + name)
        (src / 'frontend').mkdir(parents=True, exist_ok=True)
        (src / 'version.md').write_text(to + '\n', encoding='utf-8')
        (src / 'VERSION.json').write_text(json.dumps({'version': to, 'schema_version': schema}), encoding='utf-8')
        (src / 'frontend' / 'app.js').write_text('new', encoding='utf-8')
        for rel, text in (extra or {}).items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True); (src / rel).write_text(text, encoding='utf-8')
        return build_signed_package(src, self.base / name, from_version, to, key or self.key)

    def _state(self):
        return (self.root / 'version.md').read_text(encoding='utf-8').strip(), (self.root / 'frontend' / 'app.js').read_text(encoding='utf-8')

    def test_valid_update_switches_and_skips_intermediate_schema(self):
        journal = apply(self.root, self._package())
        self.assertEqual(journal['state'], 'ACCEPTED')
        self.assertEqual((journal['from_schema'], journal['to_schema']), (9, 11))
        self.assertEqual(self._state(), ('1.004', 'new'))
        self.assertTrue((self.root / 'UserData' / 'keep.txt').exists())
        self.assertFalse((self.root / '.update-work').exists())
        self.assertEqual([p.name for p in self.root.parent.iterdir() if p.name.startswith('Instalação')], ['Instalação Portátil'])

    def test_bad_signature_is_rejected_without_changes(self):
        with self.assertRaises(Exception):
            apply(self.root, self._package(key=Ed25519PrivateKey.generate()))
        self.assertEqual(self._state(), ('1.003', 'old'))

    def test_tampered_payload_hash_is_rejected(self):
        package = self._package()
        tampered = self.base / 'tampered.usup'
        with zipfile.ZipFile(package) as zin, zipfile.ZipFile(tampered, 'w') as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'payload/frontend/app.js': data = b'evil'
                zout.writestr(item, data)
        with self.assertRaises(Exception):
            apply(self.root, tampered)
        self.assertEqual(self._state(), ('1.003', 'old'))

    def test_schema_downgrade_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, 'schema'):
            apply(self.root, self._package(schema=8))
        self.assertEqual(self._state(), ('1.003', 'old'))
        journal = json.loads((self.root / 'UserData' / 'State' / 'update_journal.json').read_text(encoding='utf-8'))
        self.assertEqual(journal['rollback_reason'], 'update_failed_before_acceptance')

    def test_wrong_source_version_and_userdata_payload_are_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'installed version'):
            apply(self.root, self._package(from_version='1.002', name='v.usup'))
        with self.assertRaisesRegex(RuntimeError, 'UserData'):
            apply(self.root, self._package(extra={'UserData/x.txt': 'x'}, name='u.usup'))
        self.assertEqual((self.root / 'UserData' / 'keep.txt').read_text(encoding='utf-8'), 'dados')

    def test_failed_post_switch_healthcheck_restores_previous_files(self):
        package = self._package(extra={'version.md': '9.999\n'}, name='h.usup')
        with self.assertRaisesRegex(RuntimeError, 'post-switch'):
            apply(self.root, package)
        self.assertEqual(self._state(), ('1.003', 'old'))
        self.assertFalse((self.root / '.update-work').exists())


if __name__ == '__main__':
    unittest.main()
