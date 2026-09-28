import asyncio
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))

from ustracker.db import Database
from ustracker.server import create_app
from ustracker.services import create_catalog, create_client


def asgi_request(app, method, path, session=None, payload=None):
    encoded = json.dumps(payload).encode() if payload is not None else b''
    headers = [(b'host', b'127.0.0.1:50000'), (b'content-type', b'application/json')]
    if session:
        headers += [(b'cookie', ('us_session=' + session.token).encode()),
                    (b'x-csrf-token', session.csrf.encode())]
    if method not in {'GET', 'HEAD', 'OPTIONS'}:
        headers.append((b'x-operation-id', str(uuid.uuid4()).encode()))
    messages = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': encoded, 'more_body': False}
        await asyncio.sleep(3600)

    async def send(message):
        messages.append(message)

    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
             'query_string': b'', 'headers': headers, 'client': ('127.0.0.1', 12345),
             'server': ('127.0.0.1', 50000), 'root_path': ''}
    asyncio.run(app(scope, receive, send))
    status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
    body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
    return status, json.loads(body) if body else {}


class R2RouteTests(unittest.TestCase):
    def test_sales_and_client_profile_routes_use_real_session_and_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = create_app(root)
            app.state.auth.bootstrap('Admin', '1234')
            session = app.state.auth.login('Admin', '1234', 'test')
            db = Database(root, 'test', session.db_key)
            client = create_client(db, 1, {'legal_name': 'Cliente API'})
            catalog = create_catalog(db, 1, {
                'code': 'API-R2', 'name': 'Plano API', 'category': 'Serviço',
                'kind': 'PLAN', 'price': '50.00',
            })
            status, sale = asgi_request(app, 'POST', '/api/v1/direct-sales', session, {
                'client_id': client['id'], 'sold_on': '2026-05-01',
                'items': [{'catalog_id': catalog['id'], 'quantity': 2}],
            })
            self.assertEqual(status, 201, sale)
            self.assertEqual(sale['total_cents'], 10000)
            status, listing = asgi_request(app, 'GET', '/api/v1/direct-sales', session)
            self.assertEqual((status, listing['items'][0]['id']), (200, sale['id']))
            status, changed = asgi_request(app, 'PATCH', f"/api/v1/direct-sales/{sale['id']}/status", session,
                                           {'status': 'PAID', 'paid_on': '2026-05-02', 'expected_revision': 1})
            self.assertEqual((status, changed['status']), (200, 'PAID'))
            status, profile = asgi_request(app, 'GET', f"/api/v1/clients/{client['id']}/profile", session)
            self.assertEqual((status, profile['direct_sales'][0]['id']), (200, sale['id']))
            status, _ = asgi_request(app, 'GET', '/api/v1/direct-sales')
            self.assertEqual(status, 401)


if __name__ == '__main__':
    unittest.main()
