from __future__ import annotations

import csv, io
from openpyxl import Workbook
from .db import Database

DANGEROUS=('=','+','-','@')
def safe_text(v):
    s='' if v is None else str(v)
    return "'"+s if s.startswith(DANGEROUS) else s

def client_csv(db:Database)->bytes:
    out=io.StringIO(); w=csv.writer(out,delimiter=';'); w.writerow(['ID','Nome legal','Fantasia','Nome público','Status'])
    for r in db.query('SELECT id,legal_name,trade_name,public_name,status FROM clients ORDER BY legal_name'):
        w.writerow([safe_text(x) for x in r])
    return ('\ufeff'+out.getvalue()).encode('utf-8')
def client_xlsx(db:Database)->bytes:
    wb=Workbook(); ws=wb.active; ws.title='Clientes'; ws.append(['ID','Nome legal','Fantasia','Nome público','Status'])
    for r in db.query('SELECT id,legal_name,trade_name,public_name,status FROM clients ORDER BY legal_name'): ws.append([safe_text(x) for x in r])
    b=io.BytesIO(); wb.save(b); return b.getvalue()
