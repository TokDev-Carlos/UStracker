"""H-19 (2.6 Etapa 4) — LGPD e prazo dos dados (decisão do Carlos, 2026-10-08).

* Cliente excluído SEM financeiro: depois dos 14 dias da Lixeira some por completo (fotos e anexos também).
* Cliente excluído COM financeiro: depois de 14 dias saem contatos, endereço, observações, fotos e anexos;
  ficam nome, documento, placas e todo o financeiro (prova de pagamento) por 5 anos.
* Depois de 5 anos: saem nome, documento, placas e tudo que liga a alguém; os VALORES ficam para sempre.
* Os totais recebidos e de despesas de cada mês nunca mudam.
* Exportar os dados de um cliente (para entregar ao titular).
"""
import io, json, os, sys, tempfile, unittest, zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from PIL import Image
from ustracker import media, retention
from ustracker.billing import register_subscription_payment
from ustracker.db import Database
from ustracker.extensions import set_subscription_status
from ustracker.services import archive_clients, create_catalog, create_client, create_subscription, create_vehicle
from ustracker.trash import purge_due

KEY = b'0' * 32
MKEY = b'm' * 32
UTC = timezone.utc
CPF_A, CPF_B = '52998224725', '11144477735'


def month_totals(db):
    pay = {r[0]: r[1] for r in db.query("SELECT substr(paid_on,1,7),SUM(amount_cents) FROM payments WHERE reversed_at IS NULL GROUP BY 1")}
    chg = {r[0]: r[1] for r in db.query('SELECT competence,SUM(amount_cents) FROM charges GROUP BY 1')}
    return pay, chg


