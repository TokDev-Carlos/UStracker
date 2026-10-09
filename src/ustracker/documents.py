"""2.8.0 — Recibo de pagamento e 2ª via da mensalidade em PDF (com PIX da empresa)."""
from __future__ import annotations

from datetime import date, datetime

from . import pix
from .billing import _charges_by_competence, _comp, _shift, _status
from .db import Database
from .money import due_date
from .pdfdoc import PDF

INK, MUTED, BRAND = (0.09, 0.13, 0.2), (0.4, 0.44, 0.52), (0.08, 0.37, 0.94)


def brl(cents: int) -> str:
    v = abs(int(cents or 0))
    s = f'{v // 100:,}'.replace(',', '.') + f',{v % 100:02d}'
    return ('-R$ ' if int(cents or 0) < 0 else 'R$ ') + s


def dmy(iso: str | None) -> str:
    return f'{iso[8:10]}/{iso[5:7]}/{iso[0:4]}' if iso and len(iso) >= 10 else '—'


def my(comp: str | None) -> str:
    return f'{comp[5:7]}/{comp[0:4]}' if comp and len(comp) >= 7 else '—'


def doc_fmt(t: str | None, n: str | None) -> str:
    n = n or ''
    if t == 'CPF' and len(n) == 11:
        return f'CPF {n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}'
    if t == 'CNPJ' and len(n) == 14:
        return f'CNPJ {n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}'
    return f'{t} {n}'.strip() if n else ''


def company(con) -> dict:
    s = {r['key']: r['value'] for r in con.execute('SELECT key,value FROM settings').fetchall()}
    name = s.get('company_display_name') or s.get('company_legal_name') or 'UStracker'
    return {'name': name, 'legal': s.get('company_legal_name') or '', 'document': s.get('company_document') or '',
            'phone': s.get('contact_phone') or '', 'email': s.get('contact_email') or '', 'address': s.get('address_display') or '',
            'pix_key': s.get('pix_key') or '', 'pix_name': s.get('pix_name') or name, 'pix_city': s.get('pix_city') or ''}


def _client(con, client_id: str) -> dict:
    c = con.execute('SELECT id,code,legal_name,phone,email FROM clients WHERE id=?', (client_id,)).fetchone()
    if not c:
        raise KeyError('client not found')
    d = con.execute('''SELECT type,normalized_number FROM client_documents WHERE client_id=? AND archived=0
                       ORDER BY is_primary DESC,created_at LIMIT 1''', (client_id,)).fetchone()
    rec = dict(c)
    rec['document'] = doc_fmt(d['type'], d['normalized_number']) if d else ''
    return rec


def _plate(con, subscription_id: str) -> str:
    rows = con.execute('''SELECT v.plate FROM subscription_targets t JOIN vehicles v ON v.id=t.vehicle_id
                          WHERE t.subscription_id=? ORDER BY v.plate''', (subscription_id,)).fetchall()
    return ', '.join(r[0] for r in rows if r[0]) or '—'


def _header(pdf: PDF, comp: dict, title: str, code: str = '') -> float:
    pdf.rect(0, 0, 595.28, 6, fill=BRAND)
    pdf.text(40, 46, comp['name'], 16, bold=True, color=INK)
    info = '  ·  '.join(x for x in (comp['document'], comp['phone'], comp['email']) if x)
    if info:
        pdf.text(40, 62, info, 9, color=MUTED)
    if comp['address']:
        pdf.text(40, 74, comp['address'], 9, color=MUTED)
    pdf.text(555, 46, title, 15, bold=True, color=BRAND, align='right')
    if code:
        pdf.text(555, 62, code, 10, color=MUTED, align='right')
    pdf.line(40, 88, 555, 88, 1)
    return 108


def _table(pdf: PDF, y: float, cols: list[tuple[str, float, str]], rows: list[list[str]]) -> float:
    pdf.rect(40, y - 12, 515, 18)
    for (label, x, align) in cols:
        pdf.text(x, y, label, 8.5, bold=True, color=MUTED, align=align)
    y += 18
    for row in rows:
        if y > 760:
            pdf.page(); y = 60
        for (label, x, align), value in zip(cols, row):
            pdf.text(x, y, value, 9.5, align=align)
        pdf.line(40, y + 6, 555, y + 6)
        y += 18
    return y


