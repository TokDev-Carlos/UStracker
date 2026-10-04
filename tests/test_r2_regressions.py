import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))

from ustracker.auth import AuthService
from ustracker.server import create_app


def asgi_post(app, path):
    sent = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        await asyncio.sleep(3600)

    async def send(message):
        sent.append(message)

    scope = {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'POST', 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'headers': [(b'host', b'127.0.0.1:50000')],
        'client': ('127.0.0.1', 12345), 'server': ('127.0.0.1', 50000),
        'root_path': '',
    }
    asyncio.run(app(scope, receive, send))
    return next(x['status'] for x in sent if x['type'] == 'http.response.start')


class R2Regressions(unittest.TestCase):
    def test_four_character_secret_remains_valid(self):
        AuthService._validate_secret('abcd')
        AuthService._validate_secret('1234')
        with self.assertRaises(ValueError):
            AuthService._validate_secret('abc')

    def test_shutdown_can_be_requested_from_login_without_session(self):
        with tempfile.TemporaryDirectory() as directory:
            status = asgi_post(create_app(Path(directory)), '/api/v1/system/shutdown')
            self.assertEqual(status, 200)


if __name__ == '__main__':
    unittest.main()
