"""2.6 — Diagnóstico (só administradores): backup diário conferido, avisos, retrato do sistema e pacote de suporte.

O pacote de suporte nunca leva banco, backup, senha, token, chave ou dado de cliente: só o retrato
(contagens, datas, versões) e o registro de erros com nomes, documentos, contatos e segredos apagados.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
BACKUP_STALE = timedelta(days=2)
CLOUD_STALE = timedelta(days=1)
RETRY_FAILED = timedelta(hours=1)
COUNT_TABLES = ('clients', 'vehicles', 'subscriptions', 'charges', 'payments', 'expenses')


def _now() -> datetime:
    return datetime.now(UTC)


def _marker(root: Path, environment: str) -> Path:
    return Path(root) / 'UserData' / 'State' / f'auto_backup_{environment}.json'


def backup_status(root: Path, environment: str = 'production') -> dict:
    try:
        return json.loads(_marker(root, environment).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def write_backup_status(root: Path, environment: str, data: dict) -> None:
    path = _marker(root, environment)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def check_backup(path: Path, vrk: bytes, db_key: bytes, environment: str) -> dict:
    """Confere de verdade: abre a cópia (cifra + hash), restaura o banco numa pasta temporária,
    roda integrity_check e conta os registros principais."""
    from .backup import _decrypt
    from .db import Database
    header, plain = _decrypt(path, vrk)
    tmp = Path(tempfile.mkdtemp(prefix='ustracker-check-'))
    try:
        with zipfile.ZipFile(io.BytesIO(plain)) as z:
            target = tmp / 'UserData' / environment.capitalize()
            target.mkdir(parents=True)
            (target / 'ustracker.db').write_bytes(z.read('database/ustracker.db'))
        db = Database(tmp, environment, db_key)
        ok = db.one('PRAGMA integrity_check')[0]
        if ok != 'ok':
            raise ValueError(f'banco da cópia com defeito: {ok}')
        return {t: db.one(f'SELECT COUNT(*) FROM {t}')[0] for t in COUNT_TABLES}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def due(root: Path, environment: str, interval: timedelta) -> bool:
    st = backup_status(root, environment)
    try:
        last = datetime.fromisoformat(st['at'])
    except (KeyError, ValueError, TypeError):
        return True
    wait = interval if st.get('verified') else min(interval, RETRY_FAILED)
    return _now() - last >= wait


def alerts(root: Path, cloud: dict | None, environment: str = 'production') -> list[dict]:
    """Avisos para o topo da tela (só administradores)."""
    out = []
    st = backup_status(root, environment)
    if st and st.get('verified') is False:   # 2.7.0: arquivo antigo (antes da 2.6, sem 'verified') não é falha
        out.append({'code': 'backup_failed', 'level': 'error',
                    'message': f"A cópia de segurança automática falhou: {st.get('error') or 'erro'}. O sistema tenta de novo em 1 hora."})
    last_ok = st.get('last_verified_at') or (st.get('at') if 'verified' not in st else None)
    try:
        stale = not last_ok or _now() - datetime.fromisoformat(last_ok) > BACKUP_STALE
    except ValueError:
        stale = True
    if st and stale:
        out.append({'code': 'backup_stale', 'level': 'warn', 'message': 'Última cópia de segurança conferida tem mais de 2 dias.'})
    if cloud and cloud.get('enabled'):
        if cloud.get('conflict'):
            out.append({'code': 'cloud_conflict', 'level': 'error',
                        'message': 'Nuvem em conflito: este computador parou de enviar. Veja Sistema › Nuvem.'})
        since = cloud.get('pending_since')
        if since and _now().timestamp() - float(since) > CLOUD_STALE.total_seconds():
            out.append({'code': 'cloud_stale', 'level': 'warn', 'message': 'Há alterações sem ir para a nuvem há mais de 1 dia (sem internet?).'})
    return out


# ---------------------------------------------------------------- retrato e pacote de suporte
_ERR_HEAD = re.compile(r'^--- (\S+) (\S+) (\S+)')


def recent_errors(root: Path, limit: int = 20) -> list[dict]:
    log = Path(root) / 'UserData' / 'Logs' / 'erros.log'
    try:
        lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    items, cur = [], None
    for line in lines:
        m = _ERR_HEAD.match(line)
        if m:
            cur = {'at': m.group(1), 'route': f'{m.group(2)} {m.group(3)}', 'error': ''}
            items.append(cur)
        elif cur is not None and line and not line.startswith((' ', 'Traceback')):
            cur['error'] = line.split(':', 1)[0][:80]  # só o tipo do erro (a mensagem pode ter dados)
    return items[-limit:][::-1]


def snapshot(root: Path, db, cloud: dict | None, users_active: int) -> dict:
    root = Path(root)
    version = {}
    for base in (root, Path(__file__).resolve().parents[2]):
        try:
            version = json.loads((base / 'VERSION.json').read_text(encoding='utf-8')); break
        except (OSError, ValueError):
            continue
    usage = shutil.disk_usage(root)
    try:
        from .station import list_stations
        stations = [{'name': s.get('name'), 'status': s.get('status'), 'updated_at': s.get('updated_at')}
                    for s in list_stations(root, db)['items']]
    except Exception:
        stations = []
    st = backup_status(root, db.environment)
    backups = sorted((root / 'UserData' / 'Backups').glob(f'UStracker_{db.environment}_*.usbk'))
    return {
        'generated_at': _now().isoformat(),
        'version': version.get('version'), 'schema_version': version.get('schema_version'),
        'cloud': {k: (cloud or {}).get(k) for k in ('enabled', 'generation', 'last_upload_at', 'last_upload_size', 'conflict', 'last_error', 'pending_since', 'running')},
        'backup': {'last_at': st.get('at'), 'verified': st.get('verified'), 'last_verified_at': st.get('last_verified_at'),
                   'error': st.get('error'), 'counts': st.get('counts'), 'files': len(backups),
                   'size_mb': round(sum(p.stat().st_size for p in backups) / 1e6, 1)},
        'disk': {'free_gb': round(usage.free / 1e9, 1), 'total_gb': round(usage.total / 1e9, 1)},
        'errors': recent_errors(root),
        'users_active': users_active,
        'stations': stations,
    }


_PATTERNS = [
    re.compile(r'gh[pousr]_[A-Za-z0-9]{10,}'), re.compile(r'github_pat_[A-Za-z0-9_]+'),
    re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'),
    re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'), re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'),
    re.compile(r'\b[0-9a-fA-F]{24,}\b'), re.compile(r'\b[A-Za-z0-9+/_=-]{32,}\b'), re.compile(r'\d{6,}'),
]


def _personal_words(db) -> list[str]:
    words = set()
    try:
        for row in db.query('SELECT legal_name,trade_name,public_name,email,phone,document,address FROM clients'):
            for value in row:
                if value:
                    words.add(str(value))
                    words.update(w for w in re.split(r'\s+', str(value)) if len(w) >= 4)
    except Exception:
        pass
    for sql in ('SELECT number,normalized_number FROM client_documents', 'SELECT legal_name,trade_name,normalized_document FROM client_companies',
                'SELECT plate FROM vehicles'):
        try:
            for row in db.query(sql):
                words.update(str(v) for v in row if v and len(str(v)) >= 4)
        except Exception:
            pass
    return sorted(words, key=len, reverse=True)


def scrub(text: str, words: list[str]) -> str:
    for w in words:
        text = text.replace(w, '[cliente]')
    for p in _PATTERNS:
        text = p.sub('[oculto]', text)
    return text


def support_package(root: Path, db, cloud: dict | None, users_active: int) -> bytes:
    root = Path(root)
    words = _personal_words(db)
    snap = snapshot(root, db, cloud, users_active)
    snap['cloud']['last_error'] = scrub(str(snap['cloud'].get('last_error') or ''), words) or None
    snap['backup']['error'] = scrub(str(snap['backup'].get('error') or ''), words) or None
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('diagnostico.json', json.dumps(snap, ensure_ascii=False, indent=2))
        log = root / 'UserData' / 'Logs' / 'erros.log'
        if log.exists():
            z.writestr('erros.log', scrub(log.read_text(encoding='utf-8', errors='replace')[-200_000:], words))
        upd = root / 'UserData' / 'Logs' / 'atualizacao.log'
        if upd.exists():
            z.writestr('atualizacao.log', scrub(upd.read_text(encoding='utf-8', errors='replace')[-50_000:], words))
    return mem.getvalue()
