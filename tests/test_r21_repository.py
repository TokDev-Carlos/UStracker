import re, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src' / 'ustracker'


class R21RepositoryBoundaryTests(unittest.TestCase):
    def test_server_opens_databases_only_through_repository(self):
        server = (SRC / 'server.py').read_text(encoding='utf-8')
        self.assertIn('repository = LocalRepository(root)', server)
        self.assertEqual(re.findall(r'(?<![.\w])Database\(', server), [])

    def test_domain_modules_do_not_touch_sqlite_drivers(self):
        allowed = {'db.py', 'auth.py', 'backup.py', 'recovery.py'}
        offenders = [p.name for p in SRC.glob('*.py') if p.name not in allowed
                     and re.search(r'^\s*(import|from)\s+(sqlite3|sqlcipher3)', p.read_text(encoding='utf-8'), re.M)]
        self.assertEqual(offenders, [])

    def test_repository_protocol_has_no_remote_provider_yet(self):
        text = (SRC / 'repository.py').read_text(encoding='utf-8')
        self.assertIn('class Repository(Protocol)', text)
        self.assertNotRegex(text, r'Remote|http|requests|supabase|firebase')


if __name__ == '__main__':
    unittest.main()
