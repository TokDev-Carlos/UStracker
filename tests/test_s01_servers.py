"""S-01..S-03 — dois Servidores no mesmo banco: vez de gravar automática, dados e usuários chegam sozinhos."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.auth import AuthService
from ustracker.cloud import CloudError, CloudSync, apply_pending_restore, restore_from_cloud
from ustracker.db import Database
from ustracker.services import create_client
from ustracker.station import ensure_station

NODE = shutil.which('node')
PW = 'senha-servidor-1'


@unittest.skipUnless(NODE, 'node not available')
class TwoServers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        info = json.loads(cls.proc.stdout.readline())
        cls.url = f"http://127.0.0.1:{info['port']}/exec"; cls.secret = info['secret']

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(5)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, db, n):
        return create_client(db, 1, {'legal_name': f'Cliente {n}', 'email': f'{n}@x.test', 'documents': [{'type': 'RG', 'number': f'RG-S01-{n}', 'is_primary': True}]})

    def test_two_servers_share_data_users_and_take_turns(self):
        # Servidor 1
        ra = self.dir / 'A'; (ra / 'UserData').mkdir(parents=True)
        auth_a = AuthService(ra); auth_a.bootstrap('Admin', PW)
        sa = auth_a.login('Admin', PW); db_a = Database(ra, 'production', sa.db_key)
        self.assertEqual(ensure_station(ra, db_a)['name'], 'UStracker Servidor 1')
        cloud_a = CloudSync(ra, auth_a, debounce=0)
        cloud_a.connect(sa, self.url, self.secret, mode='replace')
        auth_a.create_user(sa, {'name': 'operador', 'password': '1234', 'package_id': 'OPERADOR'})
        cloud_a.acquire_turn(sa); self.client(db_a, 'A1'); cloud_a.mark_dirty(); cloud_a.sync_now(sa)
        # Servidor 2: instala, entra com usuário e senha → dados e usuários da empresa
        rb = self.dir / 'B'; (rb / 'UserData').mkdir(parents=True)
        restore_from_cloud(rb, self.url, self.secret)
        auth_b = AuthService(rb); cloud_b = CloudSync(rb, auth_b, debounce=0); cloud_b.pending_secret = self.secret
        sb = auth_b.login('operador', '1234'); db_b0 = Database(rb, 'production', sb.db_key)
        apply_pending_restore(rb, db_b0, sb, cloud_b)
        db_b = Database(rb, 'production', sb.db_key)
        self.assertEqual(db_b.one("SELECT COUNT(*) FROM clients WHERE legal_name='Cliente A1'")[0], 1)
        self.assertEqual(ensure_station(rb, db_b)['name'], 'UStracker Servidor 2')
        # Servidor 1 ainda com a vez → Servidor 2 espera e avisa quem está salvando
        with self.assertRaises(CloudError) as ctx:
            cloud_b.acquire_turn(sb, wait=0)
        self.assertEqual(ctx.exception.code, 'BUSY'); self.assertIn('Servidor 1', ctx.exception.detail)
        cloud_a.release_turn(sa)
        cloud_b.acquire_turn(sb); self.client(db_b, 'B1'); cloud_b.mark_dirty(); cloud_b.sync_now(sb); cloud_b.release_turn(sb)
        # Servidor 1 recebe sozinho
        before = cloud_a.data_version
        self.assertTrue(cloud_a.pull(sa)); self.assertGreater(cloud_a.data_version, before)
        self.assertEqual(Database(ra, 'production', sa.db_key).one("SELECT COUNT(*) FROM clients")[0], 2)
        names = [r[0] for r in Database(ra, 'production', sa.db_key).query('SELECT name FROM stations ORDER BY name')]
        self.assertEqual(names, ['UStracker Servidor 1', 'UStracker Servidor 2'])
        # usuário criado no Servidor 2 entra no Servidor 1
        sb_admin = auth_b.login('Admin', PW)
        auth_b.create_user(sb_admin, {'name': 'gerente', 'password': '5678', 'package_id': 'GERENTE'})
        cloud_b.acquire_turn(sb_admin); cloud_b.mark_dirty(); cloud_b.sync_now(sb_admin); cloud_b.release_turn(sb_admin)
        cloud_a.pull(sa)
        self.assertEqual(auth_a.login('gerente', '5678').package_title, 'Gerente')


if __name__ == '__main__':
    unittest.main()
