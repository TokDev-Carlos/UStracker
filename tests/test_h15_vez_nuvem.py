"""H-15 (2.6) — achados dos testes pesados: "Enviar agora" respeita a vez de gravar; conflito não trava a vez.

1. Com a vez nas mãos de outro computador, enviar à nuvem espera a vez (ou avisa "está salvando agora")
   e nunca sobe por cima — antes subia e deixava o outro computador em CONFLITO.
2. Em conflito, o computador para de enviar sozinho e SOLTA a vez (antes segurava para sempre e
   todos os outros ficavam "está salvando agora").
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.auth import AuthService
from ustracker.cloud import CloudClient, CloudError, CloudSync, apply_pending_restore, restore_from_cloud
from ustracker.db import Database
from ustracker.services import create_client

NODE = shutil.which('node')
PW = 'senha-vez-1234'


@unittest.skipUnless(NODE, 'node not available')
class VezDeGravar(unittest.TestCase):
    def setUp(self):
        self.proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        info = json.loads(self.proc.stdout.readline())
        self.url, self.key = f"http://127.0.0.1:{info['port']}/exec", info['secret']
        self.tmp = tempfile.TemporaryDirectory(); base = Path(self.tmp.name)
        ra = base / 'A'; (ra / 'UserData').mkdir(parents=True)
        auth = AuthService(ra); auth.bootstrap('Admin', PW); s = auth.login('Admin', PW)
        ca = CloudSync(ra, auth, debounce=0); ca.connect(s, self.url, self.key, mode='replace'); ca.release_turn(s)
        self.a = (ra, s, ca)
        rb = base / 'B'; (rb / 'UserData').mkdir(parents=True)
        restore_from_cloud(rb, self.url, self.key)
        ab = AuthService(rb); cb = CloudSync(rb, ab, debounce=0); cb.pending_secret = self.key
        sb = ab.login('Admin', PW)
        apply_pending_restore(rb, Database(rb, 'production', sb.db_key), sb, cb)
        self.b = (rb, sb, cb)

    def tearDown(self):
        self.proc.terminate(); self.proc.wait(5); self.proc.stdout.close(); self.tmp.cleanup()

    def write(self, srv, name):
        r, s, c = srv
        c.acquire_turn(s, wait=1)
        with c.db_gate:
            create_client(Database(r, 'production', s.db_key), 1, {'legal_name': name, 'email': f'{name}@x.test'.replace(' ', ''),
                                                                    'documents': [{'type': 'RG', 'number': 'RG-' + name, 'is_primary': True}]})
        c.mark_dirty()

    def head(self):
        return CloudClient(self.url, self.key).call('ping', {})['head']['generation']

    def test_send_now_respects_the_other_computers_turn(self):
        ra, sa, ca = self.a; rb, sb, cb = self.b
        self.write(self.a, 'cliente A')                      # A tem a vez e uma alteração ainda não enviada
        before = self.head()
        with self.assertRaises(CloudError) as ctx:          # B clica "Enviar agora"
            cb.sync_now(sb, turn_wait=1)
        self.assertEqual(ctx.exception.code, 'BUSY')
        self.assertEqual(self.head(), before, 'B não subiu por cima da vez de A')
        ca.sync_now(sa)                                     # A envia normalmente, sem conflito
        self.assertIsNone(ca.state.get('conflict'))
        self.assertEqual(self.head(), before + 1)

    def test_conflict_stops_auto_send_and_frees_the_turn(self):
        ra, sa, ca = self.a; rb, sb, cb = self.b
        self.write(self.a, 'cliente A')
        ca.state.set(generation=0)                          # simula A atrasado (ex.: ficou sem internet)
        ca.last_turn_use = 0; ca.state.set(last_change=0)
        with self.assertRaises(CloudError):                 # o laço tenta enviar → conflito (o laço registra e segue)
            ca.tick(sa)
        self.assertTrue(ca.state.get('conflict'))
        self.assertEqual(ca.lease_until, 0.0, 'em conflito, A solta a vez')
        ca.tick(sa)                                         # e não volta a pegar a vez sozinho
        self.assertEqual(ca.lease_until, 0.0)
        self.write(self.b, 'cliente B')                     # B consegue gravar e enviar
        cb.sync_now(sb)
        self.assertIsNone(cb.state.get('conflict'))


@unittest.skipUnless(NODE, 'node not available')
class EnviarAgoraSegundoComputador(unittest.TestCase):
    """Antes: no 2º computador "Enviar agora" dava "station is read-only" (regra antiga de estação única)."""
    def setUp(self):
        from ustracker import adm_global as ag
        from ustracker.placa import build_placa, new_master, save_bootstrap
        from ustracker.server import create_app
        from tests.test_h01_activation import PIN, RepoServer, gas
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        os.environ['USTRACKER_BACKUPS'] = str(self.base / 'bk')
        self.repo = RepoServer(); self.pin = PIN
        trust, token, _ = ag.create('crj', PIN, url=self.repo.base + '/token-mestre.json', read_token=self.repo.read_token)
        self.repo.files['token-mestre.json'] = token
        master = new_master(); self.repo.files['company-key.json'] = ag.wrap_company_key(master['company_key'], trust)
        self.proc, url, secret = gas(); self.repo.files['placa.json'] = build_placa([{'url': url, 'key': secret}], master, 1)
        self.apps = []
        for name in ('A', 'B'):
            root = self.base / name
            ag.save_trust(root, trust); save_bootstrap(root, url=self.repo.base + '/placa.json', master=master)
            self.apps.append(create_app(root))

    def tearDown(self):
        for app in self.apps:
            app.state.cloud.stop(); app.state.updates.stop()
        self.proc.terminate(); self.proc.wait(5); self.proc.stdout.close(); self.repo.stop(); self.tmp.cleanup()
        os.environ.pop('USTRACKER_BACKUPS', None)

    def test_second_computer_writes_and_sends_now(self):
        from tests.test_g04_adm_global import call
        sessions = []
        for app in self.apps:
            call(app, 'POST', '/api/v1/auth/activate', {'name': 'crj', 'password': self.pin}, precsrf=True)
            st, body = call(app, 'POST', '/api/v1/auth/activate', {'name': 'crj', 'password': self.pin, 'answer': self.pin}, precsrf=True)
            self.assertEqual(st, 200, body)
            s = next(x for x in app.state.auth._sessions.values() if x.environment == 'production')
            sessions.append(s)
            app.state.cloud.release_turn(s)
        app_a, s_a = self.apps[0], sessions[0]
        app_b, s_b = self.apps[1], sessions[1]
        st, out = call(app_a, 'POST', '/api/v1/clients', {'legal_name': 'Cliente do A', 'email': 'a@x.test', 'documents': [{'type': 'CPF', 'number': '11144477735', 'is_primary': True}]},
                       token=s_a.token, csrf=s_a.csrf)
        self.assertEqual(st, 201, out)
        app_a.state.cloud.sync_now(s_a); app_a.state.cloud.release_turn(s_a)
        self.assertTrue(app_b.state.cloud.pull(s_b), 'B recebe o banco que A enviou')
        st, out = call(app_b, 'POST', '/api/v1/clients', {'legal_name': 'Cliente do B', 'email': 'b@x.test', 'documents': [{'type': 'CPF', 'number': '52998224725', 'is_primary': True}],
                                                         'phone': '11900000000'}, token=s_b.token, csrf=s_b.csrf)
        self.assertEqual(st, 201, out)
        st, out = call(app_b, 'POST', '/api/v1/cloud/sync', {}, token=s_b.token, csrf=s_b.csrf)
        self.assertEqual(st, 200, out)


if __name__ == '__main__':
    unittest.main()
