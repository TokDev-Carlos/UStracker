"""G-01..G-03 — Release 2: restaurar da nuvem é só do Administrador; instalador único com a placa embutida."""
import asyncio, json, os, re, sys, tempfile, unittest, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'installer' if (ROOT / 'installer').exists() else ROOT / 'release' / 'installer'
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.placa import new_master, save_bootstrap
from ustracker.server import create_app


def call(app, method, path, payload=None, session=None, precsrf=False):
    body = json.dumps(payload or {}).encode()
    headers = [(b'host', b'127.0.0.1:50000'), (b'content-type', b'application/json'), (b'x-operation-id', str(uuid.uuid4()).encode())]
    if session:
        headers += [(b'cookie', ('us_session=' + session.token).encode()), (b'x-csrf-token', session.csrf.encode())]
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
    return next(m['status'] for m in out if m['type'] == 'http.response.start')


class CloudRestoreIsGlobalOnly(unittest.TestCase):
    def test_restore_needs_admin_session(self):
        with tempfile.TemporaryDirectory() as d:
            app = create_app(Path(d))
            payload = {'url': 'http://127.0.0.1:9/exec', 'secret': 'x' * 32, 'confirm': 'RESTAURAR DA NUVEM'}
            self.assertEqual(call(app, 'POST', '/api/v1/cloud/restore', payload, precsrf=True), 401, 'antes do login: recusado')
            app.state.auth.bootstrap('Admin', 'senha-1234')
            admin = app.state.auth.login('Admin', 'senha-1234', 'production')
            self.assertEqual(call(app, 'POST', '/api/v1/cloud/restore', payload, session=admin), 403, 'G-04: só o Adm Global')
            app.state.auth.create_user(admin, {'name': 'gil', 'password': '1234', 'package_id': 'GERENTE'})
            gil = app.state.auth.login('gil', '1234', 'production')
            self.assertEqual(call(app, 'POST', '/api/v1/cloud/restore', payload, session=gil), 403, 'gerente não pode')


class SingleInstaller(unittest.TestCase):
    nsi = (INSTALLER / 'UStracker.nsi').read_text(encoding='utf-8')

    def test_single_file_with_placa_inside(self):
        self.assertIn('UStracker_install_x64.exe', self.nsi)
        self.assertNotIn('$EXEDIR', self.nsi, 'nada ao lado do instalador')
        self.assertRegex(self.nsi, r'!error[^\n]*PLACA', 'compilar sem a placa é erro')
        self.assertRegex(self.nsi, r'!error[^\n]*WV2', 'compilar sem o WebView2 é erro')
        self.assertRegex(self.nsi, r'File /oname=placa-bootstrap\.json "\$\{PLACA\}"')
        self.assertNotRegex(self.nsi.lower(), r'restaurar da nuvem')

    def test_bootstrap_no_longer_written_to_kit_folder(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'Instalador').mkdir()
            save_bootstrap(d, url='https://raw.githubusercontent.com/x/y/main/docs/placa.json', master=new_master())
            self.assertTrue((Path(d) / 'Trust' / 'placa-bootstrap.json').exists())
            self.assertFalse((Path(d) / 'Instalador' / 'placa-bootstrap.json').exists())


class VersionTwo(unittest.TestCase):
    def test_version_is_2_4_0(self):
        for name in ('VERSION.json', 'current.json'):
            self.assertEqual(json.loads((ROOT / name).read_text(encoding='utf-8'))['version'], '2.4.0', name)


if __name__ == '__main__':
    unittest.main()
