import asyncio
import json
import os
import sys
import tempfile
import urllib.parse
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.server import create_app
from ustracker.services import create_client, create_client_company


def asgi_get(app, path, session=None):
    url_path, _, query = path.partition('?')
    headers = [(b'host', b'127.0.0.1:50000')]
    if session:
        headers.append((b'cookie', ('us_session=' + session.token).encode()))
    messages = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        await asyncio.sleep(3600)

    async def send(message):
        messages.append(message)

    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': 'GET', 'scheme': 'http', 'path': url_path, 'raw_path': url_path.encode(),
             'query_string': query.encode(), 'headers': headers, 'client': ('127.0.0.1', 12345),
             'server': ('127.0.0.1', 50000), 'root_path': ''}
    asyncio.run(app(scope, receive, send))
    status = next(message['status'] for message in messages if message['type'] == 'http.response.start')
    body = b''.join(message.get('body', b'') for message in messages if message['type'] == 'http.response.body')
    return status, json.loads(body) if body else {}


class R12ClientEntityRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = create_app(self.root)
        self.app.state.auth.bootstrap('Admin', '1234')
        self.session = self.app.state.auth.login('Admin', '1234', 'test')
        self.db = Database(self.root, 'test', self.session.db_key)
        for index in range(35):
            name = 'Cárlos Operações' if index == 0 else f'Cliente Rota {index:02d}'
            client = create_client(self.db, 1, {
                'legal_name': name, 'phone': f'1199999{index:04d}',
                'documents': [{'type': 'RG', 'number': f'R12ROUTE{index:04d}', 'is_primary': True}],
            })
            if index == 0:
                create_client_company(self.db, 1, client['id'], {'legal_name': 'Órbita Logística', 'is_primary': True})

    def tearDown(self):
        self.tmp.cleanup()

    def get(self, query, limit=None, session=True):
        params = {'q': query}
        if limit is not None:
            params['limit'] = str(limit)
        return asgi_get(
            self.app, '/api/v1/entities/clients?' + urllib.parse.urlencode(params),
            self.session if session else None,
        )

    def test_route_requires_authentication_and_empty_query_returns_no_rows(self):
        status, _ = self.get('cliente', session=False)
        empty_status, empty = self.get('')
        self.assertEqual(status, 401)
        self.assertEqual((empty_status, empty['items'], empty['limit']), (200, [], 20))

    def test_route_matches_folded_fields_and_caps_shape_at_thirty(self):
        status, accented = self.get('CARLOS OPERACOES')
        company_status, company = self.get('orbita logistica')
        capped_status, capped = self.get('cliente rota', limit=1000)
        self.assertEqual((status, company_status, capped_status), (200, 200, 200))
        self.assertEqual((accented['items'][0]['display_name'], company['items'][0]['primary_company']),
                         ('Cárlos Operações', 'Órbita Logística'))
        self.assertEqual((capped['limit'], len(capped['items'])), (30, 30))
        self.assertEqual(set(capped['items'][0]), {
            'id', 'display_name', 'phone', 'email', 'status', 'primary_document', 'primary_company',
        })


if __name__ == '__main__':
    unittest.main()
