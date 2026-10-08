"""H-14 (2.5.0) — usuários globais: login único na nuvem (HMAC), senha hash+cripto (nuvem e cópia local),
alterações só online, login offline até 1 dia, senha trocada em outra máquina vale ao reconectar."""
import json, os, shutil, sys, tempfile, threading, unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.auth import AuthService
from ustracker.cloud import CloudClient
from ustracker.users_global import normalize_login
from tests.test_h01_activation import NODE, gas

COMPANY_KEY = 'k' * 43 + '='
PW = 'senha-1234'


@unittest.skipUnless(NODE, 'node not available')
class UsuariosGlobais(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.proc, self.url, self.secret = gas()
        CloudClient(self.url, self.secret).call('reset_company', {'epoch': 25}, check_epoch=False)
        self.a = AuthService(self.base / 'A')
        self.a.bootstrap('Admin', PW)
        self.adm = self.a.login('Admin', PW)
        self.a.set_directory(self.url, self.secret, COMPANY_KEY)
        b = self.base / 'B' / 'UserData' / 'Auth'; b.mkdir(parents=True)
        for n in ('auth.db', 'vault.json'):  # B ativado: acessos e cofre vieram da nuvem
            shutil.copy2(self.base / 'A' / 'UserData' / 'Auth' / n, b / n)
        self.b = AuthService(self.base / 'B')
        self.b.set_directory(self.url, self.secret, COMPANY_KEY)

    def tearDown(self):
        self.proc.terminate(); self.proc.wait(5); self.tmp.cleanup()

    def test_normalize_login(self):
        self.assertEqual(normalize_login('  Cárlos.Jr '), 'carlos.jr')
        for bad in ('ab', 'com espaço', 'x' * 33, 'nome!'):
            with self.assertRaises(ValueError):
                normalize_login(bad)

    def test_unique_login_across_machines_and_atomic(self):
        self.a.create_user(self.adm, {'name': 'Carlos', 'password': PW, 'package_id': 'OPERADOR'})
        adm_b = self.b.login('Admin', PW)
        with self.assertRaises(ValueError) as ctx:
            self.b.create_user(adm_b, {'name': 'cárlos', 'password': PW})
        self.assertIn('login already exists', str(ctx.exception))
        results = []
        def make(svc, sess):
            try:
                svc.create_user(sess, {'name': 'maria', 'password': PW}); results.append('ok')
            except ValueError as exc:
                results.append(str(exc))
        threads = [threading.Thread(target=make, args=(self.a, self.adm)), threading.Thread(target=make, args=(self.b, adm_b))]
        [t.start() for t in threads]; [t.join() for t in threads]
        self.assertEqual(sorted(results), ['login already exists', 'ok'])

    def test_cloud_holds_only_ciphertext(self):
        self.a.create_user(self.adm, {'name': 'joana', 'password': PW, 'full_name': 'Joana Silva'})
        raw = json.dumps(CloudClient(self.url, self.secret).call('users_get', {'since': 0}))
        for clear in ('joana', 'Joana Silva', PW, 'OPERADOR'):
            self.assertNotIn(clear, raw)

    def test_other_machine_logs_in_and_password_change_wins_after_reconnect(self):
        self.a.create_user(self.adm, {'name': 'pedro', 'password': PW})
        s_b = self.b.login('pedro', PW)                      # B nunca viu o pedro: veio da nuvem
        uid = next(u['id'] for u in self.a.list_users() if u['name'] == 'pedro')
        self.a.update_user(self.adm, uid, {'password': 'nova-5678'})
        self.b.set_directory('http://127.0.0.1:9/exec', self.secret, COMPANY_KEY)   # B sem internet
        self.assertTrue(self.b.login('pedro', PW), 'offline: entra com a cópia local (menos de 1 dia)')
        with self.assertRaises(ValueError) as ctx:
            self.b.create_user(self.b.login('Admin', PW), {'name': 'novo', 'password': PW})
        self.assertIn('internet required', str(ctx.exception))
        self.b.set_directory(self.url, self.secret, COMPANY_KEY)                   # internet voltou
        self.b.refresh_users()
        self.assertIsNone(self.b.get_session(s_b.token), 'sessão aberta com a senha antiga caiu')
        with self.assertRaises(ValueError):
            self.b.login('pedro', PW)
        self.assertTrue(self.b.login('pedro', 'nova-5678'))

    def test_offline_more_than_one_day_is_refused(self):
        self.a.create_user(self.adm, {'name': 'lia', 'password': PW})
        self.b.login('lia', PW)
        self.b.set_directory('http://127.0.0.1:9/exec', self.secret, COMPANY_KEY)
        self.b._set_meta('last_cloud_ok', (self.b._now() - timedelta(days=1, minutes=5)).isoformat())
        with self.assertRaises(ValueError) as ctx:
            self.b.login('lia', PW)
        self.assertIn('offline too long', str(ctx.exception))

    def test_deleted_login_is_gone_everywhere_and_reserved(self):
        self.a.create_user(self.adm, {'name': 'rui', 'password': PW})
        self.b.login('rui', PW)
        uid = next(u['id'] for u in self.a.list_users() if u['name'] == 'rui')
        self.a.update_user(self.adm, uid, {'deleted': True})
        with self.assertRaises(ValueError):
            self.b.login('rui', PW)
        with self.assertRaises(ValueError) as ctx:
            self.a.create_user(self.adm, {'name': 'rui', 'password': PW})
        self.assertIn('login already exists', str(ctx.exception))

    def test_gerente_manages_users_but_not_admin_powers(self):
        self.a.create_user(self.adm, {'name': 'gerente1', 'password': PW, 'package_id': 'GERENTE'})
        ger = self.a.login('gerente1', PW)
        self.assertTrue(ger.can('users.manage'))
        self.a.create_user(ger, {'name': 'operador1', 'password': PW, 'package_id': 'OPERADOR'})
        pkg = self.a.save_package(self.adm, {'title': 'Sistema total', 'permissions': ['system', 'clients.view']})
        with self.assertRaises(PermissionError):
            self.a.create_user(ger, {'name': 'poderoso', 'password': PW, 'package_id': pkg['id']})
        op = self.a.login('operador1', PW)
        with self.assertRaises(PermissionError):
            self.a.create_user(op, {'name': 'x1x', 'password': PW})

    def test_password_set_by_someone_else_is_provisional_everywhere(self):
        self.a.create_user(self.adm, {'name': 'nina', 'password': PW})
        self.assertTrue(self.b.login('nina', PW).must_change, 'senha criada pelo administrador: troca no 1º acesso, em qualquer computador')
        s = self.a.login('nina', PW)
        self.a.change_password(s, PW, 'minha-9876')
        self.assertFalse(self.b.login('nina', 'minha-9876').must_change)

    def test_package_created_on_a_reaches_b(self):
        pkg = self.a.save_package(self.adm, {'title': 'Vendas', 'permissions': ['clients.view']})
        self.a.create_user(self.adm, {'name': 'vend', 'password': PW, 'package_id': pkg['id']})
        s = self.b.login('vend', PW)
        self.assertEqual(s.package_title, 'Vendas')


if __name__ == '__main__':
    unittest.main()
