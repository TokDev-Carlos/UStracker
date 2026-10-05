"""G-03 — banco de Teste só do Administrador: entra pelo Sistema, nunca vai para a nuvem, nunca aparece no Real."""
import asyncio, io, json, os, sys, tempfile, unittest, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from PIL import Image
from ustracker import media
from ustracker.cloud import blob_files
from ustracker.db import Database
from ustracker.server import create_app
from ustracker.services import create_client

PW = 'senha-admin-1234'


def call(app, method, path, payload=None, token=None, csrf=None):
    body = json.dumps(payload or {}).encode()
    headers = [(b'host', b'127.0.0.1:50000'), (b'content-type', b'application/json'), (b'x-operation-id', str(uuid.uuid4()).encode())]
    if token:
        headers += [(b'cookie', ('us_session=' + token).encode()), (b'x-csrf-token', csrf.encode())]
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
    cookies = [v.decode() for k, v in start['headers'] if k == b'set-cookie']
    return start['status'], (json.loads(data) if data else {}), cookies


def doc(n):
    return {'legal_name': f'Cliente {n}', 'email': f'c{n}@x.test', 'documents': [{'type': 'RG', 'number': f'RG-G03-{n}', 'is_primary': True}]}


class TestEnvironmentAdminOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.app = create_app(self.root); self.auth = self.app.state.auth
        self.auth.bootstrap('Admin', PW)
        self.admin = self.auth.login('Admin', PW, 'production')
        self.auth.create_user(self.admin, {'name': 'gil', 'password': '1234', 'package_id': 'GERENTE'})

    def tearDown(self):
        self.app.state.cloud.stop(); self.tmp.cleanup()

    def test_users_never_enter_test(self):
        with self.assertRaises(ValueError):
            self.auth.login('gil', '1234', 'test')
        gil = self.auth.login('gil', '1234', 'production')
        status, _, _ = call(self.app, 'POST', '/api/v1/session/environment', {'environment': 'test'}, gil.token, gil.csrf)
        self.assertEqual(status, 403)

    def test_admin_switches_without_password_and_data_stays_apart(self):
        status, body, cookies = call(self.app, 'POST', '/api/v1/session/environment', {'environment': 'test'}, self.admin.token, self.admin.csrf)
        self.assertEqual((status, body['environment']), (200, 'test'), body)
        self.assertTrue(any(c.startswith('us_session=') for c in cookies), 'nova sessão no cookie')
        test = self.auth.get_session(next(c for c in cookies if c.startswith('us_session=')).split(';')[0].split('=', 1)[1])
        self.assertEqual(test.environment, 'test'); self.assertEqual(test.csrf, body['csrf'])
        self.assertNotEqual(self.app.state.cloud.token, test.token, 'Teste nunca liga a nuvem')
        tdb = Database(self.root, 'test', test.db_key)
        c = create_client(tdb, 1, doc(1))
        buf = io.BytesIO(); Image.new('RGB', (16, 16)).save(buf, 'PNG')
        media.store(self.root, tdb, 1, test.media_key, 'client', c['id'], buf.getvalue())
        self.assertEqual(blob_files(self.root), {}, 'fotos do Teste fora da nuvem')
        pdb = Database(self.root, 'production', self.admin.db_key)
        self.assertEqual(pdb.one('SELECT COUNT(*) FROM clients')[0], 0, 'Teste não aparece no Real')
        status, body, cookies = call(self.app, 'POST', '/api/v1/session/environment', {'environment': 'production'}, test.token, test.csrf)
        self.assertEqual((status, body['environment']), (200, 'production'))
        self.assertIsNone(self.auth.get_session(test.token), 'sessão de Teste encerrada ao voltar')
        back = next(c for c in cookies if c.startswith('us_session=')).split(';')[0].split('=', 1)[1]
        self.assertEqual(self.app.state.cloud.token, back, 'nuvem volta a usar a sessão do Real')


if __name__ == '__main__':
    unittest.main()
