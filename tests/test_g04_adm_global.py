"""G-04 — Adm Global (Token Mestre no Git + pergunta falsa com pistas), Adm Local único e Chave de Recuperação."""
import asyncio, json, os, sqlite3, sys, tempfile, threading, unittest, uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import adm_global as ag
from ustracker.auth import AuthService
from ustracker.server import create_app

PIN = '482913'
LOCAL = 'senha-local-1234'


def call(app, method, path, payload=None, token=None, csrf=None, precsrf=False):
    body = json.dumps(payload or {}).encode()
    headers = [(b'host', b'127.0.0.1:50000'), (b'content-type', b'application/json'), (b'x-operation-id', str(uuid.uuid4()).encode())]
    if token:
        headers += [(b'cookie', ('us_session=' + token).encode()), (b'x-csrf-token', csrf.encode())]
    elif precsrf:
        headers += [(b'cookie', b'us_csrf=abc123abc123'), (b'x-csrf-token', b'abc123abc123')]
    out, sent = [], False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await asyncio.sleep(3600)

    async def send(m): out.append(m)
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method, 'scheme': 'http', 'path': path,
             'raw_path': path.encode(), 'query_string': b'', 'headers': headers, 'client': ('127.0.0.1', 1), 'server': ('127.0.0.1', 50000), 'root_path': ''}
    asyncio.run(app(scope, receive, send))
    start = next(m for m in out if m['type'] == 'http.response.start')
    data = b''.join(m.get('body', b'') for m in out if m['type'] == 'http.response.body')
    return start['status'], (json.loads(data) if data else {})


class TokenServer:
    """Plays the private acesso-UStracker repo (requires the read token)."""
    def __init__(self):
        self.body = b'{}'; self.read_token = 'leitura-123'; owner = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get('Authorization') != f'Bearer {owner.read_token}':
                    self.send_response(404); self.end_headers(); return
                self.send_response(200); self.end_headers(); self.wfile.write(owner.body)
            def log_message(self, *a): pass
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}/token-mestre.json'

    def publish(self, token): self.body = json.dumps(token).encode()
    def stop(self): self.httpd.shutdown()


class Crypto(unittest.TestCase):
    def test_token_pin_signature_pass_and_wrap(self):
        trust, token, keys = ag.create('crj', PIN, url='https://x/token-mestre.json', read_token='t')
        self.assertNotIn(PIN, json.dumps(token)); self.assertNotIn(PIN, json.dumps(trust))
        ag.verify(token, trust)
        opened = ag.open_keys(token, PIN, trust)
        with self.assertRaises(ag.AccessDenied):
            ag.open_keys(token, '000000', trust)
        bad = dict(token, status='active', login='outro')
        with self.assertRaises(ag.AccessDenied):
            ag.verify(bad, trust)
        p = ag.make_pass(token, opened, hours=24)
        ag.verify(p, trust, offline=True)
        with self.assertRaises(ag.AccessDenied):
            ag.verify(ag.make_pass(token, opened, hours=-1), trust, offline=True)
        with self.assertRaises(ag.AccessDenied):
            ag.verify(token, trust, offline=True)  # online token is not a pass
        vrk = os.urandom(32)
        self.assertEqual(ag.unwrap(ag.wrap(vrk, trust), opened), vrk)
        token2 = ag.change_pin(token, opened, '7777', status='active')
        self.assertEqual(ag.open_keys(token2, '7777', trust)['x_pub'], opened['x_pub'], 'troca de PIN mantém as chaves')
        q = ag.question(); self.assertEqual(len(ag.hints(q['id'])), 3)


