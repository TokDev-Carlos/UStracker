"""H-01 (2.2.0) — computador novo é ATIVADO só pelo Adm Global; a chave da empresa não vai no instalador.

Também cobre a regressão do "Internal Server Error" na primeira entrada (auth.db antigo vindo da nuvem) e o
tratamento genérico de erros (JSON + UserData/Logs/erros.log).
"""
import asyncio, json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, unittest, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import adm_global as ag
from ustracker.cloud import CloudClient
from ustracker.db import Database
from ustracker.placa import build_placa, load_bootstrap, new_master, save_bootstrap
from ustracker.server import create_app
from ustracker.services import create_client
from tests.test_g04_adm_global import call

PIN = '4829'
LOCAL = 'senha-local-1234'
NODE = shutil.which('node')


class RepoServer:
    """Plays acesso-<Empresa> (needs the read token) and the public placa.json."""
    def __init__(self):
        self.files = {}; self.read_token = 'leitura-123'; owner = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                name = self.path.split('?')[0].rsplit('/', 1)[-1]
                private = name != 'placa.json'
                if (private and self.headers.get('Authorization') != f'Bearer {owner.read_token}') or name not in owner.files:
                    self.send_response(404); self.end_headers(); return
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(owner.files[name]).encode())
            def log_message(self, *a): pass
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.httpd.server_address[1]}'

    def stop(self): self.httpd.shutdown()


def gas():
    proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
    info = json.loads(proc.stdout.readline())
    return proc, f"http://127.0.0.1:{info['port']}/exec", info['secret']


