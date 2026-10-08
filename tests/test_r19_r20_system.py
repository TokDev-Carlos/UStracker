import os, re, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src')); sys.path.insert(0, str(ROOT / 'tests'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from test_r12_routes import asgi_get
from ustracker.paths import ProductPaths
from ustracker.server import create_app

SECRET = re.compile(r'(password|passwd|hash|secret|token|vrk|db_key|media_key|private)', re.I)


class R19SecretExposureTests(unittest.TestCase):
    def test_admin_and_diagnostic_reads_do_not_expose_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp))
            app.state.auth.bootstrap('Admin', '1234')
            session = app.state.auth.login('Admin', '1234', 'test')
            # G-04: /integrations is Adm Global only (local admin gets 403)
            self.assertEqual(asgi_get(app, '/api/v1/integrations', session)[0], 403)
            for path in ('/api/v1/system/runtime', '/api/v1/settings', '/api/v1/auth/setup-status', '/api/v1/stations'):
                status, body = asgi_get(app, path, session)
                self.assertEqual(status, 200, path)
                keys = []
                def walk(value):
                    if isinstance(value, dict):
                        for k, v in value.items(): keys.append(k); walk(v)
                    elif isinstance(value, list):
                        for v in value: walk(v)
                walk(body)
                self.assertFalse([k for k in keys if SECRET.search(str(k))], path)


class R20PortabilityTests(unittest.TestCase):
    def test_roots_derive_from_any_app_root(self):
        for base in ('D:/Apps/UStracker', 'E:/Pasta Com Espaço/Sistema UStracker', '/mnt/usb/copia restaurada/UStracker'):
            paths = ProductPaths.from_root(base)
            for root in (paths.data_root, paths.cache_root, paths.backup_root, paths.log_root, paths.state_root):
                self.assertTrue(str(root).startswith(str(paths.app_root)), (base, root))

    def test_product_code_has_no_hardcoded_install_path(self):
        offenders = []
        for folder in ('src', 'frontend', 'host'):
            for path in (ROOT / folder).rglob('*'):
                if path.suffix not in {'.py', '.js', '.cs', '.html', '.css'}: continue
                text = path.read_text(encoding='utf-8', errors='ignore')
                if re.search(r'[A-Za-z]:\\\\+UStracker|[A-Za-z]:/UStracker|Users\\\\+[A-Za-z]', text):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
