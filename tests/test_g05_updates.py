"""G-05 — atualização pela nuvem: canal no GitHub (updates/update.json assinado + pacote .usup),
checagem a cada 3 h, download verificado, aplicação ao fechar/reabrir ou "Atualizar agora", volta automática."""
import asyncio, hashlib, json, os, shutil, sys, tempfile, threading, unittest, uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from ustracker import update_channel as uc
from ustracker.access import GERENTE, OPERADOR


def install(root: Path, version: str, key) -> None:
    """A fake portable install: metadata + package file + Trust key."""
    (root / 'Runtime' / 'Lib' / 'site-packages' / 'ustracker').mkdir(parents=True)
    (root / 'Runtime' / 'Lib' / 'site-packages' / 'ustracker' / 'marker.py').write_text(f"V = '{version}'\n")
    (root / 'frontend').mkdir(); (root / 'frontend' / 'app.js').write_text(f'// {version}\n')
    (root / 'version.md').write_text(version + '\n')
    (root / 'VERSION.json').write_text(json.dumps({'product': 'UStracker', 'version': version, 'schema_version': 14}))
    (root / 'Trust').mkdir()
    (root / 'Trust' / 'update_public_key.pem').write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    (root / 'UserData' / 'State').mkdir(parents=True)


def release_source(base: Path, version: str) -> Path:
    src = base / f'src-{version}'
    shutil.rmtree(src, ignore_errors=True)
    (src / 'Runtime' / 'Lib' / 'site-packages' / 'ustracker').mkdir(parents=True)
    (src / 'Runtime' / 'Lib' / 'site-packages' / 'ustracker' / 'marker.py').write_text(f"V = '{version}'\n")
    (src / 'frontend').mkdir(); (src / 'frontend' / 'app.js').write_text(f'// {version}\n')
    (src / 'version.md').write_text(version + '\n')
    (src / 'VERSION.json').write_text(json.dumps({'product': 'UStracker', 'version': version, 'schema_version': 14}))
    return src


class Channel:
    def __init__(self, folder: Path):
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(_Quiet, directory=str(folder)))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.httpd.server_address[1]}/update.json'

    def stop(self): self.httpd.shutdown()


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


class UpdateChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.key = Ed25519PrivateKey.generate()
        self.root = self.base / 'install'; install(self.root, '2.0.2', self.key)
        self.pub = self.base / 'channel'; self.pub.mkdir()
        self.ch = Channel(self.pub)

    def tearDown(self):
        self.ch.stop(); self.tmp.cleanup()

    def publish(self, version, level='normal', key=None):
        return uc.build_release(release_source(self.base, version), self.pub, version, level, f'Notas {version}', key or self.key)

    def svc(self):
        return uc.UpdateService(self.root, channel_url=self.ch.url)

    def test_check_download_and_apply_at_next_start(self):
        s = self.svc()
        self.assertFalse(s.check()['available'], 'canal vazio')
        self.publish('2.1.0', 'normal')
        st = s.check()
        self.assertEqual((st['available'], st['version'], st['level']), (True, '2.1.0', 'normal'))
        self.assertTrue(s.download()['downloaded'])
        self.assertTrue((self.root / 'UserData' / 'Updates' / 'pending.json').exists())
        out = uc.apply_pending(self.root, sanity=lambda r: True)
        self.assertEqual(out['to'], '2.1.0')
        self.assertEqual((self.root / 'version.md').read_text().strip(), '2.1.0')
        self.assertIn("2.1.0", (self.root / 'Runtime/Lib/site-packages/ustracker/marker.py').read_text())
        self.assertFalse((self.root / 'UserData' / 'Updates' / 'pending.json').exists(), 'pendente consumido')
        self.assertIsNone(uc.apply_pending(self.root, sanity=lambda r: True), 'nada pendente')
        self.assertFalse(self.svc().check()['available'], 'já está na última')

    def test_bad_signature_tampered_package_and_downgrade_are_refused(self):
        self.publish('2.1.0', key=Ed25519PrivateKey.generate())
        self.assertFalse(self.svc().check()['available'], 'assinatura de outra chave')
        self.publish('2.1.0')
        pkg = next(self.pub.glob('*.usup')); pkg.write_bytes(pkg.read_bytes()[:-10] + b'0123456789')
        s = self.svc(); s.check()
        with self.assertRaises(uc.UpdateError):
            s.download()
        self.publish('2.0.1')
        self.assertFalse(self.svc().check()['available'], 'nunca volta versão')

    def test_channel_must_announce_the_package_version(self):
        self.publish('2.1.0')
        m = json.loads((self.pub / 'update.json').read_text())
        body = {k: v for k, v in m.items() if k != 'sig'}; body['version'] = '2.9.0'
        m = {**body, 'sig': self.key.sign(uc._canonical(body)).hex()}
        (self.pub / 'update.json').write_text(json.dumps(m))
        s = self.svc(); self.assertTrue(s.check()['available'])
        with self.assertRaises(uc.UpdateError):
            s.download()
        self.assertFalse((self.root / 'UserData' / 'Updates' / 'pending.usup').exists())

    def test_read_only_program_folder_asks_windows_for_elevation(self):
        self.publish('2.1.0'); s = self.svc(); s.check(); s.download()
        asked = []
        orig = uc._root_writable
        uc._root_writable = lambda root: False
        try:
            with self.assertRaises(uc.UpdateError):
                uc.apply_pending(self.root, sanity=lambda r: True, elevate=lambda root: asked.append(root) or None)
            self.assertEqual(len(asked), 1)
            self.assertTrue((self.root / 'UserData' / 'Updates' / 'pending.usup').exists(), 'continua guardada')
            out = uc.apply_pending(self.root, sanity=lambda r: True, elevate=lambda root: uc.main(['--apply-pending', '--root', str(root)]))
            self.assertEqual(out['result'], 'applied')
        finally:
            uc._root_writable = orig
        self.assertEqual((self.root / 'version.md').read_text().strip(), '2.1.0')

    def test_failed_start_rolls_back(self):
        self.publish('2.1.0'); s = self.svc(); s.check(); s.download()
        with self.assertRaises(uc.UpdateError):
            uc.apply_pending(self.root, sanity=lambda r: False)
        self.assertEqual((self.root / 'version.md').read_text().strip(), '2.0.2', 'voltou sozinho')
        self.assertIn("2.0.2", (self.root / 'Runtime/Lib/site-packages/ustracker/marker.py').read_text())

    def test_critical_level_and_permissions(self):
        self.assertIn('update.apply', GERENTE); self.assertNotIn('update.apply', OPERADOR)
        self.publish('2.1.0', 'critical'); s = self.svc(); st = s.check()
        self.assertEqual(st['level'], 'critical')
        self.assertTrue(uc.can_apply(st, is_admin=False, permissions=frozenset()), 'crítica: qualquer um aplica')
        self.publish('2.1.1', 'normal'); st = s.check()
        self.assertFalse(uc.can_apply(st, is_admin=False, permissions=OPERADOR))
        self.assertTrue(uc.can_apply(st, is_admin=False, permissions=GERENTE))
        self.assertEqual(uc.CHECK_EVERY_SECONDS, 3 * 3600)


class UpdateRoutes(unittest.TestCase):
    def test_status_and_apply_now_routes(self):
        from ustracker.server import create_app
        from tests.test_g04_adm_global import call
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); app = create_app(root); auth = app.state.auth
            auth.bootstrap('Admin', 'senha-1234'); admin = auth.login('Admin', 'senha-1234')
            auth.create_user(admin, {'name': 'op', 'password': '1234', 'package_id': 'OPERADOR'})
            auth.create_user(admin, {'name': 'ger', 'password': '1234', 'package_id': 'GERENTE'})
            op, ger = auth.login('op', '1234'), auth.login('ger', '1234')
            svc = app.state.updates
            svc.state.update(available=True, version='9.9.9', level='normal', notes='x', downloaded=True)
            restarts = []; svc.restart = lambda: restarts.append(1)
            st, body = call(app, 'GET', '/api/v1/update/status', token=op.token, csrf=op.csrf)
            self.assertEqual((st, body['available'], body['can_apply']), (200, True, False))
            self.assertEqual(call(app, 'POST', '/api/v1/update/apply-now', {}, op.token, op.csrf)[0], 403)
            st, body = call(app, 'POST', '/api/v1/update/apply-now', {}, ger.token, ger.csrf)
            self.assertEqual((st, body.get('restarting')), (200, True)); self.assertEqual(restarts, [1])
            svc.state.update(level='critical')
            self.assertEqual(call(app, 'POST', '/api/v1/update/apply-now', {}, op.token, op.csrf)[0], 200, 'crítica: todos')
            app.state.cloud.stop()


if __name__ == '__main__':
    unittest.main()
