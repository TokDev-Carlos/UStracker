"""H-16 (2.6) — achado dos testes pesados: a tela Clientes mostrava só os 500 primeiros (o resto sumia da lista)."""
import os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker.db import Database
from ustracker.services import list_clients


class ListasGrandes(unittest.TestCase):
    def test_clients_list_is_not_cut_at_500(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp), 'test', b'0' * 32)
            with db.transaction() as con:
                for i in range(620):
                    con.execute("INSERT INTO clients(id,legal_name,phone,status,created_at,updated_at) VALUES(?,?,?,'ACTIVE','2026-01-01','2026-01-01')",
                                (f'c{i:04d}', f'Cliente {i:04d}', '11900000000'))
            self.assertEqual(len(list_clients(db)), 620)


if __name__ == '__main__':
    unittest.main()
