"""H-03 — Aplicador de Patch: 1) esta máquina (backup + aplica + volta se falhar) e 2) todos (canal no GitHub)."""
import base64, hashlib, json, os, shutil, sys, tempfile, unittest, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools'), str(ROOT / 'tools' / 'patch')]
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import make_patch
import patch_tool as pt
from publish_update import stage
from ustracker.update_channel import _apply_here

VERSION = (ROOT / 'version.md').read_text(encoding='utf-8').strip()


class FakeGitHub:
    """Contents API in memory."""
    def __init__(self, files=None):
        self.files = dict(files or {}); self.calls = []

    def get(self, path):
        if path not in self.files:
            return {}
        data = self.files[path]
        return {'sha': hashlib.sha1(data).hexdigest(), 'content': base64.b64encode(data).decode()}

    def put(self, path, data, message, sha):
        if path in self.files and sha != hashlib.sha1(self.files[path]).hexdigest():
            raise pt.PatchError('sha mismatch')
        self.calls.append(('put', path)); self.files[path] = data

    def delete(self, path, message, sha):
        self.calls.append(('delete', path)); self.files.pop(path)


class PatchTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        self.key = Ed25519PrivateKey.generate()
        pem = self.key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        # an installed machine on the previous version
        self.root = stage(ROOT, base / 'install')
        (self.root / 'version.md').write_text('2.2.0', encoding='utf-8')
        meta = json.loads((self.root / 'VERSION.json').read_text(encoding='utf-8')); meta['version'] = '2.2.0'
        (self.root / 'VERSION.json').write_text(json.dumps(meta), encoding='utf-8')
        (self.root / 'Trust').mkdir(); (self.root / 'Trust' / 'update_public_key.pem').write_bytes(pem)
        for name in ('Auth', 'Production'):
            (self.root / 'UserData' / name).mkdir(parents=True)
        (self.root / 'UserData' / 'Auth' / 'auth.db').write_bytes(b'acessos')
        (self.root / 'UserData' / 'Production' / 'ustracker.db').write_bytes(b'clientes')
        self.patch = make_patch.make_patch(ROOT, base / 'out', 'normal', 'teste', self.key)
        self.backups = base / 'backups'
        self.runner = lambda: (_apply_here(self.root, sanity=lambda r: True), 0)[1]

    def tearDown(self):
        self.tmp.cleanup()

    def test_info_shows_from_and_to(self):
        out = pt.cmd_info(self.root, self.patch)
        self.assertEqual((out['from'], out['to'], out['newer']), ('2.2.0', VERSION, True))

    def test_apply_backs_up_data_then_updates_this_machine(self):
        out = pt.cmd_apply(self.root, self.patch, self.backups, runner=self.runner)
        self.assertEqual(out['to'], VERSION)
        self.assertEqual((self.root / 'version.md').read_text().strip(), VERSION)
        saved = Path(out['backup'])
        self.assertEqual((saved / 'Auth' / 'auth.db').read_bytes(), b'acessos')
        self.assertEqual((saved / 'Production' / 'ustracker.db').read_bytes(), b'clientes')
        self.assertEqual((self.root / 'UserData' / 'Production' / 'ustracker.db').read_bytes(), b'clientes', 'dados intactos')
        with self.assertRaises(pt.PatchError):  # same version again
            pt.cmd_apply(self.root, self.patch, self.backups, runner=self.runner)

    def test_failed_apply_keeps_the_machine_and_says_where_the_backup_is(self):
        with self.assertRaises(pt.PatchError) as ctx:
            pt.cmd_apply(self.root, self.patch, self.backups, runner=lambda: 1)
        self.assertIn('2.2.0', str(ctx.exception)); self.assertIn('Backup', str(ctx.exception))

    def test_package_from_another_key_or_tampered_is_refused(self):
        other = make_patch.make_patch(ROOT, Path(self.tmp.name) / 'other', 'normal', 'x', Ed25519PrivateKey.generate())
        with self.assertRaises(pt.PatchError):
            pt.cmd_info(self.root, other)
        bad = Path(self.tmp.name) / 'bad.uspatch'
        with zipfile.ZipFile(self.patch) as src, zipfile.ZipFile(bad, 'w') as dst:
            for name in src.namelist():
                data = src.read(name)
                dst.writestr(name, data[:-10] + b'0' * 10 if name.endswith('.usup') else data)
        with self.assertRaises(pt.PatchError):
            pt.cmd_info(self.root, bad)
        notzip = Path(self.tmp.name) / 'x.uspatch'; notzip.write_bytes(b'nada')
        with self.assertRaises(pt.PatchError):
            pt.cmd_info(self.root, notzip)

    def test_publish_only_after_this_machine_and_never_backwards(self):
        gh = FakeGitHub()
        with self.assertRaises(pt.PatchError):  # option 2 requires option 1 first
            pt.cmd_publish(self.root, self.patch, 'tok', github=gh)
        pt.cmd_apply(self.root, self.patch, self.backups, runner=self.runner)
        old = json.dumps({'version': '2.1.1', 'package': 'UStracker-2.1.1.usup'}).encode()
        gh = FakeGitHub({'updates/update.json': old, 'updates/UStracker-2.1.1.usup': b'old'})
        out = pt.cmd_publish(self.root, self.patch, 'tok', github=gh)
        self.assertEqual((out['published'], out['previous'], out['removed']), (VERSION, '2.1.1', 'UStracker-2.1.1.usup'))
        order = [p for _, p in gh.calls]
        self.assertLess(order.index(f'updates/UStracker-{VERSION}.usup'), order.index('updates/update.json'), 'pacote antes do anúncio')
        self.assertNotIn('updates/UStracker-2.1.1.usup', gh.files)
        with zipfile.ZipFile(self.patch) as z:
            self.assertEqual(json.loads(gh.files['updates/update.json'])['sig'], json.loads(z.read('update.json'))['sig'])
        with self.assertRaises(pt.PatchError):  # cloud already on this version
            pt.cmd_publish(self.root, self.patch, 'tok', github=gh)

    def test_token_is_read_from_the_file_text(self):
        self.assertEqual(pt.parse_token('#Full access: github_pat_' + 'A1' * 20), 'github_pat_' + 'A1' * 20)
        with self.assertRaises(pt.PatchError):
            pt.parse_token('nada aqui')


if __name__ == '__main__':
    unittest.main()
