"""S-11 (pesado) — 3 Servidores salvando ao mesmo tempo: ninguém perde dado, ninguém dá conflito,
todos terminam iguais à nuvem."""
import json, os, shutil, subprocess, sys, tempfile, threading, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.auth import AuthService
from ustracker.cloud import CloudClient, CloudSync, apply_pending_restore, restore_from_cloud
from ustracker.db import Database
from ustracker.services import create_client

NODE = shutil.which('node')
PW = 'senha-tres-servidores'
ROUNDS = 6


@unittest.skipUnless(NODE, 'node not available')
class ThreeServers(unittest.TestCase):
    def test_concurrent_saves_converge(self):
        proc = subprocess.Popen([NODE, str(ROOT / 'cloud' / 'harness' / 'gas_server.mjs')], stdout=subprocess.PIPE, text=True)
        tmp = tempfile.TemporaryDirectory()
        try:
            info = json.loads(proc.stdout.readline()); url = f"http://127.0.0.1:{info['port']}/exec"; key = info['secret']
            base = Path(tmp.name)
            servers = []
            ra = base / 'S1'; (ra / 'UserData').mkdir(parents=True)
            auth = AuthService(ra); auth.bootstrap('Admin', PW); s = auth.login('Admin', PW)
            cloud = CloudSync(ra, auth, debounce=0); cloud.connect(s, url, key, mode='replace'); cloud.release_turn(s)
            servers.append((ra, auth, s, cloud))
            for name in ('S2', 'S3'):
                r = base / name; (r / 'UserData').mkdir(parents=True)
                restore_from_cloud(r, url, key)
                a = AuthService(r); c = CloudSync(r, a, debounce=0); c.pending_secret = key
                sess = a.login('Admin', PW)
                apply_pending_restore(r, Database(r, 'production', sess.db_key), sess, c)
                servers.append((r, a, sess, c))
            errors = []

            def work(i, srv):
                r, a, sess, c = srv
                for k in range(ROUNDS):
                    try:
                        c.acquire_turn(sess, wait=120)
                        with c.db_gate:
                            create_client(Database(r, 'production', sess.db_key), 1, {'legal_name': f'S{i}-C{k}', 'email': f's{i}c{k}@x.test',
                                          'documents': [{'type': 'RG', 'number': f'RG-S{i}-{k}', 'is_primary': True}]})
                        c.mark_dirty(); c.sync_now(sess); c.release_turn(sess)
                    except Exception as exc:  # noqa
                        errors.append(f'S{i} round {k}: {exc}')

            threads = [threading.Thread(target=work, args=(i + 1, srv)) for i, srv in enumerate(servers)]
            for t in threads: t.start()
            for t in threads: t.join(600)
            self.assertEqual(errors, [])
            for r, a, sess, c in servers:
                c.pull(sess)
                names = {row[0] for row in Database(r, 'production', sess.db_key).query('SELECT legal_name FROM clients')}
                self.assertEqual(len(names), 3 * ROUNDS, r.name)
            head = CloudClient(url, key).call('ping', {})['head']
            self.assertEqual(head['generation'], 1 + 3 * ROUNDS)
        finally:
            proc.terminate(); proc.wait(5); proc.stdout.close(); tmp.cleanup()


if __name__ == '__main__':
    unittest.main()
