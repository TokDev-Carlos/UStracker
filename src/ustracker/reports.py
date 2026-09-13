from __future__ import annotations

import csv
import io
from openpyxl import Workbook
from .db import Database

DANGEROUS = ('=', '+', '-', '@')
REPORTS = {
    'clients': (
        ['ID', 'Nome legal', 'Fantasia', 'Nome público', 'Documento', 'E-mail', 'Telefone', 'Status'],
        'SELECT id,legal_name,trade_name,public_name,document,email,phone,status FROM clients ORDER BY legal_name',
    ),
    'vehicles': (
        ['ID', 'Cliente', 'Frota', 'Placa', 'Tipo', 'RENAVAM', 'Rastreador', 'Status'],
        'SELECT id,client_id,fleet_id,plate,type,renavam,tracker_serial_imei,tracking_status FROM vehicles ORDER BY plate',
    ),
    'charges': (
        ['ID', 'Cliente', 'Assinatura', 'Competência', 'Vencimento', 'Valor', 'Ajustes', 'Status'],
        'SELECT id,client_id,subscription_id,competence,due_on,amount_cents,adjustment_cents,status FROM charges ORDER BY due_on DESC',
    ),
    'payments': (
        ['ID', 'Cliente', 'Data', 'Valor', 'Método', 'Estornado em'],
        'SELECT id,client_id,paid_on,amount_cents,method,reversed_at FROM payments ORDER BY paid_on DESC',
    ),
    'credits': (
        ['ID', 'Cliente', 'Pagamento origem', 'Valor', 'Saldo', 'Status'],
        'SELECT id,client_id,origin_payment_id,amount_cents,balance_cents,status FROM credits ORDER BY created_at DESC',
    ),
    'expenses': (
        ['ID', 'Categoria', 'Descrição', 'Competência', 'Vencimento', 'Previsto', 'Fornecedor', 'Status'],
        'SELECT id,category,description,competence,due_on,expected_amount_cents,supplier,status FROM expenses ORDER BY competence DESC,due_on DESC',
    ),
}


def safe_text(value):
    s = '' if value is None else str(value)
    return "'" + s if s.startswith(DANGEROUS) else s


def _report(db: Database, name: str):
    if name not in REPORTS:
        raise ValueError('unknown report')
    headers, sql = REPORTS[name]
    return headers, db.query(sql)


def report_csv(db: Database, name: str) -> bytes:
    headers, rows = _report(db, name)
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_text(x) for x in row])
    return ('\ufeff' + out.getvalue()).encode('utf-8')


def report_xlsx(db: Database, name: str) -> bytes:
    headers, rows = _report(db, name)
    wb = Workbook()
    ws = wb.active
    ws.title = name[:31].title()
    ws.append(headers)
    for row in rows:
        ws.append([safe_text(x) for x in row])
    for column in ws.columns:
        letter = column[0].column_letter
        width = max(10, min(45, max(len(str(cell.value or '')) for cell in column) + 2))
        ws.column_dimensions[letter].width = width
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def client_csv(db: Database) -> bytes:
    return report_csv(db, 'clients')


def client_xlsx(db: Database) -> bytes:
    return report_xlsx(db, 'clients')
