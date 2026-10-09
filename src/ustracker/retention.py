"""2.6 — LGPD: prazo dos dados de cliente excluído (decisão do Carlos, 2026-10-08) e exportação para o titular.

Linha do tempo de um cliente excluído (a exclusão já passa pela Lixeira de 14 dias):
* até 14 dias: nada muda (Lixeira; volta inteiro);
* depois de 14 dias:
  - SEM financeiro: sai de vez (cadastro, documentos, empresas, frotas, veículos, fotos e anexos);
  - COM financeiro: saem contatos, endereço, observações, fotos e anexos; ficam nome, documento,
    placas e todo o financeiro, como prova de pagamento, por 5 anos;
* depois de 5 anos: saem nome, documento, placas e tudo que liga a alguém. Os valores ficam para sempre
  (data, competência, tipo, forma de pagamento, valor), ligados só a "Cliente removido #XXXX".
Os totais de cada mês nunca mudam (nenhum valor é apagado). Cada passada fica na auditoria só com quantidades.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from .db import Database
from .services import audit, now

UTC = timezone.utc
TRASH_DAYS = 14
KEEP_YEARS = 5
FINANCIAL = ('charges', 'payments', 'credits', 'direct_sales', 'service_coverage_periods', 'expenses')
DDL = '''CREATE TABLE IF NOT EXISTS client_retention(
  client_id TEXT PRIMARY KEY, stage INTEGER NOT NULL, deleted_at TEXT NOT NULL, stage1_at TEXT, stage2_at TEXT)'''


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _has_financial(con, cid: str) -> bool:
    return any(con.execute(f'SELECT 1 FROM {t} WHERE client_id=? LIMIT 1', (cid,)).fetchone() for t in FINANCIAL)


def _ids(con, sql: str, args: tuple) -> list[str]:
    return [r[0] for r in con.execute(sql, args).fetchall()]


def _drop_media_and_files(con, cid: str, vehicles: list[str], fleets: list[str]) -> list[str]:
    """Fotos e anexos do cliente, dos veículos e das frotas: apaga os registros e devolve os arquivos a apagar."""
    files: list[str] = []
    for kind, ids in (('client', [cid]), ('vehicle', vehicles), ('fleet', fleets)):
        for mid in ids:
            for row in con.execute('SELECT * FROM media WHERE entity_type=? AND entity_id=?', (kind, mid)).fetchall():
                files += [f'm:{Path(str(row[c]).replace(chr(92), "/")).name}' for c in ('variant_path', 'thumb_path', 'original_path') if row[c]]
            con.execute('DELETE FROM media WHERE entity_type=? AND entity_id=?', (kind, mid))
    marks = ','.join('?' * (1 + len(vehicles) + len(fleets)))
    where = f'client_id=? OR vehicle_id IN ({marks}) OR fleet_id IN ({marks})'
    args = (cid, cid, *vehicles, *fleets, cid, *vehicles, *fleets)
    for row in con.execute(f'SELECT local_path FROM attachments WHERE {where}', args).fetchall():
        if row[0]:
            files.append('a:' + Path(str(row[0]).replace('\\', '/')).name)
    con.execute(f'DELETE FROM attachments WHERE {where}', args)
    return files


def _remove_everything(con, cid: str, vehicles: list[str], fleets: list[str]) -> None:
    subs = _ids(con, 'SELECT id FROM subscriptions WHERE client_id=?', (cid,))
    for sid in subs:
        for t in ('subscription_targets', 'subscription_items'):
            con.execute(f'DELETE FROM {t} WHERE subscription_id=?', (sid,))
    con.execute('DELETE FROM subscriptions WHERE client_id=?', (cid,))
    for vid in vehicles:
        con.execute('DELETE FROM vehicle_transfer_cases WHERE vehicle_id=?', (vid,))
    con.execute('DELETE FROM vehicle_transfer_cases WHERE from_client_id=? OR to_client_id=?', (cid, cid))
    con.execute('DELETE FROM ownerships WHERE client_id=?', (cid,))
    for vid in vehicles:
        con.execute('DELETE FROM ownerships WHERE vehicle_id=?', (vid,))
        con.execute('DELETE FROM vehicles WHERE id=?', (vid,))
    for fid in fleets:
        con.execute('DELETE FROM fleets WHERE id=?', (fid,))
    for t in ('client_documents', 'client_companies', 'collection_reminders'):
        con.execute(f'DELETE FROM {t} WHERE client_id=?', (cid,))
    con.execute('UPDATE logical_codes SET client_id=NULL WHERE client_id=?', (cid,))
    con.execute('DELETE FROM clients WHERE id=?', (cid,))


def _reduce(con, cid: str, vehicles: list[str]) -> None:
    con.execute('UPDATE clients SET email=NULL,phone=NULL,address=NULL,notes=NULL,updated_at=? WHERE id=?', (now(), cid))
    for vid in vehicles:
        con.execute('UPDATE vehicles SET notes=NULL WHERE id=?', (vid,))


def _anonymize(con, cid: str, vehicles: list[str], fleets: list[str]) -> None:
    tag = cid.replace('-', '')[:4].upper()
    con.execute('''UPDATE clients SET legal_name=?,trade_name=NULL,public_name=NULL,document=NULL,email=NULL,phone=NULL,
                   address=NULL,notes=NULL,updated_at=? WHERE id=?''', (f'Cliente removido #{tag}', now(), cid))
    con.execute('DELETE FROM client_documents WHERE client_id=?', (cid,))
    con.execute('DELETE FROM collection_reminders WHERE client_id=?', (cid,))
    con.execute("UPDATE client_companies SET legal_name='Empresa removida',trade_name=NULL,document=NULL,normalized_document=NULL WHERE client_id=?", (cid,))
    for i, vid in enumerate(vehicles):
        con.execute('''UPDATE vehicles SET plate=?,brand=NULL,model=NULL,year=NULL,renavam=NULL,tracker_ref=NULL,tracker_serial_imei=NULL,
                       notes=NULL WHERE id=?''', (f'REM{tag}{i:03d}', vid))
    for fid in fleets:
        con.execute("UPDATE fleets SET name='Frota removida',sector_or_unit=NULL WHERE id=?", (fid,))
    con.execute('UPDATE payments SET notes=NULL WHERE client_id=?', (cid,))
    con.execute('UPDATE direct_sales SET notes=NULL WHERE client_id=?', (cid,))
    con.execute("UPDATE charge_adjustments SET reason='(removido)' WHERE charge_id IN (SELECT id FROM charges WHERE client_id=?)", (cid,))


def run(root: Path | str, db: Database, actor: int = 0, at: datetime | None = None) -> dict:
    """Uma passada (roda sozinha junto da limpeza da Lixeira). Tudo numa transação; arquivos só depois."""
    when = at or datetime.now(UTC)
    out = {'removed': 0, 'reduced': 0, 'anonymized': 0, 'files': []}
    with db.transaction() as con:
        con.execute(DDL)
        due = con.execute('''SELECT t.entity_id,t.deleted_at FROM trash t JOIN clients c ON c.id=t.entity_id
                             WHERE t.entity_type='client' AND t.purged_at IS NOT NULL AND t.restored_at IS NULL AND c.archived=1
                               AND t.entity_id NOT IN (SELECT client_id FROM client_retention)''').fetchall()
        for cid, deleted_at in due:
            if when - datetime.fromisoformat(deleted_at) < timedelta(days=TRASH_DAYS):
                continue
            vehicles = _ids(con, 'SELECT id FROM vehicles WHERE client_id=?', (cid,))
            fleets = _ids(con, 'SELECT id FROM fleets WHERE client_id=?', (cid,))
            out['files'] += _drop_media_and_files(con, cid, vehicles, fleets)
            if _has_financial(con, cid):
                _reduce(con, cid, vehicles)
                con.execute('INSERT INTO client_retention(client_id,stage,deleted_at,stage1_at) VALUES(?,1,?,?)', (cid, deleted_at, _iso(when)))
                out['reduced'] += 1
            else:
                _remove_everything(con, cid, vehicles, fleets)
                out['removed'] += 1
        limit = _iso(when - timedelta(days=365 * KEEP_YEARS))
        for (cid,) in con.execute('SELECT client_id FROM client_retention WHERE stage=1 AND deleted_at<=?', (limit,)).fetchall():
            vehicles = _ids(con, 'SELECT id FROM vehicles WHERE client_id=?', (cid,))
            fleets = _ids(con, 'SELECT id FROM fleets WHERE client_id=?', (cid,))
            _anonymize(con, cid, vehicles, fleets)
            con.execute('UPDATE client_retention SET stage=2,stage2_at=? WHERE client_id=?', (_iso(when), cid))
            out['anonymized'] += 1
        if out['removed'] or out['reduced'] or out['anonymized']:
            audit(con, actor, 'RETENTION', 'retention', 'lgpd', None,
                  {k: out[k] for k in ('removed', 'reduced', 'anonymized')} | {'files': len(out['files'])})
    base = Path(root) / 'UserData'
    for item in out['files']:
        kind, _, name = item.partition(':')
        (base / ('Media' if kind == 'm' else 'Attachments') / db.environment / name).unlink(missing_ok=True)
    return out


# ---------------------------------------------------------------- exportação para o titular
def _rows(db, sql, args=()):
    return [dict(r) for r in db.query(sql, args)]


def export_client(root: Path | str, db: Database, media_key: bytes, client_id: str) -> tuple[bytes, str]:
    from . import media
    client = db.one('SELECT * FROM clients WHERE id=?', (client_id,))
    if not client:
        raise KeyError('client not found')
    data = {
        'gerado_em': datetime.now(UTC).isoformat(),
        'cliente': dict(client),
        'documentos': _rows(db, 'SELECT type,number FROM client_documents WHERE client_id=? AND archived=0', (client_id,)),
        'empresas': _rows(db, 'SELECT legal_name,trade_name,document FROM client_companies WHERE client_id=?', (client_id,)),
        'frotas': _rows(db, 'SELECT id,name,code FROM fleets WHERE client_id=?', (client_id,)),
        'veiculos': _rows(db, 'SELECT id,plate,type,brand,model,year,code FROM vehicles WHERE client_id=? ORDER BY plate', (client_id,)),
        'assinaturas': _rows(db, 'SELECT code,start_on,end_on,lifecycle_status,due_day FROM subscriptions WHERE client_id=?', (client_id,)),
        'cobrancas': _rows(db, 'SELECT competence,due_on,amount_cents,status FROM charges WHERE client_id=? ORDER BY competence', (client_id,)),
        'pagamentos': _rows(db, 'SELECT paid_on,amount_cents,method,reversed_at FROM payments WHERE client_id=? ORDER BY paid_on', (client_id,)),
        'compras': _rows(db, 'SELECT code,sold_on,total_cents,status FROM direct_sales WHERE client_id=? ORDER BY sold_on', (client_id,)),
    }
    for k in ('cobrancas', 'pagamentos', 'compras'):
        for r in data[k]:
            for col in [c for c in r if c.endswith('_cents')]:
                r[col.replace('_cents', '')] = f"{(r.pop(col) or 0) / 100:.2f}"
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('dados.json', json.dumps(data, ensure_ascii=False, indent=2, default=str))
        z.writestr('dados.html', _html(data))
        ids = [('client', client_id)] + [('vehicle', v['id']) for v in data['veiculos']] + [('fleet', f['id']) for f in data['frotas']]
        for kind, eid in ids:
            for row in db.query('SELECT id FROM media WHERE entity_type=? AND entity_id=?', (kind, eid)):
                try:
                    blob, mime = media.load(Path(root), db, media_key, row[0], 'operational')
                    z.writestr(f"fotos/{kind}_{row[0]}.{'webp' if 'webp' in mime else 'jpg'}", blob)
                except Exception:
                    continue
    name = f"dados_cliente_{client['code'] or client_id[:8]}.zip"
    return mem.getvalue(), name


def _html(d: dict) -> str:
    def table(title, rows):
        if not rows:
            return f'<h2>{escape(title)}</h2><p>Nenhum registro.</p>'
        cols = list(rows[0])
        head = ''.join(f'<th>{escape(str(c))}</th>' for c in cols)
        body = ''.join('<tr>' + ''.join(f'<td>{escape(str(r.get(c) if r.get(c) is not None else ""))}</td>' for c in cols) + '</tr>' for r in rows)
        return f'<h2>{escape(title)}</h2><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
    c = d['cliente']
    info = ''.join(f'<tr><th>{escape(k)}</th><td>{escape(str(c.get(k) or ""))}</td></tr>'
                   for k in ('code', 'legal_name', 'trade_name', 'document', 'email', 'phone', 'address', 'status', 'created_at'))
    parts = [table(t, d[k]) for t, k in (('Documentos', 'documentos'), ('Empresas', 'empresas'), ('Frotas', 'frotas'), ('Veículos', 'veiculos'),
                                          ('Assinaturas', 'assinaturas'), ('Cobranças', 'cobrancas'), ('Pagamentos', 'pagamentos'), ('Compras', 'compras'))]
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Dados do cliente</title>'
            '<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#101828}table{border-collapse:collapse;margin:6px 0 18px;width:100%}'
            'th,td{border:1px solid #d0d5dd;padding:4px 8px;text-align:left;font-size:13px}h2{font-size:16px;margin-top:20px}</style>'
            f'<h1>Dados pessoais do titular</h1><p>Gerado em {escape(d["gerado_em"][:19])}. Para salvar em PDF: Imprimir › Salvar como PDF.</p>'
            f'<table>{info}</table>' + ''.join(parts) + '</html>')