class LocalAdmin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_admin_and_recovery_key(self):
        auth = AuthService(self.root)
        out = auth.bootstrap('Admin', LOCAL)
        self.assertNotIn('tickets', out); self.assertRegex(out['recovery_key'], r'^[A-Z2-9]{4}(-[A-Z2-9]{4}){5}$')
        self.assertEqual([a['slot'] for a in auth.setup_status()['admins']], [1])
        self.assertTrue(auth.setup_status()['complete'])
        with self.assertRaises(ValueError):
            auth.recover('AAAA-AAAA-AAAA-AAAA-AAAA-AAAA', 'nova-123')
        auth.recover(out['recovery_key'].lower().replace('-', ' '), 'nova-senha-9')
        self.assertEqual(auth.login('Admin', 'nova-senha-9').slot, 1)
        with self.assertRaises(ValueError):
            auth.login('Admin', LOCAL)

    def test_old_install_drops_pending_slots_and_gets_recovery_on_login(self):
        auth = AuthService(self.root); auth.bootstrap('Admin', LOCAL)
        con = sqlite3.connect(self.root / 'UserData' / 'Auth' / 'auth.db')
        con.execute("INSERT INTO admins(slot,status,updated_at) VALUES(2,'PENDING_ENROLLMENT','x'),(3,'PENDING_ENROLLMENT','x')")
        con.execute('DELETE FROM recovery'); con.commit(); con.close()
        auth = AuthService(self.root)
        self.assertEqual([a['slot'] for a in auth.setup_status()['admins']], [1])
        s = auth.login('Admin', LOCAL)
        code = auth.ensure_recovery(s)
        self.assertTrue(code); self.assertIsNone(auth.ensure_recovery(s), 'mostrada uma vez só')


class GlobalLogin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.srv = TokenServer()
        trust, self.token, self.keys = ag.create('crj', PIN, url=self.srv.url, read_token=self.srv.read_token)
        ag.save_trust(self.root, trust); self.trust = trust
        self.srv.publish(self.token)
        self.app = create_app(self.root); self.auth = self.app.state.auth
        self.auth.bootstrap('Admin', LOCAL)

    def tearDown(self):
        self.app.state.cloud.stop(); self.srv.stop(); self.tmp.cleanup()

    def login(self, payload):
        return call(self.app, 'POST', '/api/v1/auth/login', payload, precsrf=True)

    def global_login(self, pin=PIN, answer=None):
        status, body = self.login({'name': 'crj', 'password': pin})
        self.assertEqual(status, 200, body); self.assertIn('question', body['challenge'])
        return self.login({'name': 'crj', 'password': pin, 'answer': pin if answer is None else answer, 'question_id': body['challenge']['id']})

    def test_needs_local_login_first_then_global_works(self):
        status, body = self.global_login()
        self.assertNotEqual(status, 200, 'instalação ainda sem acesso preparado')
        self.assertEqual(self.login({'name': 'Admin', 'password': LOCAL})[0], 200)  # prepara o acesso do Adm Global
        status, body = self.global_login()
        self.assertEqual(status, 200, body); self.assertTrue(body['is_global'])
        g = self.auth.get_session(next(t for t, s in self.auth._sessions.items() if s.kind == 'global'))
        self.assertEqual(call(self.app, 'GET', '/api/v1/cloud/placa', token=g.token, csrf=g.csrf)[0], 200)
        local = self.auth.login('Admin', LOCAL)
        self.assertEqual(call(self.app, 'GET', '/api/v1/cloud/placa', token=local.token, csrf=local.csrf)[0], 403)
        self.assertEqual(call(self.app, 'POST', '/api/v1/backups/restore', token=local.token, csrf=local.csrf)[0], 403)
        self.assertEqual(call(self.app, 'POST', '/api/v1/stations/claim', {'confirm': 'ASSUMIR ESCRITA'}, local.token, local.csrf)[0], 403)
        # Adm Global redefine o Adm Local e gera nova chave de recuperação
        st, out = call(self.app, 'POST', '/api/v1/admin-local/password', {'new_password': 'redefinida-1'}, g.token, g.csrf)
        self.assertEqual(st, 200, out); self.assertEqual(self.auth.login('Admin', 'redefinida-1').slot, 1)
        st, out = call(self.app, 'POST', '/api/v1/admin-local/recovery-key', {}, g.token, g.csrf)
        self.assertEqual(st, 200); self.assertTrue(out['recovery_key'])
        # passe de 1 dia
        st, out = call(self.app, 'POST', '/api/v1/global/pass', {}, g.token, g.csrf)
        self.assertEqual(st, 200); ag.verify(out['pass'], self.trust, offline=True)

    def test_wrong_answers_show_hints_and_lock_30_minutes(self):
        self.login({'name': 'Admin', 'password': LOCAL})
        hints = []
        for _ in range(5):
            status, body = self.global_login(answer='flamengo')
            self.assertEqual(status, 422); hints.append(body.get('hint'))
            self.assertNotIn(PIN, json.dumps(body))
        self.assertTrue(all(hints)); self.assertEqual(len(set(hints)), 3, 'pistas avançam e se repetem')
        status, body = self.login({'name': 'crj', 'password': PIN, 'answer': PIN, 'question_id': 1})
        self.assertEqual(status, 429, 'bloqueado mesmo com o PIN certo')
        self.assertEqual(self.login({'name': 'crj', 'password': PIN})[0], 429, 'nem mostra a pergunta durante o bloqueio')
        self.assertGreaterEqual(body.get('retry_minutes', 0), 29)
        audit = [r[0] for r in sqlite3.connect(self.root / 'UserData' / 'Auth' / 'auth.db').execute('SELECT action FROM auth_audit')]
        self.assertIn('GLOBAL_DECOY', audit)
        # bloqueio sobrevive a reinício
        app2 = create_app(self.root)
        status, _ = call(app2, 'POST', '/api/v1/auth/login', {'name': 'crj', 'password': PIN, 'answer': PIN, 'question_id': 1}, precsrf=True)
        self.assertEqual(status, 429); app2.state.cloud.stop()

    def test_revoked_and_offline_pass(self):
        self.login({'name': 'Admin', 'password': LOCAL})
        self.srv.publish(ag.change_pin(self.token, self.keys, PIN, status='revoked'))
        self.assertEqual(self.global_login()[0], 422, 'revogado no Git')
        self.srv.stop()  # sem internet
        self.assertEqual(self.global_login()[0], 422, 'sem internet e sem passe')
        ag.save_pass(self.root, ag.make_pass(self.token, self.keys, hours=24))
        self.assertEqual(self.global_login()[0], 200, 'passe de pendrive válido')
        ag.save_pass(self.root, ag.make_pass(self.token, self.keys, hours=-1))
        self.assertEqual(self.global_login()[0], 422, 'passe vencido')
        self.srv = TokenServer()  # keep tearDown happy