def _footer(pdf: PDF) -> None:
    pdf.text(40, 812, f'Emitido em {datetime.now().strftime("%d/%m/%Y %H:%M")} pelo UStracker.', 8, color=MUTED)


def receipt_pdf(db: Database, payment_id: str) -> tuple[bytes, str]:
    with db.transaction() as con:
        p = con.execute('SELECT * FROM payments WHERE id=?', (payment_id,)).fetchone()
        if not p:
            raise KeyError('payment not found')
        comp, cli = company(con), _client(con, p['client_id'])
        rows = []
        for a in con.execute('''SELECT pa.amount_cents,c.competence,c.subscription_id,s.code FROM payment_allocations pa
                                JOIN charges c ON c.id=pa.charge_id JOIN subscriptions s ON s.id=c.subscription_id
                                WHERE pa.payment_id=? AND pa.active=1 ORDER BY c.competence,s.code''', (payment_id,)).fetchall():
            rows.append([a['code'] or '—', _plate(con, a['subscription_id']), my(a['competence']), brl(a['amount_cents'])])
        discount = -int(con.execute("SELECT COALESCE(SUM(amount_cents),0) FROM charge_adjustments WHERE kind='DISCOUNT' AND reason=?",
                                    (f'Desconto no pagamento {payment_id}',)).fetchone()[0] or 0)
        credit = int(con.execute('SELECT COALESCE(SUM(amount_cents),0) FROM credits WHERE origin_payment_id=?', (payment_id,)).fetchone()[0] or 0)
    pdf = PDF('Recibo')
    y = _header(pdf, comp, 'RECIBO', p['code'] or '')
    if p['reversed_at']:
        pdf.text(555, 78, 'ESTORNADO', 12, bold=True, color=(0.77, 0.24, 0.29), align='right')
    pdf.text(40, y, 'Recebemos de', 9, color=MUTED)
    pdf.text(40, y + 16, cli['legal_name'], 13, bold=True)
    pdf.text(40, y + 31, '  ·  '.join(x for x in (cli['code'], cli['document']) if x), 9, color=MUTED)
    pdf.text(555, y, 'Valor recebido', 9, color=MUTED, align='right')
    pdf.text(555, y + 20, brl(p['amount_cents']), 18, bold=True, color=BRAND, align='right')
    y += 58
    pdf.text(40, y, f'Data do pagamento: {dmy(p["paid_on"])}', 10)
    pdf.text(300, y, f'Forma: {p["method"] or "—"}', 10)
    y += 26
    pdf.text(40, y, 'Referente a', 10, bold=True)
    y = _table(pdf, y + 18, [('Assinatura', 46, 'left'), ('Veículo', 200, 'left'), ('Mês', 360, 'left'), ('Valor', 549, 'right')],
               rows or [['—', '—', '—', brl(p['amount_cents'])]])
    if discount:
        pdf.text(549, y + 4, f'Desconto: {brl(discount)}', 9.5, color=MUTED, align='right'); y += 16
    if credit:
        pdf.text(549, y + 4, f'Crédito para o próximo pagamento: {brl(credit)}', 9.5, color=MUTED, align='right'); y += 16
    pdf.text(549, y + 10, f'Total: {brl(p["amount_cents"])}', 12, bold=True, align='right')
    if p['notes']:
        pdf.text(40, y + 40, f'Obs.: {p["notes"]}', 9, color=MUTED)
    pdf.line(330, 740, 555, 740, 0.8, color=INK)
    pdf.text(330, 754, comp['legal'] or comp['name'], 9, color=MUTED)
    _footer(pdf)
    name = f'Recibo_{(p["code"] or payment_id[:8])}_{(p["paid_on"] or "")[:10]}.pdf'
    return pdf.output(), name


