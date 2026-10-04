"""C-10 — erros da nuvem explicam a causa (URL errada, implantação não pública, HTML, rede)."""
import io, os, sys, unittest, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.cloud import CloudClient, CloudError

GOOD = 'https://script.google.com/macros/s/AKfycbxABC/exec'
SECRET = 'a' * 48


class _Resp(io.BytesIO):
    def __init__(self, body, url): super().__init__(body); self._url = url
    def geturl(self): return self._url
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Opener:
    def __init__(self, fn): self.fn = fn
    def open(self, req, timeout=None): return self.fn(req)


def client(fn):
    return CloudClient(GOOD, SECRET, opener=_Opener(fn))


class CloudErrorTests(unittest.TestCase):
    def code(self, fn):
        with self.assertRaises(CloudError) as ctx:
            client(fn).call('ping', {}, retries=1)
        return ctx.exception

    def test_url_validation(self):
        for url, frag in [('https://script.google.com/home/projects/x/edit', 'editor'),
                          ('https://script.google.com/macros/s/X/dev', '/dev'),
                          ('https://script.google.com/macros/s/X', '/exec')]:
            with self.assertRaises(CloudError) as ctx:
                CloudClient(url, SECRET)
            self.assertEqual(ctx.exception.code, 'BAD_URL'); self.assertIn(frag, ctx.exception.detail)
        self.assertEqual(CloudClient(GOOD + '?x=1 ', ' ' + 'ab ' * 16).url, GOOD)

    def test_login_page_is_not_public(self):
        e = self.code(lambda r: _Resp(b'<html>Sign in</html>', 'https://accounts.google.com/ServiceLogin?x'))
        self.assertEqual(e.code, 'NOT_PUBLIC'); self.assertIn('Qualquer pessoa', e.detail)

    def test_http_403_and_html_error(self):
        def forbidden(r): raise urllib.error.HTTPError(GOOD, 403, 'x', {}, io.BytesIO(b''))
        self.assertEqual(self.code(forbidden).code, 'NOT_PUBLIC')
        e = self.code(lambda r: _Resp(b'<html><body>Script function not found: doPost</body></html>', GOOD))
        self.assertEqual(e.code, 'SCRIPT_NOT_READY')
        e = self.code(lambda r: _Resp(b'<html><title>Oops</title><body>Algo deu errado</body></html>', GOOD))
        self.assertEqual(e.code, 'BAD_RESPONSE'); self.assertIn('Algo deu errado', e.detail)

    def test_network_and_tls(self):
        def dns(r): raise urllib.error.URLError(OSError('[Errno 11001] getaddrinfo failed'))
        self.assertIn('DNS', self.code(dns).detail)
        def tls(r): raise urllib.error.URLError(OSError('[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed'))
        self.assertEqual(self.code(tls).code, 'TLS')


if __name__ == '__main__':
    unittest.main()
