"""H-21 (2.7.0) — avisos de cópia de segurança: arquivo de estado antigo (antes da 2.6) não é "falha";
erro sem mensagem mostra o tipo e fica no erros.log."""
import json, os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import diagnostics as dg
from ustracker.backup import maybe_automatic_backup
from ustracker.db import Database

UTC = timezone.utc


class AvisosBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'production', b'0' * 32)
        self.marker = self.root / 'UserData' / 'State' / 'auto_backup_production.json'
        self.marker.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_old_marker_is_not_a_failure(self):
        at = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
        self.marker.write_text(json.dumps({'at': at, 'backup': 'UStracker_production_x.usbk'}))
        self.assertEqual(dg.alerts(self.root, cloud=None), [])

    def test_old_marker_older_than_2_days_only_stale(self):
        at = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        self.marker.write_text(json.dumps({'at': at, 'backup': 'x.usbk'}))
        self.assertEqual([a['code'] for a in dg.alerts(self.root, cloud=None)], ['backup_stale'])

    def test_error_without_message_shows_its_type_and_is_logged(self):
        orig = dg.check_backup
        dg.check_backup = lambda *a, **k: (_ for _ in ()).throw(PermissionError())
        try:
            maybe_automatic_backup(self.root, self.db, b'v' * 32, db_key=b'0' * 32)
        finally:
            dg.check_backup = orig
        [failed] = [a for a in dg.alerts(self.root, cloud=None) if a['code'] == 'backup_failed']
        self.assertIn('PermissionError', failed['message'])
        log = (self.root / 'UserData' / 'Logs' / 'erros.log').read_text(encoding='utf-8')
        self.assertIn('auto-backup', log); self.assertIn('PermissionError', log)


if __name__ == '__main__':
    unittest.main()
