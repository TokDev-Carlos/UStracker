"""H-13 (2.5.0) — toda instalação, venha de qual versão vier, começa a 2.5 limpa (só Adm Global):
backup completo conferido por SHA-256 antes de apagar; tudo ou nada; uma vez só."""
import hashlib, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import activation


def old_install(root: Path) -> None:
    ud = root / 'UserData'
    for rel, data in {'Auth/auth.db': b'acessos-2.2', 'Auth/vault.json': b'{}', 'Production/ustracker.db': b'clientes-2.2',
                      'Test/ustracker.db': b'teste', 'Media/production/f.webp.aead': b'foto', 'Public/production/view.json': b'{}',
                      'Backups/UStracker_production_old.usbk': b'bk', 'State/cloud.json': b'{"x":1}', 'State/adm-global.ok': b'x',
                      'State/station.json': b'{}', 'Logs/erros.log': b'log', 'Updates/pending.json': b'{}'}.items():
        p = ud / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)


class InicioLimpo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.root = self.base / 'app'; self.backups = self.base / 'UStracker_Backups'
        os.environ['USTRACKER_BACKUPS'] = str(self.backups)

    def tearDown(self):
        os.environ.pop('USTRACKER_BACKUPS', None); self.tmp.cleanup()

    def test_old_version_is_backed_up_then_cleaned_once(self):
        old_install(self.root)
        out = activation.clean_start(self.root)
        self.assertTrue(out['cleaned'])
        dest = Path(out['backup'])
        self.assertTrue(dest.parent == self.backups and dest.name.startswith('Pre-2.5_'))
        self.assertEqual((dest / 'Production' / 'ustracker.db').read_bytes(), b'clientes-2.2')
        sums = json.loads((dest / 'SHA256SUMS.json').read_text(encoding='utf-8'))
        self.assertEqual(sums['Auth/auth.db'], hashlib.sha256(b'acessos-2.2').hexdigest())
        ud = self.root / 'UserData'
        for gone in ('Auth/auth.db', 'Production', 'Test', 'Media', 'Public', 'Backups', 'State/cloud.json', 'State/adm-global.ok', 'State/station.json'):
            self.assertFalse((ud / gone).exists(), gone)
        self.assertTrue((ud / 'Logs' / 'erros.log').exists()); self.assertTrue((ud / 'Updates' / 'pending.json').exists())
        self.assertTrue((ud / 'State' / activation.CLEAN_MARKER).exists())
        (ud / 'Production').mkdir(); (ud / 'Production' / 'ustracker.db').write_bytes(b'dados-novos-2.5')
        self.assertFalse(activation.clean_start(self.root)['cleaned'], 'uma vez só')
        self.assertEqual((ud / 'Production' / 'ustracker.db').read_bytes(), b'dados-novos-2.5')

    def test_fresh_install_only_marks(self):
        out = activation.clean_start(self.root)
        self.assertFalse(out['cleaned']); self.assertIsNone(out['backup'])
        self.assertTrue((self.root / 'UserData' / 'State' / activation.CLEAN_MARKER).exists())
        self.assertFalse(self.backups.exists())

    def test_backup_that_does_not_match_removes_nothing(self):
        old_install(self.root)
        real = activation._sha256_file
        def corrupt(path):
            return 'x' * 64 if 'Pre-2.5_' in str(path) else real(path)
        with mock.patch.object(activation, '_sha256_file', side_effect=corrupt):
            with self.assertRaises(OSError):
                activation.clean_start(self.root)
        self.assertEqual((self.root / 'UserData' / 'Production' / 'ustracker.db').read_bytes(), b'clientes-2.2')
        self.assertFalse((self.root / 'UserData' / 'State' / activation.CLEAN_MARKER).exists())


if __name__ == '__main__':
    unittest.main()
