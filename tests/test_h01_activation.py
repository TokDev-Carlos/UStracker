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
        self.assertEqual(st, 200, body); self.assertTrue(body['create_admin']); self.assertTrue(body['cloud'])
        st, out = call(app_a, 'POST', '/api/v1/auth/activate/admin', {'ticket': 'falso', 'name': 'Admin', 'password': LOCAL}, precsrf=True)
        self.assertEqual(st, 422, out)
        st, out = call(app_a, 'POST', '/api/v1/auth/activate/admin', {'ticket': body['ticket'], 'name': 'Admin', 'password': LOCAL}, precsrf=True)
        self.assertEqual(st, 200, out)
        self.assertTrue(out['recovery_key']); self.assertTrue(out['cloud']['connected']); self.assertNotIn('error', out['cloud'])
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

    def test_offline_or_missing_company_key_is_a_clear_error(self):
        self.repo.files.pop('company-key.json')
        root, app = self.machine('A')
        st, body = self.activate(app)
        self.assertEqual(st, 200, body); self.assertTrue(body['create_admin']); self.assertFalse(body['cloud'])


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
