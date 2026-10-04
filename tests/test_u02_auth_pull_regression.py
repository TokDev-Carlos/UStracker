"""Regressão 1.007: Usuários dava erro 500 — a nuvem trouxe um auth.db antigo (sem tabelas de usuários)
por cima do local. Regras: (1) Usuários funciona mesmo com auth.db antigo; (2) acesso local mais novo
nunca é substituído pelo da nuvem."""
import json, os, shutil, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.auth import AuthService
from ustracker.cloud import CloudSync

NODE = shutil.which('node')
PW = 'senha-regressao-1'


class OldAuthDb(unittest.TestCase):
    def test_users_work_on_auth_db_without_new_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth = AuthService(Path(tmp)); auth.bootstrap('Admin', PW); s = auth.login('Admin', PW)
            con = sqlite3.connect(Path(tmp) / 'UserData' / 'Auth' / 'auth.db')
            con.execute('DROP TABLE users'); con.execute('DROP TABLE packages'); con.commit(); con.close()
            self.assertEqual(auth.list_users(), [])
            self.assertEqual({p['id'] for p in auth.list_packages()}, {'OPERADOR', 'GERENTE'})
            auth.create_user(s, {'name': 'ana', 'password': '1234'})


@unittest.skipUnless(NODE, 'node not available')
class LocalAuthWins(unittest.TestCase):
    def test_pull_never_overwrites_newer_local_access(self):
        proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        try:
            info = json.loads(proc.stdout.readline())
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); (root / 'UserData').mkdir()
                auth = AuthService(root); auth.bootstrap('Admin', PW); s = auth.login('Admin', PW)
                cloud = CloudSync(root, auth, debounce=0)
                cloud.connect(s, f"http://127.0.0.1:{info['port']}/exec", info['secret'], mode='replace')
                cloud.state.set(auth_head_id=None)          # as after the 1.006 → 1.007 update
                auth.create_user(s, {'name': 'ana', 'password': '1234'})
                cloud.pull(s)
                self.assertEqual([u['name'] for u in auth.list_users()], ['ana'])
        finally:
            proc.terminate(); proc.wait(5); proc.stdout.close()


if __name__ == '__main__':
    unittest.main()
