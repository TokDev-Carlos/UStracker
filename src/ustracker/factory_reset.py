"""G-02 — zerar tudo uma vez (entrega oficial / Release 2).

Pedido interno (não aparece na tela): ``UserData/State/factory-reset.json``. É executado no próximo login de um
Administrador no ambiente Real, porque só ele abre as chaves dos dois bancos.

Apaga: dados do Real (clientes, frotas, planos, financeiro, Lixeira, fotos e anexos), o ambiente Teste inteiro,
usuários não administradores e pacotes próprios. Mantém: administradores, configurações da empresa (nome, marca,
chave da placa, identificador da nuvem) e a ligação com a nuvem. Na nuvem: o próximo envio leva o banco vazio,
apaga fotos/anexos e remove os pontos de restauração antigos.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

MARKER = ('UserData', 'State', 'factory-reset.json')
UTC = timezone.utc


def _marker(root) -> Path:
    return Path(root).joinpath(*MARKER)


def request_reset(root) -> Path:
    path = _marker(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'requested_at': datetime.now(UTC).isoformat(), 'scope': 'all'}), encoding='utf-8')
    return path


def reset_pending(root) -> bool:
    return _marker(root).exists()


def _drop_files(root: Path, environment: str) -> None:
    for folder in ('Media', 'Attachments'):
        shutil.rmtree(root / 'UserData' / folder / environment, ignore_errors=True)
    view = root / 'UserData' / 'Public' / environment / 'view.json'
    view.unlink(missing_ok=True)


def _drop_db(root: Path, environment: str) -> None:
    folder = root / 'UserData' / environment.capitalize()
    for suffix in ('', '-wal', '-shm', '-journal'):
        (folder / f'ustracker.db{suffix}').unlink(missing_ok=True)


def run_if_requested(root, auth, session, cloud=None) -> dict | None:
    """Run the pending reset with an Administrator's Production session. None when nothing ran."""
    from .db import Database
    root = Path(root)
    if not reset_pending(root) or not getattr(session, 'is_admin', False) or session.environment != 'production':
        return None
    gate = getattr(cloud, 'db_gate', None)
    if gate is not None:
        gate.acquire()
    try:
        old = Database(root, 'production', session.db_key)
        settings = [tuple(r) for r in old.query('SELECT key,value,updated_at FROM settings')]
        clients = old.one('SELECT COUNT(*) FROM clients')[0]
        del old
        _drop_db(root, 'production'); _drop_files(root, 'production')
        _drop_db(root, 'test'); _drop_files(root, 'test')
        fresh = Database(root, 'production', session.db_key)
        with fresh.transaction() as con:
            con.executemany('INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,?)', settings)
        vault = auth._read_vault(session.vrk)
        from .auth import b64d
        Database(root, 'test', b64d(vault['test']['db_key']))
        removed = auth.remove_all_users(session)
        if cloud is not None and cloud.state.get('url'):
            cloud.state.set(wipe_cloud=True, uploaded_blobs=[], pending_delete=[],
                            compact_before=datetime.now(UTC).isoformat())
            cloud.mark_dirty()
        _marker(root).unlink(missing_ok=True)
        return {'clients_removed': clients, **{f'{k}_removed': v for k, v in removed.items()}}
    finally:
        if gate is not None:
            gate.release()
