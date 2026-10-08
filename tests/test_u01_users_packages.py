"""U-01..U-05 — usuários com pacotes (Operador, Gerente, personalizado) e regras de rota."""
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.access import ALL, GERENTE, OPERADOR, required_permission, restrict_dashboard, strip_costs
from ustracker.auth import AuthService


class Users(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.auth = AuthService(Path(self.tmp.name))
        self.auth.bootstrap('Admin', 'senha-admin-123')
        self.admin = self.auth.login('Admin', 'senha-admin-123', 'production')

    def tearDown(self):
        self.tmp.cleanup()

    def test_operator_login_gets_package_and_same_data_keys(self):
        self.auth.create_user(self.admin, {'name': 'ana', 'password': '1234', 'package_id': 'OPERADOR'})
        s = self.auth.login('ANA', '1234', 'production')
        self.assertEqual(s.kind, 'user'); self.assertEqual(s.package_title, 'Operador')
        self.assertEqual(s.db_key, self.admin.db_key, 'mesmo banco da empresa')
        self.assertTrue(s.can('clients.edit')); self.assertFalse(s.can('clients.delete')); self.assertFalse(s.can('system'))
        self.assertGreaterEqual(s.slot, 1000)

    def test_name_unique_and_deactivate_and_password_reset(self):
        u = self.auth.create_user(self.admin, {'name': 'bia', 'password': 'abcd', 'package_id': 'GERENTE'})
        with self.assertRaises(ValueError):
            self.auth.create_user(self.admin, {'name': 'Admin', 'password': 'abcd'})
        s = self.auth.login('bia', 'abcd')
        self.auth.update_user(self.admin, u['id'], {'active': False})
        self.assertIsNone(self.auth.get_session(s.token), 'desativar derruba a sessão')
        with self.assertRaises(ValueError):
            self.auth.login('bia', 'abcd')
        self.auth.update_user(self.admin, u['id'], {'active': True, 'password': 'nova1'})
        self.assertEqual(self.auth.login('bia', 'nova1').package_title, 'Gerente')
        self.auth.create_user(self.auth.login('bia', 'nova1'), {'name': 'op1', 'password': '1234'})  # 2.5: Gerente cria usuários
        with self.assertRaises(PermissionError):
            self.auth.create_user(self.auth.login('op1', '1234'), {'name': 'x', 'password': '1234'})

    def test_custom_package_applies_to_open_sessions(self):
        pkg = self.auth.save_package(self.admin, {'title': 'Financeiro sem Despesas', 'permissions': ['finance.view', 'finance.pay', 'nope']})
        self.assertEqual(pkg['permissions'], ['finance.pay', 'finance.view'])
        self.auth.create_user(self.admin, {'name': 'caio', 'password': '1234', 'package_id': pkg['id']})
        s = self.auth.login('caio', '1234')
        self.assertFalse(s.can('expenses.view'))
        self.auth.save_package(self.admin, {'title': 'Financeiro sem Despesas', 'permissions': ['finance.view', 'expenses.view']}, pkg['id'])
        self.assertTrue(self.auth.get_session(s.token).can('expenses.view'))
        with self.assertRaises(ValueError):
            self.auth.delete_package(self.admin, pkg['id'])  # em uso
        with self.assertRaises(ValueError):
            self.auth.save_package(self.admin, {'title': 'X', 'permissions': []}, 'OPERADOR')

    def test_user_changes_own_password(self):
        self.auth.create_user(self.admin, {'name': 'davi', 'password': '1234'})
        s = self.auth.login('davi', '1234')
        self.auth.change_password(s, '1234', '5678')
        self.assertEqual(self.auth.login('davi', '5678').name, 'davi')


class Rules(unittest.TestCase):
    def test_route_rules(self):
        r = required_permission
        self.assertEqual(r('POST', '/api/v1/clients/archive'), 'clients.delete')
        self.assertEqual(r('PATCH', '/api/v1/clients/x'), 'clients.edit')
        self.assertEqual(r('DELETE', '/api/v1/vehicles/x'), 'mobility.delete')
        self.assertEqual(r('POST', '/api/v1/payments/x/reverse'), 'finance.reverse')
        self.assertEqual(r('POST', '/api/v1/billing/payments'), 'finance.pay')
        self.assertEqual(r('GET', '/api/v1/expenses'), 'expenses.view')
        self.assertEqual(r('GET', '/api/v1/backups'), 'system')
        self.assertEqual(r('POST', '/api/v1/users'), 'users.manage')
        self.assertEqual(r('POST', '/api/v1/packages'), 'system')
        self.assertIsNone(r('GET', '/api/v1/auth/me'))
        self.assertEqual(r('GET', '/api/v1/unknown'), 'system', 'rota nova sem regra = só administrador')

    def test_packages_shape(self):
        self.assertNotIn('system', GERENTE); self.assertIn('clients.delete', GERENTE)
        self.assertFalse({'clients.delete', 'expenses.view', 'finance.reverse', 'catalog.costs'} & OPERADOR)
        self.assertTrue(OPERADOR < ALL)

    def test_data_filters(self):
        d = restrict_dashboard({'period': {'revenue_cents': 1, 'expenses_cents': 2, 'result_cents': 3}, 'active_clients': 4})
        self.assertEqual(d['period'], {'revenue_cents': 1}); self.assertTrue(d['restricted'])
        self.assertEqual(strip_costs({'items': [{'price_cents': 1, 'cost_cents': 2, 'margin_cents': 3}]}), {'items': [{'price_cents': 1}]})


if __name__ == '__main__':
    unittest.main()
