"""G-02 — zerar tudo uma vez (Release 2): pedido interno, executado no próximo login do Administrador.

Apaga clientes, frotas, financeiro, fotos, ambiente Teste, usuários não administradores e pacotes próprios;
mantém administradores, configurações da empresa (nome, marca, chave da placa) e a ligação com a nuvem.
A nuvem recebe o estado vazio e perde fotos e pontos antigos. Roda uma vez só.
"""
import io, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from PIL import Image
from ustracker import media
from ustracker.auth import AuthService
from ustracker.cloud import CloudClient, CloudSync
from ustracker.db import Database
from ustracker.factory_reset import request_reset, reset_pending, run_if_requested
from ustracker.services import create_client

NODE = shutil.which('node')
PW = 'senha-admin-1234'


def doc(n):
    return {'legal_name': f'Cliente {n}', 'email': f'c{n}@x.test', 'documents': [{'type': 'RG', 'number': f'RG-G02-{n}', 'is_primary': True}]}


@unittest.skipUnless(NODE, 'node not available')
class FactoryReset(unittest.TestCase):
    def setUp(self):
        self.proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        info = json.loads(self.proc.stdout.readline())
        self.base, self.secret = f"http://127.0.0.1:{info['port']}", info['secret']
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name) / 'A'
        (self.root / 'UserData').mkdir(parents=True)

    def tearDown(self):
        self.proc.terminate(); self.proc.wait(5); self.tmp.cleanup()

    def test_reset_once_keeps_admins_settings_and_empties_cloud(self):
        auth = AuthService(self.root); auth.bootstrap('Admin', PW)
        s = auth.login('Admin', PW, 'production'); db = Database(self.root, 'production', s.db_key)
        from ustracker.station import ensure_station
        ensure_station(self.root, db)
        c = create_client(db, 1, doc(1)); create_client(db, 1, doc(2))
        buf = io.BytesIO(); Image.new('RGB', (32, 32), (9, 9, 9)).save(buf, 'PNG')
        media.store(self.root, db, 1, s.media_key, 'client', c['id'], buf.getvalue())
        with db.transaction() as con:
            con.execute("INSERT INTO settings(key,value,updated_at) VALUES('company_display_name','Minha Empresa','x')")
            con.execute("INSERT INTO settings(key,value,updated_at) VALUES('placa_master_key','SELADA','x')")
        t = auth.login('Admin', PW, 'test'); create_client(Database(self.root, 'test', t.db_key), 1, doc(3))
        pkg = auth.save_package(s, {'title': 'Próprio', 'permissions': ['clients.view']})
        auth.create_user(s, {'name': 'ana', 'password': '1234', 'package_id': pkg['id']})
        cloud = CloudSync(self.root, auth, debounce=0)
        cloud.connect(s, self.base + '/exec', self.secret)
        client = CloudClient(self.base + '/exec', self.secret)
        self.assertEqual(len(client.call('list_blobs', {})['names']), 2)
        gen_before = client.call('ping', {})['head']['generation']

        self.assertIsNone(run_if_requested(self.root, auth, s, cloud), 'sem pedido, nada acontece')
        request_reset(self.root)
        self.assertTrue(reset_pending(self.root))
        user = auth.login('ana', '1234', 'production')
        self.assertIsNone(run_if_requested(self.root, auth, user, cloud), 'só Administrador executa')
        self.assertTrue(reset_pending(self.root))

        s = auth.login('Admin', PW, 'production')
        out = run_if_requested(self.root, auth, s, cloud)
        self.assertEqual(out['clients_removed'], 2)
        self.assertFalse(reset_pending(self.root), 'roda uma vez só')
        db = Database(self.root, 'production', s.db_key)
        self.assertEqual(db.one('SELECT COUNT(*) FROM clients')[0], 0)
        self.assertEqual(db.one('SELECT COUNT(*) FROM media')[0], 0)
        settings = dict(db.query('SELECT key,value FROM settings'))
        self.assertEqual(settings['company_display_name'], 'Minha Empresa')
        self.assertEqual(settings['placa_master_key'], 'SELADA')
        self.assertFalse(any((self.root / 'UserData' / 'Media' / 'production').glob('*')), 'fotos apagadas')
        t = auth.login('Admin', PW, 'test')
        self.assertEqual(Database(self.root, 'test', t.db_key).one('SELECT COUNT(*) FROM clients')[0], 0)
        with self.assertRaises(ValueError):
            auth.login('ana', '1234')
        self.assertEqual(sorted(p['id'] for p in auth.list_packages()), ['GERENTE', 'OPERADOR'])
        self.assertIsNone(auth.get_session(user.token), 'sessão do usuário removido cai')

        cloud.sync_now(s)
        self.assertEqual(client.call('list_blobs', {})['names'], [], 'fotos saem da nuvem')
        head = client.call('ping', {})['head']
        self.assertEqual(head['generation'], gen_before + 1, 'sequência continua, sem conflito')
        items = client.call('list_snapshots', {'kind': 'db'}).get('items', [])
        self.assertEqual(len(items), 1, 'pontos antigos removidos')
        self.assertEqual(items[0]['meta']['counts']['clients'], 0)
        self.assertIsNone(run_if_requested(self.root, auth, s, cloud))


if __name__ == '__main__':
    unittest.main()


class ResetOnLogin(unittest.TestCase):
    def test_marker_file_is_ignored_at_login(self):
        """2.2.0 security: a file dropped in UserData/State must never erase data at the next sign in."""
        from tests.test_g01_release2 import call
        from ustracker.server import create_app
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); app = create_app(root)
            app.state.auth.bootstrap('Admin', PW)
            s = app.state.auth.login('Admin', PW, 'production')
            create_client(Database(root, 'production', s.db_key), 1, doc(9))
            request_reset(root)
            self.assertEqual(call(app, 'POST', '/api/v1/auth/login', {'name': 'Admin', 'password': PW, 'environment': 'production'}, precsrf=True), 200)
            self.assertEqual(Database(root, 'production', s.db_key).one('SELECT COUNT(*) FROM clients')[0], 1)
            app.state.cloud.stop()
