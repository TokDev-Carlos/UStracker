"""C-11 — testes pesados da nuvem contra o Code.gs real (Node + serviços Google simulados).

* banco grande (vários pedaços de 4 MB) sobe e volta byte a byte;
* muitas fotos (blobs) de uma vez, com reenvio idempotente;
* 12 envios seguidos, 15 dias depois a limpeza diária mantém só o ponto atual,
  e um computador novo ainda restaura tudo;
* pedido adulterado e pedido repetido são recusados.
"""
import io, json, os, secrets, shutil, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from PIL import Image
from ustracker import media
from ustracker.auth import AuthService
from ustracker.cloud import CloudClient, CloudError, CloudSync, apply_pending_restore, restore_from_cloud
from ustracker.db import Database
from ustracker.expenses import create_company_expense
from ustracker.services import create_client
from ustracker.station import ensure_station

NODE = shutil.which('node')
PASSWORD = 'senha-da-nuvem-123'


@unittest.skipUnless(NODE, 'node not available')
class CloudHeavy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        info = json.loads(cls.proc.stdout.readline())
        cls.base = f"http://127.0.0.1:{info['port']}"
        cls.url = cls.base + '/exec'
        cls.secret = info['secret']

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(5)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def get(self, path):
        return json.loads(urllib.request.urlopen(self.base + path).read() or b'{}')

    def test_1_big_snapshot_and_many_blobs(self):
        client = CloudClient(self.url, self.secret)
        data = secrets.token_bytes(9 * 1024 * 1024 + 123)  # 3 pedaços
        t = time.time()
        snap = client.upload(data, {'kind': 'auth', 'dataset_id': 'heavy-test', 'environment': 'production'})
        manifest, back = client.download('auth', snap['id'])
        self.assertEqual(back, data)
        self.assertEqual(len(manifest['parts']), 3)
        blobs = {f'm.heavy{i:03d}.bin': secrets.token_bytes(30_000 + i) for i in range(60)}
        for name, payload in blobs.items():
            client.put_blob(name, payload)
        client.put_blob('m.heavy000.bin', blobs['m.heavy000.bin'])  # reenvio não duplica
        listed = client.call('list_blobs', {})
        names = [b['name'] if isinstance(b, dict) else b for b in (listed.get('names') or listed.get('blobs') or listed.get('items') or [])]
        self.assertEqual(sum(1 for n in names if n.startswith('m.heavy')), 60)
        self.assertEqual(client.get_blob('m.heavy059.bin'), blobs['m.heavy059.bin'])
        self.assertLess(time.time() - t, 120)

    def test_2_tampered_and_replayed_requests_are_refused(self):
        client = CloudClient(self.url, self.secret)
        with self.assertRaises(CloudError) as ctx:
            CloudClient(self.url, self.secret[:-1] + ('0' if self.secret[-1] != '0' else '1')).call('ping', {}, retries=1)
        self.assertEqual(ctx.exception.code, 'AUTH')
        # same nonce twice -> REPLAY
        import hashlib, hmac
        body = '{}'; ts = int(time.time() * 1000); nonce = secrets.token_hex(16)
        sig = hmac.new(self.secret.encode(), f'ping\n{ts}\n{nonce}\n{body}'.encode(), hashlib.sha256).hexdigest()
        payload = json.dumps({'v': 1, 'action': 'ping', 'ts': ts, 'nonce': nonce, 'body': body, 'sig': sig}).encode()
        first = json.loads(client.opener.open(urllib.request.Request(self.url, data=payload, method='POST')).read())
        second = json.loads(client.opener.open(urllib.request.Request(self.url, data=payload, method='POST')).read())
        self.assertTrue(first['ok']); self.assertEqual(second.get('error'), 'REPLAY')

    def test_3_many_syncs_then_retention_and_restore(self):
        root = self.dir / 'A'; (root / 'UserData').mkdir(parents=True)
        auth = AuthService(root); auth.bootstrap('Admin', PASSWORD)
        session = auth.login('Admin', PASSWORD, 'production')
        db = Database(root, 'production', session.db_key); ensure_station(root, db)
        sync = CloudSync(root, auth, debounce=0)
        sync.connect(session, self.url, self.secret, mode='replace')
        for i in range(12):
            c = create_client(db, 1, {'legal_name': f'Cliente Pesado {i}', 'email': f'h{i}@x.test', 'documents': [{'type': 'RG', 'number': f'RG-HEAVY-{i}', 'is_primary': True}]})
            buf = io.BytesIO(); Image.new('RGB', (320, 200), (i * 20 % 255, 80, 160)).save(buf, 'JPEG')
            media.store(root, db, 1, session.media_key, 'client', c['id'], buf.getvalue())
            create_company_expense(db, 1, {'category': 'Outros', 'description': f'Despesa {i}', 'amount': '1,00', 'repeat': 'ONCE'})
            sync.sync_now(session)
        self.assertGreaterEqual(len(sync.points(session)), 12)
        self.get('/__clock?days=15'); self.get('/__daily'); self.get('/__clock?days=0')
        points = sync.points(session)
        self.assertEqual(len(points), 1); self.assertTrue(points[0]['is_head'])
        # computador novo, 15 dias depois: tudo volta
        new = self.dir / 'B'; (new / 'UserData').mkdir(parents=True)
        restore_from_cloud(new, self.url, self.secret)
        auth_b = AuthService(new); sb = auth_b.login('Admin', PASSWORD, 'production')
        apply_pending_restore(new, Database(new, 'production', sb.db_key), sb, None)
        db_b = Database(new, 'production', sb.db_key)
        self.assertEqual(db_b.one("SELECT COUNT(*) FROM clients WHERE legal_name LIKE 'Cliente Pesado %'")[0], 12)
        self.assertEqual(db_b.one('SELECT COUNT(*) FROM media')[0], 12)
        mid = db_b.one('SELECT id FROM media LIMIT 1')[0]
        self.assertGreater(len(media.load(new, db_b, sb.media_key, mid, 'thumb')[0]), 100)


if __name__ == '__main__':
    unittest.main()
