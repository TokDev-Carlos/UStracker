"""H-18 (2.6 Etapa 2) — backup diário conferido, avisos para administradores, Diagnóstico e pacote de suporte."""
import io, json, os, sys, tempfile, unittest, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import diagnostics as dg
from ustracker.access import GERENTE, required_permission
from ustracker.backup import maybe_automatic_backup
from ustracker.db import Database
from ustracker.services import create_client

VRK = b'v' * 32
KEY = b'0' * 32
UTC = timezone.utc


class Diagnostico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'production', KEY)
        create_client(self.db, 1, {'legal_name': 'Maria Teste', 'email': 'maria@exemplo.com', 'documents': [{'type': 'CPF', 'number': '52998224725', 'is_primary': True}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_daily_backup_is_checked_by_opening_the_copy(self):
        path = maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY)
        st = dg.backup_status(self.root, 'production')
        self.assertTrue(st['verified']); self.assertEqual(st['backup'], path.name)
        self.assertEqual(st['counts']['clients'], 1, 'a cópia foi aberta e conferida (não só o arquivo)')
        self.assertEqual(dg.alerts(self.root, cloud=None), [])

    def test_failed_check_is_recorded_and_alerts(self):
        orig = dg.check_backup
        dg.check_backup = lambda *a, **k: (_ for _ in ()).throw(ValueError('cópia corrompida'))
        try:
            maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY)
        finally:
            dg.check_backup = orig
        st = dg.backup_status(self.root, 'production')
        self.assertFalse(st['verified']); self.assertIn('corrompida', st['error'])
        self.assertIn('backup_failed', [a['code'] for a in dg.alerts(self.root, cloud=None)])
        # falhou: tenta de novo em 1 hora (não espera 24 h)
        self.assertIsNone(maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY), 'não repete na mesma hora')
        marker = self.root / 'UserData' / 'State' / 'auto_backup_production.json'
        data = json.loads(marker.read_text()); data['at'] = (datetime.now(UTC) - timedelta(minutes=61)).isoformat(); marker.write_text(json.dumps(data))
        self.assertIsNotNone(maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY))
        self.assertTrue(dg.backup_status(self.root, 'production')['verified'])

    def test_stale_backup_and_cloud_alerts(self):
        maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY)
        marker = self.root / 'UserData' / 'State' / 'auto_backup_production.json'
        data = json.loads(marker.read_text()); old = (datetime.now(UTC) - timedelta(days=2, hours=1)).isoformat()
        data['at'] = data['last_verified_at'] = old; marker.write_text(json.dumps(data))
        cloud = {'enabled': True, 'pending_since': (datetime.now(UTC) - timedelta(days=1, hours=1)).timestamp(), 'conflict': None}
        codes = [a['code'] for a in dg.alerts(self.root, cloud=cloud)]
        self.assertEqual(sorted(codes), ['backup_stale', 'cloud_stale'])
        self.assertIn('cloud_conflict', [a['code'] for a in dg.alerts(self.root, cloud={'enabled': True, 'conflict': 'x'})])
        for a in dg.alerts(self.root, cloud=cloud):
            self.assertTrue(a['message'] and a['level'] in ('warn', 'error'))

    def test_snapshot_has_the_essentials(self):
        maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY)
        snap = dg.snapshot(self.root, self.db, cloud={'enabled': False}, users_active=3)
        for k in ('version', 'schema_version', 'cloud', 'backup', 'disk', 'errors', 'users_active', 'stations', 'generated_at'):
            self.assertIn(k, snap)
        self.assertGreater(snap['disk']['free_gb'], 0)

    def test_support_package_has_no_secrets_nor_client_data(self):
        log = self.root / 'UserData' / 'Logs' / 'erros.log'; log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('--- 2026-10-08T10:00:00 POST /api/v1/clients cid=1\nValueError: cliente Maria Teste 529.982.247-25 maria@exemplo.com '
                       'token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 github_pat_11ABCDEFG_xyz key=x\'00112233445566778899aabbccddeeff\' '
                       'secret=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCd\n', encoding='utf-8')
        maybe_automatic_backup(self.root, self.db, VRK, db_key=KEY)
        blob = dg.support_package(self.root, self.db, cloud={'enabled': False}, users_active=1)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            text = ''.join(z.read(n).decode('utf-8', 'replace') for n in names)
        self.assertIn('diagnostico.json', names); self.assertIn('erros.log', names)
        self.assertFalse([n for n in names if n.endswith(('.db', '.usbk', '.json')) and n != 'diagnostico.json'])
        for secret in ('Maria Teste', '529.982.247-25', '52998224725', 'maria@exemplo.com', 'ghp_ABCDEFGHIJ', 'github_pat_11ABCDEFG',
                       '00112233445566778899aabbccddeeff', 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789AbCd'):
            self.assertNotIn(secret, text, secret)
        self.assertIn('ValueError', text, 'o erro continua legível')

    def test_only_administrators(self):
        for path in ('/api/v1/system/diagnostics', '/api/v1/system/alerts', '/api/v1/system/support-package'):
            self.assertEqual(required_permission('GET', path), 'system')
        self.assertNotIn('system', GERENTE)


if __name__ == '__main__':
    unittest.main()
