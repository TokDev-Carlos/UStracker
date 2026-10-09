"""H-23 (2.8.0) — Cobrança: PIX da empresa (BR Code + QR), recibo e 2ª via em PDF."""
import os, sys, tempfile, unittest, zlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

from ustracker import documents, pix
from ustracker.billing import register_subscription_payment
from ustracker.db import Database
from ustracker.mobility import create_vehicle
from ustracker.services import create_catalog, create_client, create_subscription

TODAY = date(2026, 10, 9)


def pdf_text(blob: bytes) -> str:
    """Texto das páginas (o PDF do sistema guarda o conteúdo comprimido com Flate)."""
    out, i = [], 0
    while True:
        a = blob.find(b'>>\nstream\n', i)
        if a < 0:
            break
        a += 3
        b = blob.find(b'\nendstream', a)
        raw = blob[a + 7:b]
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        out.append(raw.decode('cp1252', 'replace'))
        i = b + 1
    return '\n'.join(out).replace('\\(', '(').replace('\\)', ')')


class Pix(unittest.TestCase):
    def test_reference_example_from_the_central_bank_manual(self):
        code = pix.br_code('123e4567-e12b-12d1-a456-426655440000', 'Fulano de Tal', 'BRASILIA')
        self.assertEqual(code, '00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-4266554400005204000053039865802BR'
                               '5913Fulano de Tal6008BRASILIA62070503***63041D3D')

    def test_amount_txid_and_names_without_accents(self):
        code = pix.br_code('carlos@ustracker.com.br', 'USTracker Rastreadores Ltda Me', 'São José dos Campos', amount_cents=12345, txid='CLI-0001-A01/2026-10')
        self.assertIn('5406123.45', code)
        self.assertIn('5925USTracker Rastreadores L', code)
        self.assertIn('6015Sao Jose dos Ca', code)
        self.assertIn('0516CLI0001A01202610', code)
        self.assertEqual(code[-4:], pix.crc16(code[:-4]))

    def test_key_validation(self):
        self.assertEqual(pix.normalize_key('529.982.247-25'), ('CPF', '52998224725'))
        self.assertEqual(pix.normalize_key('11.222.333/0001-81'), ('CNPJ', '11222333000181'))
        self.assertEqual(pix.normalize_key('(11) 91234-5678'), ('TELEFONE', '+5511912345678'))
        self.assertEqual(pix.normalize_key('Financeiro@X.com'), ('EMAIL', 'financeiro@x.com'))
        with self.assertRaises(ValueError):
            pix.normalize_key('123')

    def test_qr_code_reads_back_the_payload(self):
        try:
            import zxingcpp
            from PIL import Image
        except ImportError:
            self.skipTest('leitor de QR não instalado')
        payload = pix.br_code('52998224725', 'USTracker', 'Sao Paulo', amount_cents=5000, txid='TESTE1')
        m = pix.qr_matrix(payload)
        size = len(m) * 6
        img = Image.new('L', (size, size), 255)
        for y, row in enumerate(m):
            for x, dark in enumerate(row):
                if dark:
                    img.paste(0, (x * 6, y * 6, x * 6 + 6, y * 6 + 6))
        [result] = zxingcpp.read_barcodes(img)
        self.assertEqual(result.text, payload)


class Documentos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name), 'test', b'0' * 32)
        with self.db.transaction() as con:
            for k, v in (('company_display_name', 'USTracker Rastreadores'), ('pix_key', '52998224725'), ('pix_name', 'USTracker Rastreadores'), ('pix_city', 'São Paulo')):
                con.execute("INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,datetime('now'))", (k, v))
        self.client = create_client(self.db, 1, {'legal_name': 'Joana Prado', 'phone': '11988887777', 'email': 'joana@x.com',
                                                 'documents': [{'type': 'CPF', 'number': '52998224725', 'is_primary': True}]})
        plan = create_catalog(self.db, 1, {'description': 'Plano 50', 'category': 'Mensal', 'price': '50.00'})
        v = create_vehicle(self.db, 1, {'client_id': self.client['id'], 'plate': 'JOA1B23', 'type': 'Moto', 'brand': 'Honda', 'model': 'CG', 'year': 2024})
        self.sub = create_subscription(self.db, 1, {'client_id': self.client['id'], 'start_on': '2026-08-01', 'due_day': 10,
                                                    'items': [{'catalog_id': plan['id'], 'quantity': 1}], 'target_vehicle_ids': [v['id']]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_receipt_pdf(self):
        pay = register_subscription_payment(self.db, 1, {'subscription_id': self.sub['id'], 'months': 2, 'paid_on': '2026-10-09', 'method': 'PIX'}, as_of=TODAY)
        blob, name = documents.receipt_pdf(self.db, pay['id'])
        self.assertTrue(blob.startswith(b'%PDF-1.4')); self.assertTrue(blob.rstrip().endswith(b'%%EOF'))
        self.assertTrue(name.endswith('.pdf') and pay['code'] in name)
        text = pdf_text(blob)
        for piece in ('RECIBO', pay['code'], 'Joana Prado', 'R$ 100,00', '08/2026', '09/2026', 'JOA1B23', '09/10/2026', 'PIX', 'USTracker Rastreadores'):
            self.assertIn(piece, text, piece)

    def test_bill_pdf_lists_what_is_open_with_pix(self):
        blob, name, data = documents.bill_pdf(self.db, self.client['id'], as_of=TODAY)
        self.assertEqual([r['competence'] for r in data['rows']], ['2026-08', '2026-09', '2026-10'])
        self.assertEqual(data['total_cents'], 15000)
        self.assertTrue(data['pix_code'].startswith('000201') and '5406150.00' in data['pix_code'])
        text = pdf_text(blob)
        for piece in ('2ª VIA', 'Joana Prado', 'R$ 150,00', '10/08/2026', 'PIX copia e cola', data['pix_code'][:30]):
            self.assertIn(piece, text, piece)

    def test_bill_for_one_month_when_up_to_date(self):
        register_subscription_payment(self.db, 1, {'subscription_id': self.sub['id'], 'months': 3, 'paid_on': '2026-10-09'}, as_of=TODAY)
        _, _, data = documents.bill_pdf(self.db, self.client['id'], as_of=TODAY)
        self.assertEqual([r['competence'] for r in data['rows']], ['2026-11'], 'em dia: a 2ª via é da próxima mensalidade')

    def test_bill_without_pix_configured(self):
        with self.db.transaction() as con:
            con.execute("DELETE FROM settings WHERE key='pix_key'")
        blob, _, data = documents.bill_pdf(self.db, self.client['id'], as_of=TODAY)
        self.assertIsNone(data['pix_code'])
        self.assertIn('PIX não configurado', pdf_text(blob))


if __name__ == '__main__':
    unittest.main()