class Retencao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.db = Database(self.root, 'production', KEY)
        self.plan = create_catalog(self.db, 1, {'description': 'Plano', 'category': 'Mensal', 'price': '50.00'})
        # A: com financeiro (assinatura paga e depois cancelada)
        self.a = create_client(self.db, 1, {'legal_name': 'Ana Pagadora', 'email': 'ana@x.com', 'phone': '11911112222', 'address': 'Rua A, 1', 'notes': 'gosta de café',
                                            'documents': [{'type': 'CPF', 'number': CPF_A, 'is_primary': True}]})
        self.va = create_vehicle(self.db, 1, {'client_id': self.a['id'], 'plate': 'ANA1B23', 'type': 'Carro', 'brand': 'Fiat', 'model': 'Uno', 'year': 2020})
        start = (date.today().replace(day=1) - timedelta(days=40)).replace(day=1)
        sub = create_subscription(self.db, 1, {'client_id': self.a['id'], 'start_on': start.isoformat(), 'items': [{'catalog_id': self.plan['id'], 'quantity': 1}],
                                               'target_vehicle_ids': [self.va['id']]})
        register_subscription_payment(self.db, 1, {'subscription_id': sub['id'], 'months': 2, 'paid_on': date.today().isoformat()})
        set_subscription_status(self.db, 1, sub['id'], {'lifecycle_status': 'CANCELLED', 'expected_revision': self.db.one('SELECT revision FROM subscriptions WHERE id=?', (sub['id'],))[0]})
        # B: sem financeiro
        self.b = create_client(self.db, 1, {'legal_name': 'Beto Sem Compra', 'email': 'beto@x.com', 'documents': [{'type': 'CPF', 'number': CPF_B, 'is_primary': True}]})
        self.vb = create_vehicle(self.db, 1, {'client_id': self.b['id'], 'plate': 'BET4C56', 'type': 'Moto', 'brand': 'Honda', 'model': 'CG', 'year': 2021})
        for cid in (self.a['id'], self.b['id']):
            buf = io.BytesIO(); Image.new('RGB', (60, 40), (10, 90, 200)).save(buf, 'JPEG')
            media.store(self.root, self.db, 1, MKEY, 'client', cid, buf.getvalue())
        out = archive_clients(self.db, 1, [self.a['id'], self.b['id']])
        self.assertEqual(out['blocked'], [])
        self.before = month_totals(self.db)
        self.deleted_at = datetime.now(UTC)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self):
        return sorted(p.name for p in (self.root / 'UserData' / 'Media' / 'production').glob('*') if p.is_file())

    def run_at(self, when):
        purge_due(self.root, self.db, 0, at=when)
        return retention.run(self.root, self.db, 0, at=when)

    def test_nothing_changes_during_the_14_days(self):
        out = self.run_at(self.deleted_at + timedelta(days=13))
        self.assertEqual(out, {'removed': 0, 'reduced': 0, 'anonymized': 0, 'files': []})
        self.assertEqual(self.db.one('SELECT email FROM clients WHERE id=?', (self.a['id'],))[0], 'ana@x.com')

    def test_after_14_days(self):
        n_files = len(self.files())
        out = self.run_at(self.deleted_at + timedelta(days=15))
        self.assertEqual((out['removed'], out['reduced'], out['anonymized']), (1, 1, 0))
        # B (sem financeiro) sumiu de vez, com veículo, documento e foto
        self.assertIsNone(self.db.one('SELECT 1 FROM clients WHERE id=?', (self.b['id'],)))
        self.assertIsNone(self.db.one('SELECT 1 FROM vehicles WHERE id=?', (self.vb['id'],)))
        self.assertIsNone(self.db.one('SELECT 1 FROM client_documents WHERE client_id=?', (self.b['id'],)))
        # A (com financeiro): contatos, endereço, observações e fotos saem; nome, documento, placa e financeiro ficam
        a = dict(self.db.one('SELECT * FROM clients WHERE id=?', (self.a['id'],)))
        self.assertEqual((a['email'], a['phone'], a['address'], a['notes']), (None, None, None, None))
        self.assertEqual(a['legal_name'], 'Ana Pagadora')
        self.assertTrue(self.db.one('SELECT 1 FROM client_documents WHERE client_id=? AND normalized_number=?', (self.a['id'], CPF_A)))
        self.assertEqual(self.db.one('SELECT plate FROM vehicles WHERE id=?', (self.va['id'],))[0], 'ANA1B23')
        self.assertEqual(self.db.one("SELECT COUNT(*) FROM media WHERE entity_type='client'")[0], 0)
        self.assertLess(len(self.files()), n_files)
        self.assertEqual(month_totals(self.db), self.before, 'totais do mês intactos')
        self.assertEqual(self.run_at(self.deleted_at + timedelta(days=16))['reduced'], 0, 'não repete')

    def test_after_5_years_values_stay_without_anyone(self):
        self.run_at(self.deleted_at + timedelta(days=15))
        out = self.run_at(self.deleted_at + timedelta(days=5 * 365 + 2))
        self.assertEqual(out['anonymized'], 1)
        a = dict(self.db.one('SELECT * FROM clients WHERE id=?', (self.a['id'],)))
        self.assertTrue(a['legal_name'].startswith('Cliente removido'))
        dump = json.dumps([dict(r) for t in ('clients', 'client_documents', 'client_companies', 'vehicles', 'fleets', 'payments', 'charges', 'direct_sales')
                           for r in self.db.query(f'SELECT * FROM {t}')], default=str)
        for personal in ('Ana Pagadora', CPF_A, 'ANA1B23', 'ana@x.com', 'Uno'):
            self.assertNotIn(personal, dump, personal)
        self.assertEqual(month_totals(self.db), self.before, 'os valores ficam para sempre')
        self.assertGreater(self.db.one('SELECT COUNT(*) FROM payments')[0], 0)

    def test_retention_is_recorded_in_audit_with_counts_only(self):
        self.run_at(self.deleted_at + timedelta(days=15))
        row = self.db.one("SELECT after_json FROM audit_events WHERE action='RETENTION' ORDER BY at DESC LIMIT 1")
        self.assertIsNotNone(row)
        self.assertNotIn('Ana', row[0]); self.assertNotIn('Beto', row[0])

    def test_export_client_data_for_the_holder(self):
        blob, name = retention.export_client(self.root, self.db, MKEY, self.a['id'])
        self.assertTrue(name.endswith('.zip'))
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = z.namelist()
            data = json.loads(z.read('dados.json'))
            html = z.read('dados.html').decode('utf-8')
        self.assertEqual(data['cliente']['legal_name'], 'Ana Pagadora')
        self.assertEqual([v['plate'] for v in data['veiculos']], ['ANA1B23'])
        self.assertTrue(data['pagamentos'] and data['cobrancas'])
        self.assertIn('Ana Pagadora', html)
        self.assertTrue([n for n in names if n.startswith('fotos/')], 'fotos vão junto (abertas)')

    def test_export_is_for_administrators_only(self):
        from ustracker.access import GERENTE, required_permission
        self.assertEqual(required_permission('GET', f"/api/v1/clients/{self.a['id']}/export"), 'system')
        self.assertEqual(required_permission('GET', f"/api/v1/clients/{self.a['id']}/profile"), 'clients.view')
        self.assertNotIn('system', GERENTE)


if __name__ == '__main__':
    unittest.main()
