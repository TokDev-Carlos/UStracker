"""C-07 — nuvem ponta a ponta contra o Code.gs real (rodando em Node com serviços Google simulados).

Cenários: primeira conexão, perda total da máquina/pasta, restauração em máquina nova, máquina
antiga desatualizada (conflito), Lixeira de 14 dias apagando da nuvem, ponto de restauração,
código errado. Pulado se o Node não estiver disponível.
"""
import io, json, os, shutil, subprocess, sys, tempfile, unittest, urllib.request
from datetime import datetime, timedelta, timezone
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

NODE = shutil.which('node')
PASSWORD = 'senha-da-nuvem-123'


@unittest.skipUnless(NODE, 'node not available')
class CloudEndToEnd(unittest.TestCase):
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
        self.base_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def machine(self, name, bootstrap=True):
        root = self.base_dir / name
        (root / 'UserData').mkdir(parents=True, exist_ok=True)
        auth = AuthService(root)
        if bootstrap:
            auth.bootstrap('Admin', PASSWORD)
        return root, auth

    def login(self, root, auth, sync=None):
        session = auth.login('Admin', PASSWORD, 'production')
        db = Database(root, 'production', session.db_key)
        apply_pending_restore(root, db, session, sync)
        return session, Database(root, 'production', session.db_key)

    def cloud_files(self):
        return json.loads(urllib.request.urlopen(self.base + '/__files').read())

    def test_full_disaster_cycle(self):
        # --- machine A: data + first connection
        root_a, auth_a = self.machine('A')
        sa, db_a = self.login(root_a, auth_a)
        from ustracker.station import ensure_station
        ensure_station(root_a, db_a)
        client = create_client(db_a, 1, {'legal_name': 'Cliente Nuvem', 'email': 'n@x.test', 'documents': [{'type': 'RG', 'number': 'RG-CLOUD-1', 'is_primary': True}]})
        buf = io.BytesIO(); Image.new('RGB', (64, 64), (200, 10, 10)).save(buf, 'PNG')
        photo = media.store(root_a, db_a, 1, sa.media_key, 'client', client['id'], buf.getvalue())
        create_company_expense(db_a, 1, {'category': 'Insumos', 'description': 'Chip', 'amount': '10,00', 'repeat': 'ONCE'})
        sync_a = CloudSync(root_a, auth_a, debounce=0)
        out = sync_a.connect(sa, self.url, self.secret)
        self.assertTrue(out['connected'])
        self.assertEqual(out['sync']['generation'], 1)
        self.assertEqual(out['sync']['blobs_sent'], 2)  # operational + thumb
        self.assertNotIn(self.secret, (root_a / 'UserData' / 'State' / 'cloud.json').read_text(), 'código guardado cifrado')

        # --- wrong code is refused
        with self.assertRaises(CloudError) as ctx:
            CloudClient(self.url, 'x' * 48).call('ping', {})
        self.assertEqual(ctx.exception.code, 'AUTH')

        # --- disaster: machine A is gone. Its turn expires by itself (TTL); here it is released at once
        from ustracker.station import local_identity
        CloudClient(self.url, self.secret).call('lease', {'op': 'release', 'holder': local_identity(root_a)['id']})
        # Machine B restores everything from the cloud
        root_b, _ = self.machine('B', bootstrap=False)
        info = restore_from_cloud(root_b, self.url, self.secret)
        self.assertEqual(info['generation'], 1)
        auth_b = AuthService(root_b)
        sync_b = CloudSync(root_b, auth_b, debounce=0); sync_b.pending_secret = self.secret
        sb, db_b = self.login(root_b, auth_b, sync_b)
        self.assertEqual(db_b.one("SELECT legal_name FROM clients")[0], 'Cliente Nuvem')
        self.assertEqual(db_b.one("SELECT COUNT(*) FROM expenses")[0], 1)
        self.assertGreater(len(media.load(root_b, db_b, sb.media_key, photo['id'], 'thumb')[0]), 10)
        self.assertEqual(ensure_station(root_b, db_b)['is_writer'], 1, 'máquina restaurada assume a escrita')
        sync_b.attach(sb)
        self.assertTrue(sync_b.enabled())

        # --- B keeps working; the cloud follows
        create_company_expense(db_b, 1, {'category': 'Outros', 'description': 'Depois da restauração', 'amount': '5,00', 'repeat': 'ONCE'})
        self.assertEqual(sync_b.sync_now(sb)['generation'], 2)

        # --- old machine A comes back with stale data: refused, cloud protected
        with self.assertRaises(CloudError) as ctx:
            sync_a.sync_now(sa)
        self.assertEqual(ctx.exception.code, 'CONFLICT')

        # --- deletion inside the system: photo -> Lixeira; still in the cloud for 14 days
        media.remove(root_b, db_b, 1, photo['id'])
        sync_b.sync_now(sb)
        self.assertTrue(any(photo['id'] in f for f in self.cloud_files()))
        # day 15: purge erases locally and in the cloud; old points that still had it are compacted
        sync_b.purge_trash(sb, at=datetime.now(timezone.utc) + timedelta(days=15))
        sync_b.sync_now(sb)
        self.assertFalse(any(photo['id'] in f for f in self.cloud_files()))
        points = sync_b.points(sb)
        self.assertEqual(len(points), 1)
        self.assertTrue(points[0]['is_head'])

        # --- restore point: undo a later change
        before = db_b.one('SELECT COUNT(*) FROM expenses')[0]
        create_company_expense(db_b, 1, {'category': 'Outros', 'description': 'Lançada por engano', 'amount': '1,00', 'repeat': 'ONCE'})
        sync_b.sync_now(sb)
        target = [p for p in sync_b.points(sb) if not p['is_head']][0]
        out = sync_b.restore_point(sb, target['id'])
        self.assertEqual(Database(root_b, 'production', sb.db_key).one('SELECT COUNT(*) FROM expenses')[0], before)
        self.assertEqual(sync_b.points(sb)[0]['generation'], out['new_generation'])

        # --- folder wiped outside the system: nothing was deleted in the cloud
        root_c, _ = self.machine('C', bootstrap=False)
        restore_from_cloud(root_c, self.url, self.secret)
        auth_c = AuthService(root_c)
        sc, db_c = self.login(root_c, auth_c)
        self.assertEqual(db_c.one("SELECT legal_name FROM clients")[0], 'Cliente Nuvem')
        self.assertEqual(db_c.one('SELECT COUNT(*) FROM expenses')[0], before)

    def test_restore_needs_existing_cloud_data_and_right_code(self):
        root, _ = self.machine('D', bootstrap=False)
        with self.assertRaises(CloudError):
            restore_from_cloud(root, self.url, 'y' * 48)


if __name__ == '__main__':
    unittest.main()