@unittest.skipUnless(NODE, 'node not available')
class Activation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.repo = RepoServer()
        self.trust, token, self.keys = ag.create('crj', PIN, url=self.repo.base + '/token-mestre.json', read_token=self.repo.read_token)
        self.repo.files['token-mestre.json'] = token
        self.master = new_master()
        self.repo.files['company-key.json'] = ag.wrap_company_key(self.master['company_key'], self.trust)
        self.procs, self.apps = [], []

    def tearDown(self):
        for app in self.apps:
            app.state.cloud.stop(); app.state.updates.stop()
        for p in self.procs:
            p.terminate(); p.wait(5)
        self.repo.stop(); self.tmp.cleanup()

    def bank(self):
        proc, url, secret = gas(); self.procs.append(proc)
        self.repo.files['placa.json'] = build_placa([{'url': url, 'key': secret}], self.master, 1)
        return {'url': url, 'key': secret}

    def machine(self, name):
        root = self.base / name
        ag.save_trust(root, self.trust)
        save_bootstrap(root, url=self.repo.base + '/placa.json', master=self.master)
        app = create_app(root); self.apps.append(app)
        return root, app

    def activate(self, app, name='crj', pin=PIN, answer=None):
        st, body = call(app, 'POST', '/api/v1/auth/activate', {'name': name, 'password': pin}, precsrf=True)
        if st != 200 or 'challenge' not in body:
            return st, body
        return call(app, 'POST', '/api/v1/auth/activate', {'name': name, 'password': pin, 'answer': pin if answer is None else answer},
                    precsrf=True)

    def test_installer_files_carry_no_company_key(self):
        root, app = self.machine('A')
        boot = json.loads((root / 'Trust' / 'placa-bootstrap.json').read_text())
        self.assertNotIn('company_key', boot)
        self.assertIsNotNone(load_bootstrap(root))
        self.assertEqual(call(app, 'GET', '/api/v1/cloud/bootstrap')[1]['activation'], True)
        self.assertEqual(call(app, 'POST', '/api/v1/auth/bootstrap', {'name': 'X', 'password': LOCAL}, precsrf=True)[0], 403)
        self.assertEqual(call(app, 'POST', '/api/v1/auth/join', {'name': 'X', 'password': LOCAL}, precsrf=True)[0], 410)

    def test_new_company_then_second_computer_with_old_auth_schema(self):
        bank = self.bank()
        # --- computer A: empty cloud → Adm Global activates, creates the company Administrator, accesses go up at once
        root_a, app_a = self.machine('A')
        st, body = self.activate(app_a, name='outro')
        self.assertEqual(st, 422, body); self.assertIn('hint', body)
        st, body = self.activate(app_a, answer='errada')
        self.assertEqual(st, 422, body)
        st, body = self.activate(app_a, pin='9999')
        self.assertEqual(st, 422, body)
        st, body = self.activate(app_a)
        # 2.3.0: the Adm Global enters at once (no login, no ticket); the local admin is created inside
        self.assertEqual(st, 200, body); self.assertTrue(body['new_company']); self.assertTrue(body['is_global'])
        self.assertTrue(body['cloud']['connected']); self.assertNotIn('error', body['cloud'])
        self.assertTrue((root_a / 'UserData' / 'State' / 'adm-global.ok').exists(), 'marker for the installer scan')
        st_ = call(app_a, 'GET', '/api/v1/auth/setup-status')[1]
        self.assertTrue(st_['activated']); self.assertFalse(st_['local_admin'])
        self.assertEqual(call(app_a, 'POST', '/api/v1/auth/activate/admin', {'ticket': 'x'}, precsrf=True)[0], 410)
        g = next(s for s in app_a.state.auth._sessions.values() if s.kind == 'global')
        st, out = call(app_a, 'POST', '/api/v1/admin-local/create', {'name': 'Admin', 'password': LOCAL}, token=g.token, csrf=g.csrf)
        self.assertEqual(st, 200, out); self.assertTrue(out['recovery_key'])
        self.assertEqual(call(app_a, 'POST', '/api/v1/admin-local/create', {'name': 'Outro', 'password': LOCAL}, token=g.token, csrf=g.csrf)[0], 422)
        self.assertTrue(call(app_a, 'GET', '/api/v1/auth/setup-status')[1]['local_admin'])
        app_a.state.cloud.sync_now(g, force=True)
        ping = CloudClient(bank['url'], bank['key']).call('ping', {})
        self.assertTrue(ping.get('auth_head') and ping.get('head'), 'acessos e banco já estão na nuvem')
        session = app_a.state.auth.login('Admin', LOCAL)
        db = Database(root_a, 'production', session.db_key)
        create_client(db, 1, {'legal_name': 'Cliente Nuvem', 'email': 'n@x.test', 'documents': [{'type': 'RG', 'number': 'RG-H01-1', 'is_primary': True}]})
        # old version on A: the auth tables of 2.0 only (the cloud copy lacks login_lock / recovery)
        with sqlite3.connect(root_a / 'UserData' / 'Auth' / 'auth.db') as con:
            con.execute('DROP TABLE login_lock'); con.execute('DROP TABLE recovery')
        app_a.state.cloud.mark_dirty(); app_a.state.cloud.sync_now(session, force=True)
        # --- computer B: activation brings everything down and the Adm Global enters (no 500)
        root_b, app_b = self.machine('B')
        st, out = self.activate(app_b)
        self.assertEqual(st, 200, out); self.assertTrue(out['restored']); self.assertTrue(out['is_global'])
        g = app_b.state.auth.get_session(next(t for t, s in app_b.state.auth._sessions.items() if s.kind == 'global'))
        names = [r[0] for r in Database(root_b, 'production', g.db_key).query('SELECT legal_name FROM clients')]
        self.assertIn('Cliente Nuvem', names)
        self.assertEqual(app_b.state.cloud.company_key(g), self.master['company_key'])
        # the local Administrator also signs in on B (accesses came from the cloud)
        self.assertEqual(call(app_b, 'POST', '/api/v1/auth/login', {'name': 'Admin', 'password': LOCAL}, precsrf=True)[0], 200)
        # B is activated now: activation is refused
        self.assertEqual(self.activate(app_b)[0], 422)

    def test_old_cloud_not_validated_goes_to_backup_and_global_enters(self):
        """2.3.0: the company cloud holds data the Adm Global never validated (old version) -> backup + new company."""
        bank = self.bank()
        old_root = self.base / 'Old'
        old = create_app(old_root); self.apps.append(old)
        old.state.auth.bootstrap('Velho', LOCAL)            # old version: local admin, no Adm Global wrap
        s = old.state.auth.login('Velho', LOCAL)
        db = Database(old_root, 'production', s.db_key)
        create_client(db, 1, {'legal_name': 'Cliente Antigo', 'email': 'a@x.test', 'documents': [{'type': 'RG', 'number': 'RG-OLD-1', 'is_primary': True}]})
        old.state.cloud.keep_company_key(s, self.master['company_key'])
        old.state.cloud.apply_banks(s, [bank], 1)
        old.state.cloud.sync_now(s, force=True)
        old_head = CloudClient(bank['url'], bank['key']).call('ping', {})['head']['id']
        backup_dir = self.base / 'backup_old'
        os.environ['USTRACKER_BACKUP_OLD'] = str(backup_dir)
        try:
            root, app = self.machine('New')
            st, body = self.activate(app)
        finally:
            os.environ.pop('USTRACKER_BACKUP_OLD', None)
        self.assertEqual(st, 200, body)
        self.assertTrue(body['is_global']); self.assertTrue(body['new_company']); self.assertTrue(body['old_cloud_saved'])
        self.assertNotIn('needs_admin_login', body)
        saved = list(backup_dir.glob('nuvem_*/Auth/auth.db'))
        self.assertTrue(saved, 'the old cloud copy is kept in UStracker_backup_old')
        self.assertTrue((root / 'UserData' / 'State' / 'adm-global.ok').exists())
        g = next(x for x in app.state.auth._sessions.values() if x.kind == 'global')
        names = [r[0] for r in Database(root, 'production', g.db_key).query('SELECT legal_name FROM clients')]
        self.assertNotIn('Cliente Antigo', names)
        self.assertNotEqual(CloudClient(bank['url'], bank['key']).call('ping', {})['head']['id'], old_head, 'cloud restarted')
        # the next computer gets the NEW company and the Global enters directly
        root_b, app_b = self.machine('B')
        st, out = self.activate(app_b)
        self.assertEqual(st, 200, out); self.assertTrue(out['restored']); self.assertTrue(out['is_global'])

    def test_offline_or_missing_company_key_is_a_clear_error(self):
        self.repo.files.pop('company-key.json')
        root, app = self.machine('A')
        st, body = self.activate(app)
        self.assertEqual(st, 200, body); self.assertTrue(body['new_company']); self.assertFalse(body['cloud']['connected'])


    def test_global_login_on_old_data_says_not_prepared(self):
        root, app = self.machine('Old')
        app.state.auth._init_store()
        import ustracker.auth as A
        A.AuthService.bootstrap(app.state.auth, 'Admin', LOCAL)  # old version: local admin, no Adm Global wrap
        st, body = call(app, 'POST', '/api/v1/auth/login', {'name': 'crj', 'password': PIN}, precsrf=True)
        st, body = call(app, 'POST', '/api/v1/auth/login', {'name': 'crj', 'password': PIN, 'answer': PIN}, precsrf=True)
        self.assertEqual(st, 409, body); self.assertEqual(body['error'], 'NOT_PREPARED')


