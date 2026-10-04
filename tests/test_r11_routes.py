import asyncio
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.mobility import create_fleet, create_vehicle
from ustracker.server import create_app
from ustracker.services import create_catalog, create_client, create_client_company


def asgi_request(app, method, path, session=None, payload=None, operation_id=None):
    encoded = json.dumps(payload).encode() if payload is not None else b''
    headers = [(b'host', b'127.0.0.1:50000'), (b'content-type', b'application/json')]
    if session:
        headers += [(b'cookie', ('us_session=' + session.token).encode()),
                    (b'x-csrf-token', session.csrf.encode())]
    if operation_id:
        headers.append((b'x-operation-id', operation_id.encode()))
    elif method not in {'GET', 'HEAD', 'OPTIONS'}:
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
    status = next(message['status'] for message in messages if message['type'] == 'http.response.start')
    body = b''.join(message.get('body', b'') for message in messages if message['type'] == 'http.response.body')
    return status, json.loads(body) if body else {}


class R11SubscriptionRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = create_app(self.root)
        self.app.state.auth.bootstrap('Admin', '1234')
        self.session = self.app.state.auth.login('Admin', '1234', 'test')
        self.db = Database(self.root, 'test', self.session.db_key)
        self.client = create_client(self.db, 1, {
            'legal_name': 'Cliente API R11', 'email': 'api-r11@example.test',
            'documents': [{'type': 'RG', 'number': 'R11-ROUTE', 'is_primary': True}],
        })
        self.company = create_client_company(self.db, 1, self.client['id'], {
            'legal_name': 'Empresa API R11', 'is_primary': True,
        })
        self.fleet = create_fleet(self.db, 1, {
            'client_id': self.client['id'], 'client_company_id': self.company['id'], 'name': 'Frota API R11',
        })
        self.vehicle = create_vehicle(self.db, 1, {
            'client_id': self.client['id'], 'fleet_id': self.fleet['id'], 'plate': 'RTE1A11',
            'type': 'Carro', 'brand': 'Marca', 'model': 'Modelo', 'year': 2026,
        })
        self.plan = create_catalog(self.db, 1, {
            'description': 'Plano API R11', 'category': 'Mensal', 'price': '90.00',
        })

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, **changes):
        payload = {
            'client_id': self.client['id'], 'start_on': '2026-10-01',
            'items': [{'catalog_id': self.plan['id'], 'quantity': 1}],
            'target_vehicle_ids': [self.vehicle['id']],
        }
        payload.update(changes)
        return payload

    def test_one_endpoint_accepts_both_contexts_and_returns_hydrated_reads(self):
        client_status, client_created = asgi_request(
            self.app, 'POST', '/api/v1/subscriptions', self.session,
            self.payload(source_context='CLIENT_PROFILE'),
        )
        commercial_status, commercial_created = asgi_request(
            self.app, 'POST', '/api/v1/subscriptions', self.session,
            self.payload(source_context='COMMERCIAL', target_vehicle_ids=[], target_fleet_ids=[self.fleet['id']]),
        )

        self.assertEqual((client_status, commercial_status), (201, 201))
        self.assertEqual(client_created['targets'][0]['target_type'], 'VEHICLE')
        self.assertEqual(commercial_created['targets'][0]['target_type'], 'FLEET')
        status, listing = asgi_request(self.app, 'GET', '/api/v1/subscriptions', self.session)
        self.assertEqual(status, 200)
        self.assertEqual(len(listing['items']), 2)
        self.assertTrue(all(row['items'] and row['targets'] and row['effective_total_cents'] == 9000 for row in listing['items']))
        status, commercial = asgi_request(self.app, 'GET', '/api/v1/commercial', self.session)
        self.assertEqual(status, 200)
        self.assertTrue(all(row['items'] and row['targets'] for row in commercial['subscriptions']))
        self.assertEqual([row['id'] for row in commercial['catalog_mensal']], [self.plan['id']])
        self.assertEqual([row['id'] for row in commercial['fleets']], [self.fleet['id']])
        client_read = next(row for row in commercial['subscriptions'] if row['id'] == client_created['id'])
        self.assertEqual(client_read['vehicles'][0]['fleet_id'], self.fleet['id'])

    def test_operation_id_replay_conflict_legacy_payload_and_authentication(self):
        operation_id = 'r11-route-operation-0001'
        payload = self.payload()
        first_status, first = asgi_request(
            self.app, 'POST', '/api/v1/subscriptions', self.session, payload, operation_id,
        )
        replay_status, replay = asgi_request(
            self.app, 'POST', '/api/v1/subscriptions', self.session, payload, operation_id,
        )
        conflict_status, conflict = asgi_request(
            self.app, 'POST', '/api/v1/subscriptions', self.session,
            self.payload(due_day=15), operation_id,
        )
        legacy_status, legacy = asgi_request(
            self.app, 'POST', '/api/v1/subscriptions', self.session,
            self.payload(target_vehicle_ids=[], items=[{
                'catalog_id': self.plan['id'], 'vehicle_id': self.vehicle['id'], 'quantity': 1,
            }]),
        )
        unauthenticated_get, _ = asgi_request(self.app, 'GET', '/api/v1/subscriptions')
        unauthenticated_post, _ = asgi_request(self.app, 'POST', '/api/v1/subscriptions', payload=payload)

        self.assertEqual((first_status, replay_status, first['id'], replay['id']), (201, 201, first['id'], first['id']))
        self.assertEqual(self.db.one('SELECT COUNT(*) FROM subscriptions WHERE id=?', (first['id'],))[0], 1)
        self.assertEqual((conflict_status, conflict['error']), (422, 'VALIDATION'))
        self.assertEqual((legacy_status, legacy['targets'][0]['vehicle_id']), (201, self.vehicle['id']))
        self.assertEqual((unauthenticated_get, unauthenticated_post), (401, 401))


if __name__ == '__main__':
    unittest.main()
