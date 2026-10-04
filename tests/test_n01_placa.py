"""S-05..S-07 — placa de direção assinada; troca do Banco 1 e espelho (Banco 2) automáticos."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.auth import AuthService
from ustracker.cloud import CloudClient, CloudSync
from ustracker.db import Database
from ustracker.placa import PlacaError, build_placa, new_master, parse_form, read_placa, render_form
from ustracker.services import create_client

NODE = shutil.which('node')
FORM = """#Banco 1
Endereço Web: https://script.google.com/macros/s/AAA/exec
Chave de Conexão: 0123456789abcdef0123

#banco 2
endereco web: https://script.google.com/macros/s/BBB/exec
chave de conexao: fedcba9876543210fedc
"""


class PlacaUnit(unittest.TestCase):
    def test_form_sign_verify_and_tamper(self):
        banks = parse_form(FORM)
        self.assertEqual([b['n'] for b in banks], [1, 2]); self.assertTrue(banks[1]['url'].endswith('BBB/exec'))
        self.assertEqual(parse_form(render_form(banks))[0]['key'], banks[0]['key'])
        master = new_master(); boot = {'public': master['public'], 'company_key': master['company_key']}
        placa = build_placa(banks, master, 3)
        self.assertNotIn('0123456789abcdef0123', json.dumps(placa), 'chave nunca em texto na placa')
        self.assertEqual(read_placa(placa, boot)['banks'][1]['key'], 'fedcba9876543210fedc')
        bad = json.loads(json.dumps(placa)); bad['banks'][0]['url'] = 'https://evil.example/exec'
        with self.assertRaises(PlacaError):
            read_placa(bad, boot)
        other = new_master()
        with self.assertRaises(PlacaError):
            read_placa(placa, {'public': other['public'], 'company_key': other['company_key']})
        with self.assertRaises(PlacaError):
            parse_form('#Banco 1\nEndereço Web: http://x\nChave de Conexão: 123')


@unittest.skipUnless(NODE, 'node not available')
class BankSwitch(unittest.TestCase):
    def start(self):
        proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        info = json.loads(proc.stdout.readline()); self.procs.append(proc)
        return {'url': f"http://127.0.0.1:{info['port']}/exec", 'key': info['secret']}

    def setUp(self):
        self.procs = []; self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        for p in self.procs: p.terminate(); p.wait(5)
        self.tmp.cleanup()

    def test_mirror_then_promote_to_banco_1(self):
        b1, b2 = self.start(), self.start()
        root = Path(self.tmp.name) / 'A'; (root / 'UserData').mkdir(parents=True)
        auth = AuthService(root); auth.bootstrap('Admin', 'senha-123456'); s = auth.login('Admin', 'senha-123456')
        db = Database(root, 'production', s.db_key)
        cloud = CloudSync(root, auth, debounce=0)
        cloud.apply_banks(s, [b1, b2], 1)
        cloud.acquire_turn(s)
        create_client(db, 1, {'legal_name': 'Cliente Espelho', 'email': 'e@x.test', 'documents': [{'type': 'RG', 'number': 'RG-N01', 'is_primary': True}]})
        cloud.mark_dirty(); cloud.sync_now(s)
        h1 = CloudClient(b1['url'], b1['key']).call('ping', {})['head']; h2 = CloudClient(b2['url'], b2['key']).call('ping', {})['head']
        self.assertEqual(h1['generation'], h2['generation'], 'espelho recebe a mesma versão')
        # dono troca a ordem na placa: Banco 2 vira o principal
        out = cloud.apply_banks(s, [b2, b1], 2)
        self.assertTrue(out['switched'])
        cloud.acquire_turn(s)
        create_client(db, 1, {'legal_name': 'Depois da troca', 'email': 'd@x.test', 'documents': [{'type': 'RG', 'number': 'RG-N02', 'is_primary': True}]})
        cloud.mark_dirty(); cloud.sync_now(s)
        h2b = CloudClient(b2['url'], b2['key']).call('ping', {})['head']
        self.assertEqual(h2b['generation'], h2['generation'] + 1, 'novo principal continua a sequência sem conflito')


if __name__ == '__main__':
    unittest.main()