class LegacyBootstrapKey(unittest.TestCase):
    def test_company_key_moves_from_trust_file_into_the_database(self):
        from ustracker.auth import AuthService
        from ustracker.cloud import CloudSync
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); master = new_master()
            boot = root / 'Trust' / 'placa-bootstrap.json'; boot.parent.mkdir(parents=True)
            boot.write_text(json.dumps({'format': 'ustracker-placa-bootstrap/1', 'placa_url': 'http://127.0.0.1:9/placa.json',
                                        'public': master['public'], 'company_key': master['company_key']}))
            auth = AuthService(root); auth.bootstrap('Admin', LOCAL); s = auth.login('Admin', LOCAL)
            sync = CloudSync(root, auth)
            self.assertEqual(sync.company_key(s), master['company_key'])
            sync.keep_company_key(s, master['company_key'])
            from ustracker.placa import strip_company_key
            self.assertTrue(strip_company_key(root))
            self.assertNotIn('company_key', json.loads(boot.read_text()))
            self.assertEqual(sync.company_key(s), master['company_key'])


class GenericErrors(unittest.TestCase):
    def test_unexpected_error_is_json_and_logged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); app = create_app(root)
            app.state.auth.setup_status = lambda: 1 / 0
            out = []

            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}

            async def send(m): out.append(m)
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
                     'path': '/api/v1/auth/setup-status', 'raw_path': b'/api/v1/auth/setup-status', 'query_string': b'',
                     'headers': [(b'host', b'127.0.0.1:5')], 'client': ('127.0.0.1', 1), 'server': ('127.0.0.1', 5), 'root_path': ''}
            try:
                asyncio.run(app(scope, receive, send))
            except ZeroDivisionError:
                pass  # Starlette re-raises after answering
            start = next(m for m in out if m['type'] == 'http.response.start')
            body = json.loads(b''.join(m.get('body', b'') for m in out if m['type'] == 'http.response.body'))
            self.assertEqual(start['status'], 500); self.assertEqual(body['error'], 'INTERNAL')
            self.assertIn('ZeroDivisionError', (root / 'UserData' / 'Logs' / 'erros.log').read_text(encoding='utf-8'))
            app.state.cloud.stop()


if __name__ == '__main__':
    unittest.main()
