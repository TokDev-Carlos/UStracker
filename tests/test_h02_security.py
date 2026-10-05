"""H-02 (2.2.0) — correções da revisão de segurança (host/origem, custos, cancelamentos, ajustes, Token Mestre)."""
import asyncio, json, os, sys, tempfile, unittest, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.server import create_app
from ustracker.services import create_catalog

LOCAL = 'senha-local-1234'


def call(app, method, path, payload=None, session=None, host=b'127.0.0.1:5', origin=None):
    body = json.dumps(payload or {}).encode()
    headers = [(b'host', host), (b'content-type', b'application/json'), (b'x-operation-id', str(uuid.uuid4()).encode())]
    if session:
        headers += [(b'cookie', ('us_session=' + session.token).encode()), (b'x-csrf-token', session.csrf.encode())]
    if origin:
        headers.append((b'origin', origin))
    out, sent = [], False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await asyncio.sleep(3600)

    async def send(m): out.append(m)
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method, 'scheme': 'http', 'path': path,
             'raw_path': path.encode(), 'query_string': b'', 'headers': headers, 'client': ('127.0.0.1', 1), 'server': ('127.0.0.1', 5), 'root_path': ''}
    asyncio.run(app(scope, receive, send))
    start = next(m for m in out if m['type'] == 'http.response.start')
    data = b''.join(m.get('body', b'') for m in out if m['type'] == 'http.response.body')
    return start['status'], (json.loads(data) if data else {})


class Security(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.app = create_app(self.root); self.auth = self.app.state.auth
        self.auth.bootstrap('Admin', LOCAL)
        self.admin = self.auth.login('Admin', LOCAL)
        self.auth.create_user(self.admin, {'name': 'ana', 'password': '1234', 'package_id': 'OPERADOR'})
        self.op = self.auth.login('ana', '1234')
        self.item = create_catalog(Database(self.root, 'production', self.admin.db_key), 1,
                                   {'description': 'Plano', 'category': 'Mensal', 'price': '100,00', 'cost': '10,00'})

    def tearDown(self):
        self.app.state.cloud.stop(); self.tmp.cleanup()

    def test_only_local_host_and_exact_local_origin(self):
        self.assertEqual(call(self.app, 'GET', '/api/v1/health', host=b'testserver')[0], 400)
        self.assertEqual(call(self.app, 'GET', '/api/v1/health', host=b'evil.test')[0], 400)
        for bad in (b'http://testserver', b'http://127.0.0.1:80.evil.test', b'http://localhost.evil.test', b'null'):
            self.assertEqual(call(self.app, 'POST', '/api/v1/auth/csrf', origin=bad)[0], 403, bad)
        self.assertNotEqual(call(self.app, 'POST', '/api/v1/auth/logout', session=self.admin, origin=b'http://127.0.0.1:51234')[0], 403)

    def test_costs_never_reach_a_package_without_cost_permission(self):
        st, out = call(self.app, 'GET', f"/api/v1/catalog/{self.item['id']}/prices", session=self.op)
        self.assertEqual(st, 200); self.assertTrue(out['items'])
        self.assertNotIn('cost', json.dumps(out))
        st, out = call(self.app, 'GET', f"/api/v1/catalog/{self.item['id']}/prices", session=self.admin)
        self.assertIn('cost_cents', json.dumps(out))

    def test_cancellations_and_adjustments_need_their_permissions(self):
        st, _ = call(self.app, 'PATCH', '/api/v1/subscriptions/x/status', {'lifecycle_status': 'ENDED'}, self.op)
        self.assertEqual(st, 403)
        st, _ = call(self.app, 'PATCH', '/api/v1/clients/x', {'status': 'CANCELLED'}, self.op)
        self.assertEqual(st, 403)
        st, _ = call(self.app, 'POST', '/api/v1/charges/x/adjustments', {'amount': '-5,00'}, self.op)
        self.assertEqual(st, 403)

    def test_new_pin_token_is_downloaded_not_left_on_disk(self):
        self.assertFalse(list((self.root / 'UserData' / 'State').glob('token-mestre*')))


if __name__ == '__main__':
    unittest.main()


class WindowsLayout(unittest.TestCase):
    """2.2.0 — programa em Program Files (protegido), dados em ProgramData, migração sem apagar nada."""
    nsi = (ROOT / 'release' / 'installer' / 'UStracker.nsi').read_text(encoding='utf-8')
    ps = (ROOT / 'release' / 'installer' / 'setup-data.ps1').read_text(encoding='utf-8')
    rm = (ROOT / 'release' / 'installer' / 'remove-data.ps1').read_text(encoding='utf-8')

    def test_program_files_and_programdata(self):
        self.assertIn('InstallDir "$PROGRAMFILES64\\${APP}"', self.nsi)
        self.assertNotIn('icacls "$INSTDIR"', self.nsi, 'a pasta do programa não fica gravável por usuários')
        self.assertIn("/grant '*S-1-5-32-545:(OI)(CI)M'", self.ps)
        self.assertIn('-ItemType Junction', self.ps)
        self.assertNotRegex(self.ps, r'Remove-Item|rmdir|del ', 'a instalação nunca apaga dados')

    def test_app_opens_as_user_and_closes_running_copy(self):
        self.assertIn('explorer.exe" "$INSTDIR\\UStracker.exe"', self.nsi)
        self.assertNotIn('MUI_FINISHPAGE_RUN "$INSTDIR', self.nsi)
        self.assertIn('Stop-Process -Force', self.nsi)
        self.assertNotIn('WaitAppClosed', self.nsi)

    def test_uninstall_keep_or_remove_with_backup(self):
        self.assertIn('"REMOVER"', self.nsi)
        self.assertIn("rmdir \"$INSTDIR\\UserData\"", self.nsi, 'a junção sai sem seguir para os dados')
        self.assertLess(self.rm.index('robocopy'), self.rm.index('Remove-Item'), 'cópia antes de apagar')
        self.assertIn('if ($code -ge 8) { exit 10 }', self.rm)

    def test_trust_always_from_this_version_and_no_company_key(self):
        self.assertIn('File "${SRC}/Trust/adm-global.json"', self.nsi)
        self.assertNotIn('SetOverwrite off', self.nsi)
