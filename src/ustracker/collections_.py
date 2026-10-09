"""2.8.0 — Cobrança: régua de lembretes e inadimplência.

Régua (pela mensalidade em aberto mais antiga do cliente): 3 dias antes, no dia, 3 e 7 dias depois.
O envio é em 1 clique: o sistema monta a mensagem (com valor, vencimento e o PIX copia e cola) e abre o
WhatsApp ou o e-mail; a pessoa só aperta enviar. Cada envio fica registrado e não aparece de novo na
mesma etapa.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import quote

from . import pix
from .db import Database
from .documents import brl, company, dmy, open_items
from .services import audit, now, uid

STAGES = {'BEFORE': '3 dias antes', 'TODAY': 'No dia', 'LATE3': '3 dias de atraso', 'LATE7': '7 dias de atraso'}
CHANNELS = ('WHATSAPP', 'EMAIL', 'OUTRO')

def stage_for(days: int) -> str | None:
    """``days`` = hoje − vencimento (negativo: ainda vai vencer)."""
    if -3 <= days < 0:
        return 'BEFORE'
    if days == 0:
        return 'TODAY'
    if 3 <= days < 7:
        return 'LATE3'
    if days >= 7:
        return 'LATE7'
    return None


def _clients(con) -> list:
    return con.execute('''SELECT DISTINCT c.id,c.code,c.legal_name,c.phone,c.email FROM clients c JOIN subscriptions s ON s.client_id=c.id
                          WHERE s.lifecycle_status IN ('ACTIVE','PAUSED') AND c.archived=0 ORDER BY c.legal_name''').fetchall()


def _client_state(con, c, today: date) -> dict | None:
    items = open_items(con, c['id'], None, today)
    if not items:
        return None
    oldest = min(items, key=lambda r: r['due_on'])
    days = (today - date.fromisoformat(oldest['due_on'])).days
    late = [r for r in items if r['due_on'] < today.isoformat()]
    return {'client_id': c['id'], 'code': c['code'], 'name': c['legal_name'], 'phone': c['phone'], 'email': c['email'],
            'due_on': oldest['due_on'], 'days': days, 'stage': stage_for(days), 'items': items, 'late': late,
            'open_cents': sum(r['amount_cents'] for r in items), 'late_cents': sum(r['amount_cents'] for r in late)}


def _sent(con, client_id: str, stage: str, due_on: str) -> bool:
    return con.execute('SELECT 1 FROM collection_reminders WHERE client_id=? AND stage=? AND due_on=?', (client_id, stage, due_on)).fetchone() is not None


def reminder_queue(db: Database, as_of: date | None = None) -> list[dict]:
    """Quem lembrar hoje."""
    today = as_of or date.today()
    out = []
    with db.transaction() as con:
        for c in _clients(con):
            st = _client_state(con, c, today)
            if not st or not st['stage'] or _sent(con, c['id'], st['stage'], st['due_on']):
                continue
            amount = st['late_cents'] if st['stage'].startswith('LATE') else st['open_cents']
            out.append({k: st[k] for k in ('client_id', 'code', 'name', 'phone', 'email', 'due_on', 'days', 'stage')} |
                       {'stage_label': STAGES[st['stage']], 'amount_cents': amount})
    return out


def _wa_number(phone: str | None) -> str | None:
    d = re.sub(r'\D', '', phone or '')
    if len(d) in (10, 11):
        return '55' + d
    if d.startswith('55') and len(d) in (12, 13):
        return d
    return None


def reminder_message(db: Database, client_id: str, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    with db.transaction() as con:
        c = con.execute('SELECT id,code,legal_name,phone,email FROM clients WHERE id=?', (client_id,)).fetchone()
        if not c:
            raise KeyError('client not found')
        comp = company(con)
        st = _client_state(con, c, today)
    if not st:
        raise ValueError('client has nothing to pay')
    stage = st['stage'] or ('LATE3' if st['days'] > 0 else 'BEFORE')
    late = stage.startswith('LATE')
    amount = st['late_cents'] if late and st['late_cents'] else st['open_cents']
    code = None
    if comp['pix_key'] and comp['pix_city'] and amount > 0:
        try:
            code = pix.br_code(comp['pix_key'], comp['pix_name'], comp['pix_city'], amount_cents=amount, txid=f'{c["code"] or "UST"}{st["due_on"][:7]}')
        except ValueError:
            code = None
    first = (c['legal_name'] or '').split(' ')[0]
    who = comp['name']
    if stage == 'BEFORE':
        body = f'sua mensalidade de {brl(amount)} vence em {dmy(st["due_on"])}.'
    elif stage == 'TODAY':
        body = f'sua mensalidade de {brl(amount)} vence hoje ({dmy(st["due_on"])}).'
    else:
        body = f'consta em aberto {brl(amount)}, com vencimento em {dmy(st["due_on"])} ({st["days"]} dias).'
    lines = [f'Olá, {first}! Aqui é da {who}.', f'Lembrete: {body}']
    if code:
        lines += ['Pague com PIX (copia e cola):', code]
    lines.append('Se já pagou, por favor desconsidere esta mensagem e, se puder, envie o comprovante. Obrigado!')
    text = '\n'.join(lines)
    wa = _wa_number(c['phone'])
    subject = f'{who} — lembrete de mensalidade'
    return {'client_id': client_id, 'name': c['legal_name'], 'stage': stage, 'stage_label': STAGES[stage], 'due_on': st['due_on'],
            'amount_cents': amount, 'pix_code': code, 'text': text, 'whatsapp': wa,
            'whatsapp_url': f'https://wa.me/{wa}?text={quote(text)}' if wa else None,
            'email': c['email'], 'email_url': f'mailto:{c["email"] or ""}?subject={quote(subject)}&body={quote(text)}'}


def mark_reminded(db: Database, actor: int, client_id: str, p: dict, as_of: date | None = None) -> dict:
    today = as_of or date.today()
    channel = str(p.get('channel') or 'WHATSAPP').upper()
    if channel not in CHANNELS:
        raise ValueError('invalid channel')
    with db.transaction() as con:
        c = con.execute('SELECT * FROM clients WHERE id=?', (client_id,)).fetchone()
        if not c:
            raise KeyError('client not found')
        st = _client_state(con, c, today)
        if not st:
            raise ValueError('client has nothing to pay')
        stage = str(p.get('stage') or st['stage'] or 'LATE3').upper()
        if stage not in STAGES:
            raise ValueError('invalid stage')
        rec = {'id': uid(), 'client_id': client_id, 'stage': stage, 'due_on': st['due_on'], 'channel': channel, 'sent_at': now(), 'actor': actor}
        con.execute('INSERT INTO collection_reminders(id,client_id,stage,due_on,channel,sent_at,actor) VALUES(:id,:client_id,:stage,:due_on,:channel,:sent_at,:actor)', rec)
        audit(con, actor, 'COLLECTION_REMINDER', 'client', client_id, None, {k: rec[k] for k in ('stage', 'due_on', 'channel')})
        return rec


def reminder_history(db: Database, client_id: str) -> list[dict]:
    with db.transaction() as con:
        return [dict(r) for r in con.execute('SELECT * FROM collection_reminders WHERE client_id=? ORDER BY sent_at DESC', (client_id,)).fetchall()]


def overdue(db: Database, as_of: date | None = None) -> dict:
    """Inadimplência: clientes com mensalidade vencida e não paga."""
    today = as_of or date.today()
    items = []
    with db.transaction() as con:
        clients = _clients(con)
        active = con.execute("SELECT COUNT(DISTINCT client_id) FROM subscriptions WHERE lifecycle_status='ACTIVE'").fetchone()[0]
        for c in clients:
            st = _client_state(con, c, today)
            if not st or not st['late']:
                continue
            since = min(r['due_on'] for r in st['late'])
            last = con.execute('SELECT stage,channel,sent_at FROM collection_reminders WHERE client_id=? ORDER BY sent_at DESC LIMIT 1', (c['id'],)).fetchone()
            items.append({'client_id': c['id'], 'code': c['code'], 'name': c['legal_name'], 'phone': c['phone'], 'since': since,
                          'days': (today - date.fromisoformat(since)).days, 'months': len({r['competence'] for r in st['late']}),
                          'vehicles': len({r['subscription_id'] for r in st['late']}), 'overdue_cents': st['late_cents'],
                          'last_reminder': dict(last) if last else None})
    items.sort(key=lambda r: (-r['days'], r['name']))
    total = sum(r['overdue_cents'] for r in items)
    return {'items': items, 'summary': {'clients': len(items), 'active_clients': active, 'overdue_cents': total,
                                        'clients_pct': round(100 * len(items) / active, 1) if active else 0.0}}