def open_items(con, client_id: str, subscription_ids: list[str] | None, today: date) -> list[dict]:
    """Mensalidades a cobrar: as vencidas e a do mês (se não pagas); em dia, a próxima."""
    subs = con.execute("SELECT * FROM subscriptions WHERE client_id=? AND lifecycle_status IN ('ACTIVE','PAUSED') ORDER BY code", (client_id,)).fetchall()
    if subscription_ids:
        subs = [s for s in subs if s['id'] in set(subscription_ids)]
    rows = []
    current = _comp(today)
    for s in subs:
        st = _status(con, s, today)
        charges = _charges_by_competence(con, s['id'])
        comp = st['next_due']
        last = max(current, comp)
        while comp <= last:
            ch = charges.get(comp)
            if not ch or ch['status'] != 'PAID':
                amount = int(ch['open_cents']) if ch else int(st['monthly_cents'])
                due = ch['due_on'] if ch else due_date(comp, int(s['due_day'])).isoformat()
                if amount > 0:
                    rows.append({'subscription_id': s['id'], 'code': s['code'], 'plate': _plate(con, s['id']), 'competence': comp,
                                 'due_on': due, 'amount_cents': amount})
            comp = _shift(comp, 1)
    rows.sort(key=lambda r: (r['competence'], r['code'] or ''))
    return rows


def bill_pdf(db: Database, client_id: str, subscription_ids: list[str] | None = None, as_of: date | None = None) -> tuple[bytes, str, dict]:
    today = as_of or date.today()
    with db.transaction() as con:
        comp, cli = company(con), _client(con, client_id)
        rows = open_items(con, client_id, subscription_ids, today)
    total = sum(r['amount_cents'] for r in rows)
    code = None
    if comp['pix_key'] and comp['pix_city'] and total > 0:
        try:
            code = pix.br_code(comp['pix_key'], comp['pix_name'], comp['pix_city'], amount_cents=total,
                               txid=f'{cli["code"] or "UST"}{rows[0]["competence"] if rows else ""}')
        except ValueError:
            code = None
    pdf = PDF('2ª via')
    y = _header(pdf, comp, '2ª VIA', 'Mensalidade')
    pdf.text(40, y, 'Cliente', 9, color=MUTED)
    pdf.text(40, y + 16, cli['legal_name'], 13, bold=True)
    pdf.text(40, y + 31, '  ·  '.join(x for x in (cli['code'], cli['document']) if x), 9, color=MUTED)
    pdf.text(555, y, 'Total a pagar', 9, color=MUTED, align='right')
    pdf.text(555, y + 20, brl(total), 18, bold=True, color=BRAND, align='right')
    y += 58
    y = _table(pdf, y, [('Assinatura', 46, 'left'), ('Veículo', 170, 'left'), ('Mês', 320, 'left'), ('Vencimento', 400, 'left'), ('Valor', 549, 'right')],
               [[r['code'] or '—', r['plate'], my(r['competence']), dmy(r['due_on']), brl(r['amount_cents'])] for r in rows] or [['—', '—', '—', '—', brl(0)]])
    pdf.text(549, y + 10, f'Total: {brl(total)}', 12, bold=True, align='right')
    y += 40
    if code:
        if y > 560:
            pdf.page(); y = 60
        pdf.text(40, y, 'Pague com PIX', 13, bold=True, color=BRAND)
        pdf.qr(pix.qr_matrix(code), 40, y + 12, 150)
        pdf.text(210, y + 26, 'Abra o app do banco, escolha PIX › Ler QR Code', 10)
        pdf.text(210, y + 42, 'ou use o PIX copia e cola:', 10)
        chunk, yy = 52, y + 62
        for i in range(0, len(code), chunk):
            pdf.text(210, yy, code[i:i + chunk], 8.5, color=INK); yy += 12
        pdf.text(210, yy + 10, f'Recebedor: {comp["pix_name"]}', 9, color=MUTED)
        pdf.text(210, yy + 24, 'Depois de pagar, envie o comprovante.', 9, color=MUTED)
    else:
        pdf.text(40, y, 'PIX não configurado. Peça os dados de pagamento à empresa.', 10, color=MUTED)
    _footer(pdf)
    name = f'2a_via_{cli["code"] or "cliente"}_{today.isoformat()}.pdf'
    return pdf.output(), name, {'rows': rows, 'total_cents': total, 'pix_code': code, 'client': cli}
