"""H-13 (2.5.0) — a primeira ativação 2.5 do Adm Global zera a nuvem antiga uma vez (época 25, tudo na _lixeira);
as máquinas seguintes entram na empresa nova; a nuvem recusa gravação de outra época."""
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import adm_global as ag
from ustracker.cloud import CLOUD_EPOCH, CloudClient, CloudError
from ustracker.placa import build_placa, new_master, save_bootstrap
from ustracker.server import create_app
from tests.test_h01_activation import NODE, PIN, RepoServer, gas, call


@unittest.skipUnless(NODE, 'node not available')
class EpocaAtivacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        os.environ['USTRACKER_BACKUPS'] = str(self.base / 'bk')
        self.repo = RepoServer()
        self.trust, token, self.keys = ag.create('crj', PIN, url=self.repo.base + '/token-mestre.json', read_token=self.repo.read_token)
        self.repo.files['token-mestre.json'] = token
        self.master = new_master()
        self.repo.files['company-key.json'] = ag.wrap_company_key(self.master['company_key'], self.trust)
        self.proc, url, secret = gas()
        self.bank = {'url': url, 'key': secret}
        self.repo.files['placa.json'] = build_placa([self.bank], self.master, 1)
        self.apps = []

    def tearDown(self):
        for app in self.apps:
            app.state.cloud.stop(); app.state.updates.stop()
        self.proc.terminate(); self.proc.wait(5); self.repo.stop(); self.tmp.cleanup()
        os.environ.pop('USTRACKER_BACKUPS', None)

    def machine(self, name):
        root = self.base / name
        ag.save_trust(root, self.trust); save_bootstrap(root, url=self.repo.base + '/placa.json', master=self.master)
        app = create_app(root); self.apps.append(app)
        return root, app

    def activate(self, app):
        call(app, 'POST', '/api/v1/auth/activate', {'name': 'crj', 'password': PIN}, precsrf=True)
        return call(app, 'POST', '/api/v1/auth/activate', {'name': 'crj', 'password': PIN, 'answer': PIN}, precsrf=True)


    def test_first_25_activation_resets_old_cloud_once_and_second_machine_joins(self):
        raw = CloudClient(self.bank['url'], self.bank['key'], epoch=0)
        self.assertEqual(raw.call('ping', {}, check_epoch=False)['epoch'], 0)
        raw.call('put_blob', {'name': 'foto-antiga.webp', 'data': 'eA==', 'sha256': '2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'})
        root_a, app_a = self.machine('A')
        st, body = self.activate(app_a)
        self.assertEqual(st, 200, body); self.assertTrue(body.get('new_company')); self.assertTrue(body.get('cloud_reset'))
        ping = CloudClient(self.bank['url'], self.bank['key']).call('ping', {})
        self.assertEqual(ping['epoch'], CLOUD_EPOCH)
        self.assertTrue(ping['head'] and ping['auth_head'], 'empresa nova já subiu')
        self.assertNotIn('foto-antiga.webp', CloudClient(self.bank['url'], self.bank['key']).call('list_blobs', {})['names'])
        with self.assertRaises(CloudError) as ctx:  # versão antiga (sem época) não grava mais
            raw.call('put_blob', {'name': 'foto-velha2.webp', 'data': 'eA==', 'sha256': '2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'})
        self.assertEqual(ctx.exception.code, 'EPOCH')
        root_b, app_b = self.machine('B')
        st, body = self.activate(app_b)
        self.assertEqual(st, 200, body); self.assertTrue(body.get('restored')); self.assertFalse(body.get('cloud_reset'))
        self.assertEqual(CloudClient(self.bank['url'], self.bank['key']).call('ping', {})['epoch'], CLOUD_EPOCH, 'não zera de novo')


if __name__ == '__main__':
    unittest.main()