class FirstSetup(unittest.TestCase):
    def test_owner_configures_once_on_his_machine(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); app = create_app(root); auth = app.state.auth
            auth.bootstrap('Admin', LOCAL); local = auth.login('Admin', LOCAL)
            st, out = call(app, 'POST', '/api/v1/global/setup', {'login': 'Admin', 'pin': PIN, 'pin_confirm': PIN}, local.token, local.csrf)
            self.assertEqual(st, 422, 'nome já usado')
            st, out = call(app, 'POST', '/api/v1/global/setup', {'login': 'crj', 'pin': PIN, 'pin_confirm': PIN}, local.token, local.csrf)
            self.assertEqual(st, 200, out)
            trust = ag.load_trust(root)
            self.assertTrue(trust and out['token'])
            self.assertFalse((root / 'UserData' / 'State' / 'token-mestre-novo.json').exists(), 'Token Mestre não fica no disco')
            self.assertNotIn(PIN, json.dumps(out['token']) + json.dumps(trust))
            ag.open_keys(out['token'], PIN, trust)
            st, _ = call(app, 'POST', '/api/v1/global/setup', {'login': 'x', 'pin': PIN, 'pin_confirm': PIN}, local.token, local.csrf)
            self.assertEqual(st, 403, 'só uma vez')
            st, body = call(app, 'GET', '/api/v1/auth/setup-status')
            self.assertTrue(body['global_configured'])
            app.state.cloud.stop()


if __name__ == '__main__':
    unittest.main()
