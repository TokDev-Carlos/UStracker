"""C-02/C-03 — UStracker Cloud (Google Drive via Apps Script), client side.

The local SQLCipher database stays the source of truth (fast, ACID, portable). The cloud is an
encrypted, versioned vault:

* **db snapshots** — ``.usbk`` without photos (already AES-GCM with a key derived from the VRK),
  uploaded ~2 minutes after the last change and when the system closes;
* **blobs** — every encrypted photo/attachment file, uploaded once, by name;
* **auth bundle** — the access vault (admins), sealed with a key derived from the connection code.

Nothing readable ever leaves the computer. Deletion in the cloud happens only when an item
leaves the 14-day Lixeira inside the system (``delete_blobs`` + ``compact``).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PART_SIZE = 4 * 1024 * 1024
DEBOUNCE_SECONDS = 120
# S-02/S-03 — vários Servidores no mesmo banco: vez de gravar automática
LEASE_TTL = 120          # a vez vence sozinha se o Servidor cair
HOLD_SECONDS = 4         # sem alteração por 4 s → solta a vez (2.6: era 20 s; o outro computador esperava ~21 s)
TURN_DEBOUNCE = 2        # com a vez na mão, envia 2 s após a última alteração
PULL_EVERY = 25          # sem a vez, confere a cada 25 s se outro Servidor gravou
PLACA_EVERY = 6 * 3600   # confere a placa de direção a cada 6 h (e ao entrar)
TURN_WAIT = 45           # espera máxima pela vez ao salvar
PROTOCOL = 1
# 2.5.0: "vida" da empresa na nuvem. A 1ª ativação 2.5 zera a nuvem antiga (reset_company) e grava esta época;
# a nuvem só aceita gravação da mesma época (versões antigas não sobem dados velhos).
CLOUD_EPOCH = 25
AUTH_AAD = b'UStracker/cloud-auth/v1'
UTC = timezone.utc


class CloudError(Exception):
    def __init__(self, code: str, detail: str = ''):
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail


def _hkdf(material: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b'UStracker-cloud', info=info).derive(material)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ----------------------------------------------------------------------------- transport
_NOT_PUBLIC = ('o Google pediu login em vez de responder. No Apps Script: Implantar → Gerenciar implantações → editar (lápis) → '
               '"Executar como: Eu" e "Quem pode acessar: Qualquer pessoa" → Implantar, e use a URL que termina em /exec')


def _html_text(raw: bytes) -> str:
    import re
    text = raw.decode('utf-8', 'replace')
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
    return ' '.join(re.sub(r'<[^>]+>', ' ', text).split())[:200]


def _not_json_error(raw: bytes, final_url: str = '') -> 'CloudError':
    low = raw.decode('utf-8', 'replace').lower()
    if 'accounts.google.com' in (final_url or '').lower() or 'servicelogin' in low or 'accounts.google.com' in low:
        return CloudError('NOT_PUBLIC', _NOT_PUBLIC)
    if 'script function not found' in low or 'função de script não encontrada' in low or 'dopost' in low:
        return CloudError('SCRIPT_NOT_READY', 'o script publicado não tem o código do UStracker. Cole todo o UStracker-Cloud-Code.gs, salve e publique uma NOVA versão (Implantar → Gerenciar implantações → editar → Nova versão)')
    if 'authorization is required' in low or 'autorização' in low or 'authorisation' in low:
        return CloudError('SCRIPT_NOT_AUTHORIZED', 'falta autorizar o script: no editor, escolha a função "instalar", clique em Executar e permita o acesso')
    hint = _html_text(raw)
    return CloudError('BAD_RESPONSE', 'a URL respondeu, mas não como o UStracker Cloud. Confira se é a URL /exec do App da Web e se a implantação está atualizada' + (f' (resposta: "{hint}")' if hint else ''))


def _http_error(status: int, raw: bytes) -> 'CloudError':
    if status in (401, 403):
        return CloudError('NOT_PUBLIC', _NOT_PUBLIC)
    if status == 404:
        return CloudError('NOT_FOUND', 'URL não encontrada (404). A implantação pode ter sido arquivada ou a URL foi copiada incompleta; copie de novo a URL /exec')
    if status == 429:
        return CloudError('QUOTA', 'o Google limitou o uso temporariamente (cota). Tente de novo mais tarde')
    err = _not_json_error(raw)
    if err.code in ('NOT_PUBLIC', 'SCRIPT_NOT_READY', 'SCRIPT_NOT_AUTHORIZED'):
        return err
    return CloudError('HTTP_' + str(status), f'o Google respondeu com erro {status}. Tente de novo; se persistir, publique uma nova versão do script')


def _network_error(exc: Exception) -> 'CloudError':
    import ssl
    reason = getattr(exc, 'reason', exc)
    text = str(reason)
    if isinstance(reason, ssl.SSLError) or 'CERTIFICATE' in text.upper() or 'SSL' in text.upper():
        return CloudError('TLS', 'conexão segura recusada (certificado). Antivírus ou proxy da rede pode estar interceptando o HTTPS; libere o UStracker ou teste em outra rede. Detalhe: ' + text[:160])
    if isinstance(reason, (TimeoutError,)) or 'timed out' in text.lower():
        return CloudError('TIMEOUT', 'o Google demorou demais para responder. Verifique a internet e tente de novo')
    if 'getaddrinfo' in text or 'Name or service not known' in text or 'nodename' in text or '11001' in text:
        return CloudError('NETWORK', 'sem internet ou DNS: não foi possível encontrar script.google.com')
    return CloudError('NETWORK', 'não foi possível falar com o Google (internet, firewall ou proxy). Detalhe: ' + text[:160])


class CloudClient:
    def __init__(self, url: str, secret: str, *, timeout: float = 120.0, opener=None, epoch: int | None = None):
        url = str(url or '').strip()
        if not url.startswith('https://') and not url.startswith('http://127.0.0.1') and not url.startswith('http://localhost'):
            raise CloudError('BAD_URL', 'a URL do App da Web deve começar com https://')
        if url.startswith('https://'):
            from urllib.parse import urlsplit
            if '/macros/' not in url or (urlsplit(url).hostname or '').lower() != 'script.google.com':
                raise CloudError('BAD_URL', 'cole a URL do App da Web (começa com https://script.google.com/macros/s/ e termina em /exec), não a URL do editor do script')
            if url.rstrip('/').endswith('/dev'):
                raise CloudError('BAD_URL', 'esta é a URL de teste (/dev), que só funciona com login. Use Implantar → Gerenciar implantações e copie a URL que termina em /exec')
            url = url.split('?')[0].split('#')[0].rstrip('/')
            if not url.endswith('/exec'):
                raise CloudError('BAD_URL', 'a URL do App da Web deve terminar em /exec')
        secret = ''.join(str(secret or '').split())
        if len(secret) < 16:
            raise CloudError('BAD_SECRET', 'código de conexão incompleto: copie as 48 letras/números do Registro de execução')
        self.url = url
        self.secret = secret.strip()
        self.timeout = timeout
        self.opener = opener or urllib.request.build_opener()
        self.epoch = CLOUD_EPOCH if epoch is None else int(epoch)

    def call(self, action: str, body: dict | None = None, *, retries: int = 3, check_epoch: bool = True) -> dict:
        out = self._call(action, body, retries=retries)
        if action == 'ping' and check_epoch:
            cloud = int(out.get('epoch') or 0)
            if cloud and cloud != self.epoch:
                raise CloudError('EPOCH', f'a nuvem está na época {cloud} e este computador na {self.epoch}: atualize e ative de novo')
        return out

    def _call(self, action: str, body: dict | None = None, *, retries: int = 3) -> dict:
        last: Exception | None = None
        if self.epoch and (body is None or isinstance(body, dict)):
            body = {**(body or {}), 'epoch': self.epoch}
        for attempt in range(retries):
            body_text = json.dumps(body or {}, separators=(',', ':'))
            ts = int(time.time() * 1000)
            nonce = secrets.token_hex(16)
            sig = hmac.new(self.secret.encode(), f'{action}\n{ts}\n{nonce}\n{body_text}'.encode(), hashlib.sha256).hexdigest()
            payload = json.dumps({'v': PROTOCOL, 'action': action, 'ts': ts, 'nonce': nonce, 'body': body_text, 'sig': sig}).encode()
            req = urllib.request.Request(self.url, data=payload, method='POST', headers={'Content-Type': 'text/plain;charset=utf-8'})
            final_url = ''
            try:
                with self.opener.open(req, timeout=self.timeout) as resp:  # Apps Script answers 302 -> GET (handled by urllib)
                    raw = resp.read()
                    final_url = resp.geturl() or ''
            except urllib.error.HTTPError as exc:
                raise _http_error(exc.code, exc.read()[:4000] if exc.fp else b'') from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = _network_error(exc)
                time.sleep(min(2 ** attempt, 8) if attempt + 1 < retries else 0)
                continue
            try:
                out = json.loads(raw.decode('utf-8'))
                if not isinstance(out, dict):
                    raise ValueError('not an object')
            except ValueError:
                raise _not_json_error(raw[:4000], final_url)
            if not out.get('ok'):
                raise CloudError(out.get('error') or 'SERVER_ERROR', out.get('detail') or '')
            return out
        raise last or CloudError('NETWORK', 'sem resposta')

    # -- snapshots -------------------------------------------------------------
    def upload(self, data: bytes, meta: dict) -> dict:
        upload_id = secrets.token_hex(16)
        parts = []
        for index, offset in enumerate(range(0, max(len(data), 1), PART_SIZE)):
            chunk = data[offset:offset + PART_SIZE]
            self.call('put_part', {'upload_id': upload_id, 'index': index, 'data': base64.b64encode(chunk).decode(), 'sha256': _sha(chunk)})
            parts.append({'index': index, 'sha256': _sha(chunk), 'size': len(chunk)})
        return self.call('commit', {'upload_id': upload_id, 'parts': parts, 'total_sha256': _sha(data), 'size': len(data), **meta})['snapshot']

    def download(self, kind: str, snapshot_id: str = 'head') -> tuple[dict, bytes]:
        manifest = self.call('get_manifest', {'kind': kind, 'id': snapshot_id})['manifest']
        chunks = []
        for part in sorted(manifest['parts'], key=lambda p: int(p['index'])):
            got = self.call('get_part', {'kind': kind, 'id': manifest['id'], 'index': part['index']})
            chunk = base64.b64decode(got['data'])
            if _sha(chunk) != part['sha256']:
                raise CloudError('HASH', f"parte {part['index']} corrompida")
            chunks.append(chunk)
        data = b''.join(chunks)
        if _sha(data) != manifest['total_sha256']:
            raise CloudError('HASH', 'ponto de restauração corrompido')
        return manifest, data

    # -- blobs -----------------------------------------------------------------
    def put_blob(self, name: str, data: bytes) -> dict:
        return self.call('put_blob', {'name': name, 'data': base64.b64encode(data).decode(), 'sha256': _sha(data)})

    def get_blob(self, name: str) -> bytes:
        got = self.call('get_blob', {'name': name})
        data = base64.b64decode(got['data'])
        if _sha(data) != got['sha256']:
            raise CloudError('HASH', name)
        return data


# ----------------------------------------------------------------------------- auth bundle
def seal_auth(root: Path, secret: str) -> bytes:
    auth = Path(root) / 'UserData' / 'Auth'
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('auth.db', 'vault.json'):
            if (auth / name).exists():
                z.write(auth / name, arcname=name)
    nonce = os.urandom(12)
    return nonce + AESGCM(_hkdf(secret.encode(), AUTH_AAD)).encrypt(nonce, mem.getvalue(), AUTH_AAD)


def open_auth(blob: bytes, secret: str) -> dict[str, bytes]:
    try:
        plain = AESGCM(_hkdf(secret.encode(), AUTH_AAD)).decrypt(blob[:12], blob[12:], AUTH_AAD)
    except Exception as exc:
        raise CloudError('AUTH_BUNDLE', 'código de conexão não confere com estes dados') from exc
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        return {n: z.read(n) for n in z.namelist() if n in ('auth.db', 'vault.json')}


def _auth_fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    for name in ('auth.db', 'vault.json'):
        p = Path(root) / 'UserData' / 'Auth' / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


# ----------------------------------------------------------------------------- local state
def blob_files(root: Path, environment: str = 'production') -> dict[str, Path]:
    """Cloud name -> local file. Photos are 'm.<file>', attachments 'a.<file>'."""
    out = {}
    for prefix, folder in (('m', 'Media'), ('a', 'Attachments')):
        base = Path(root) / 'UserData' / folder / environment
        if base.exists():
            for p in base.iterdir():
                if p.is_file() and p.name.endswith('.aead'):
                    out[f'{prefix}.{p.name}'] = p
    return out


def blob_target(root: Path, name: str, environment: str = 'production') -> Path:
    prefix, _, filename = name.partition('.')
    folder = {'m': 'Media', 'a': 'Attachments'}.get(prefix)
    if not folder or not filename or '/' in filename or '\\' in filename or filename.startswith('.'):
        raise CloudError('BAD_NAME', name)
    return Path(root) / 'UserData' / folder / environment / filename


class CloudState:
    """``UserData/State/cloud.json``; the connection code is stored sealed with a VRK-derived key."""

    def __init__(self, root: Path):
        self.path = Path(root) / 'UserData' / 'State' / 'cloud.json'
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding='utf-8'))
            except ValueError:
                self.data = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding='utf-8')
        tmp.replace(self.path)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, **kw):
        self.data.update(kw)
        self.save()

    @staticmethod
    def _key(vrk: bytes) -> bytes:
        return _hkdf(vrk, b'UStracker/cloud-secret/v1')

    def seal(self, vrk: bytes, text: str) -> str:
        nonce = os.urandom(12)
        return base64.b64encode(nonce + AESGCM(self._key(vrk)).encrypt(nonce, text.encode(), b'cloud-secret')).decode()

    def unseal(self, vrk: bytes, raw: str) -> str:
        blob = base64.b64decode(raw)
        return AESGCM(self._key(vrk)).decrypt(blob[:12], blob[12:], b'cloud-secret').decode()

    def store_secret(self, vrk: bytes, secret: str):
        nonce = os.urandom(12)
        sealed = nonce + AESGCM(self._key(vrk)).encrypt(nonce, secret.encode(), b'cloud-secret')
        self.set(secret=base64.b64encode(sealed).decode())

    def secret(self, vrk: bytes) -> str | None:
        raw = self.get('secret')
        if not raw:
            return None
        blob = base64.b64decode(raw)
        return AESGCM(self._key(vrk)).decrypt(blob[:12], blob[12:], b'cloud-secret').decode()


# ----------------------------------------------------------------------------- sync engine
class CloudSync:
    """Background sync for the production dataset. All cloud I/O is serialized by one lock."""

    def __init__(self, root: Path, auth, *, debounce: float = DEBOUNCE_SECONDS, client_factory=CloudClient):
        self.root = Path(root)
        self.auth = auth
        self.debounce = debounce
        self.client_factory = client_factory
        self.state = CloudState(self.root)
        self.lock = threading.RLock()
        self.token: str | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.status = {'running': False, 'last_error': None, 'waiting_for': None, 'offline': False}
        self.pending_secret: str | None = None  # after a cloud restore, until the first login
        self.turn_lock = threading.RLock()
        self.db_gate = threading.RLock()     # pull (replace the local database) vs. writes
        self.lease_until = 0.0
        self.last_turn_use = 0.0
        self.last_pull = 0.0
        self.last_purge = 0.0
        self.on_tick = None                  # 2.6: tarefas diárias da sessão (cópia de segurança conferida)
        self.data_version = 0                # bumps when another Servidor's data arrived
        self.last_placa = 0.0

    # -- session handling -------------------------------------------------------
    def attach(self, session) -> None:
        if session.environment != 'production':
            return
        self.token = session.token

    def detach(self, token: str | None = None) -> None:
        if token is None or token == self.token:
            self.token = None

    def _session(self):
        return self.auth.get_session(self.token) if self.token else None

    def enabled(self) -> bool:
        return bool(self.state.get('enabled') and self.state.get('url') and self.state.get('secret'))

    def client(self, vrk: bytes) -> CloudClient:
        return self.client_factory(self.state.get('url'), self.state.secret(vrk))

    def mark_dirty(self) -> None:
        if self.state.get('enabled'):
            if not self.state.get('dirty_since'):
                self.state.set(dirty_since=time.time())
            self.state.set(last_change=time.time())

    # -- background loop --------------------------------------------------------
    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, name='ustracker-cloud', daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _loop(self) -> None:
        while not self.stop_event.wait(3):
            try:
                session = self._session()
                if session:
                    self.tick(session)
            except Exception as exc:  # never kill the loop
                self.status['last_error'] = str(exc)

    def tick(self, session) -> None:
        """One pass of the background loop (3 s): purge, placa, send pending changes, free the turn, pull."""
        if self.on_tick:
            try:
                self.on_tick(session)
            except Exception as exc:
                self.status['tick_error'] = str(exc)[:200]
        if time.time() - self.last_purge > 3600:
            self.last_purge = time.time()
            self.purge_trash(session)
        if time.time() - self.last_placa >= PLACA_EVERY:
            self.last_placa = time.time()
            try:
                self.check_placa(session)
            except Exception as exc:
                self.status['placa_error'] = str(exc)[:200]
        if not self.enabled():
            return
        if self.state.get('bank_switch'):
            self.pull(session)
        if self.state.get('conflict'):
            # 2.6: em conflito este computador para de enviar sozinho (a tela pede a decisão) e não segura a vez
            if self.lease_until > 0:
                self._drop_turn(session)
            return
        holding = self.lease_until > time.time()
        idle = time.time() - float(self.state.get('last_change') or 0)
        if self.state.get('dirty_since') and idle >= min(TURN_DEBOUNCE, self.debounce):
            if not holding:
                try:
                    self.acquire_turn(session, wait=0)
                except CloudError:
                    return  # another Servidor is saving; try again on the next tick
            try:
                self.sync_now(session)
            except CloudError as exc:
                if exc.code == 'CONFLICT':
                    self._drop_turn(session)
                raise
            holding = self.lease_until > time.time()   # enviou: se já está parado, solta a vez agora (o outro não espera mais um ciclo)
        if holding and not self.state.get('dirty_since') and time.time() - self.last_turn_use >= HOLD_SECONDS:
            self.release_turn(session)
        elif not holding and not self.state.get('dirty_since') and time.time() - self.last_pull >= PULL_EVERY:
            self.pull(session)

    def _drop_turn(self, session) -> None:
        """Solta a vez mesmo com alterações pendentes (conflito: elas ficam aqui até a decisão na tela)."""
        with self.turn_lock:
            try:
                self.client(session.vrk).call('lease', {'op': 'release', 'holder': self._ident()['id']}, retries=1)
            except Exception:
                pass
            finally:
                self.lease_until = 0.0

    def flush(self, timeout: float = 60.0) -> bool:
        """Called when the system closes: upload pending changes right away, then free the turn."""
        session = self._session()
        if not (session and self.enabled()):
            return False
        if not self.state.get('dirty_since'):
            try:
                self.release_turn(session)
            except Exception:
                pass
            return False
        done = threading.Event()
        def run():
            try:
                self.sync_now(session)
                self.release_turn(session)
            except Exception:
                pass
            finally:
                done.set()
        threading.Thread(target=run, daemon=True).start()
        return done.wait(timeout)

    # -- lixeira -----------------------------------------------------------------
    def purge_trash(self, session, at: datetime | None = None) -> dict:
        from .db import Database
        from .trash import purge_due
        db = Database(self.root, 'production', session.db_key)
        out = purge_due(self.root, db, session.slot, at=at)
        from .retention import run as retention_run  # 2.6 LGPD: prazos do cliente excluído (14 dias / 5 anos)
        kept = retention_run(self.root, db, session.slot, at=at)
        if kept['files'] or kept['removed'] or kept['reduced'] or kept['anonymized']:
            names = {('m.' if f.startswith('m:') else 'a.') + f[2:] for f in kept['files']}
            self.state.set(pending_delete=sorted(set(self.state.get('pending_delete', [])) | names))
            self.mark_dirty()
        out['retention'] = {k: kept[k] for k in ('removed', 'reduced', 'anonymized')}
        if out['purged']:
            pending = set(self.state.get('pending_delete', [])) | {f'm.{n}' for n in out['erased_files']}
            self.state.set(pending_delete=sorted(pending), compact_before=(at or datetime.now(UTC)).isoformat())
            self.mark_dirty()
        return out

    # -- the sync itself ----------------------------------------------------------
    def dataset_id(self, db) -> str:
        row = db.one("SELECT value FROM settings WHERE key='cloud_dataset_id'")
        if row:
            return row[0]
        value = secrets.token_hex(16)
        with db.transaction() as con:
            con.execute("INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES('cloud_dataset_id',?,?)", (value, _now_iso()))
        return db.one("SELECT value FROM settings WHERE key='cloud_dataset_id'")[0]

    def sync_now(self, session, *, force: bool = False, turn_wait: float = TURN_WAIT) -> dict:
        from .backup import create_backup
        from .db import Database
        from .station import local_identity
        if self.enabled() and not force and self.lease_until <= time.time():
            # 2.6: só envia com a vez (antes "Enviar agora" subia por cima de quem estava gravando → CONFLITO no outro)
            got = self.acquire_turn(session, wait=turn_wait)
            if got and got.get('offline'):
                raise CloudError('NETWORK', self.status.get('last_error') or 'sem conexão com a nuvem')
        with self.lock:
            if not self.enabled():
                raise CloudError('DISABLED', 'nuvem não conectada')
            self.status['running'] = True
            try:
                client = self.client(session.vrk)
                db = Database(self.root, 'production', session.db_key)
                from .station import ensure_station
                ensure_station(self.root, db)
                dataset = self.dataset_id(db)
                started = time.time()
                change_marker = self.state.get('last_change')
                # 1) photos/attachments, once each
                known = set(self.state.get('uploaded_blobs', []))
                local = blob_files(self.root)
                sent = 0
                for name, path in sorted(local.items()):
                    if name in known:
                        continue
                    client.put_blob(name, path.read_bytes())
                    known.add(name); sent += 1
                    if sent % 20 == 0:
                        self.state.set(uploaded_blobs=sorted(known))
                self.state.set(uploaded_blobs=sorted(known))
                # 2) deletions requested by the Lixeira (14 days are over); G-02 zerar tudo: every remote file not local
                pending = list(self.state.get('pending_delete', []))
                if self.state.get('wipe_cloud'):
                    pending = sorted(set(pending) | (set(client.call('list_blobs', {}).get('names', [])) - set(local)))
                if pending:
                    client.call('delete_blobs', {'names': pending})
                    self.state.set(pending_delete=[], uploaded_blobs=sorted(known - set(pending)))
                if self.state.get('wipe_cloud'):
                    self.state.set(wipe_cloud=None)
                # 3) access vault when it changed
                fp = _auth_fingerprint(self.root)
                if fp != self.state.get('auth_fingerprint'):
                    auth_rec = client.upload(seal_auth(self.root, self.state.secret(session.vrk)), {'kind': 'auth', 'dataset_id': dataset, 'force': force})
                    self.state.set(auth_fingerprint=fp, auth_head_id=(auth_rec or {}).get('id'))
                # 4) database snapshot
                generation = int(self.state.get('generation') or 0)
                tmp = Path(tempfile.mkdtemp(prefix='ustracker-cloud-', dir=str(self.root / 'UserData')))
                try:
                    snap = create_backup(self.root, db, session.vrk, include_files=False, out_dir=tmp)
                    data = snap.read_bytes()
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                counts = {t: db.one(f'SELECT COUNT(*) FROM {t}')[0] for t in ('clients', 'vehicles', 'subscriptions', 'payments', 'expenses')}
                try:
                    record = client.upload(data, {'kind': 'db', 'environment': 'production', 'dataset_id': dataset,
                                                  'generation': generation + 1, 'base_generation': generation,
                                                  'station_id': local_identity(self.root)['id'], 'created_at': _now_iso(),
                                                  'force': force, 'meta': {'counts': counts, 'blobs': len(known)}})
                except CloudError as exc:
                    if exc.code == 'CONFLICT':
                        self.state.set(conflict=exc.detail)
                    raise
                # 5) compaction after a Lixeira purge: older points still held the purged items
                if self.state.get('compact_before'):
                    client.call('compact', {'before': self.state.get('compact_before')})
                    self.state.set(compact_before=None)
                self._mirror(session, data, dataset, int(record['generation']), force)
                update = dict(generation=int(record['generation']), last_upload_at=_now_iso(), last_upload_size=len(data),
                              conflict=None, last_error=None, dataset_id=dataset)
                if self.state.get('last_change') == change_marker:
                    update['dirty_since'] = None
                self.state.set(**update)
                self.status['last_error'] = None
                return {'generation': record['generation'], 'blobs_sent': sent, 'size': len(data), 'seconds': round(time.time() - started, 1)}
            except Exception as exc:
                self.status['last_error'] = str(exc)
                self.state.set(last_error=str(exc)[:300], last_error_at=_now_iso())
                raise
            finally:
                self.status['running'] = False

    # -- S-02/S-03 vários Servidores ----------------------------------------------
    def _ident(self) -> dict:
        from .station import local_identity
        ident = local_identity(self.root)
        return {'id': ident['id'], 'name': ident.get('server_name') or ident.get('name') or 'Servidor'}

    def acquire_turn(self, session, wait: float = TURN_WAIT) -> dict | None:
        """Called before every change. Takes the turn (waiting if another Servidor is saving),
        brings the newest data first, then lets the change happen. Offline: works locally and
        the conflict check at upload time protects the cloud."""
        if session.environment != 'production' or not self.enabled():
            return None
        with self.turn_lock:
            now = time.time()
            self.last_turn_use = now
            if self.lease_until - now > 30:
                return {'held': True}
            ident = self._ident()
            try:
                client = self.client(session.vrk)
            except Exception:
                return {'offline': True}
            deadline = now + wait
            while True:
                try:
                    out = client.call('lease', {'op': 'acquire', 'holder': ident['id'], 'name': ident['name'], 'ttl': LEASE_TTL}, retries=1)
                except CloudError as exc:
                    self.status.update(offline=True, waiting_for=None, last_error=f'{exc.code}: {exc.detail}'[:300],
                                       script_outdated=(exc.code == 'UNKNOWN_ACTION'))
                    return {'offline': True}
                if out.get('granted'):
                    break
                self.status['waiting_for'] = out.get('holder_name') or 'outro Servidor'
                if time.time() >= deadline:
                    self.status['waiting_for'] = None
                    raise CloudError('BUSY', f"{out.get('holder_name') or 'Outro Servidor'} está salvando agora. Tente de novo em alguns segundos.")
                time.sleep(1)
            self.status.update(offline=False, waiting_for=None, script_outdated=False)
            self.lease_until = time.time() + LEASE_TTL - 10
            self.last_turn_use = time.time()
            self._pull_from(session, client, out.get('head'), out.get('auth_head'))
            return {'granted': True}

    def release_turn(self, session) -> None:
        if self.lease_until <= 0 or not self.enabled():
            return
        with self.turn_lock:
            if self.state.get('dirty_since'):
                return
            try:
                self.client(session.vrk).call('lease', {'op': 'release', 'holder': self._ident()['id']}, retries=1)
            finally:
                self.lease_until = 0.0

    def pull(self, session) -> bool:
        """Without the turn: bring what other Servidores saved (screens refresh by data_version)."""
        if session.environment != 'production' or not self.enabled():
            return False
        self.last_pull = time.time()
        with self.turn_lock:
            client = self.client(session.vrk)
            ping = client.call('ping', {}, retries=1)
            self.status['offline'] = False
            return self._pull_from(session, client, ping.get('head'), ping.get('auth_head'))

    def _pull_from(self, session, client, head: dict | None, auth_head: dict | None) -> bool:
        from .backup import restore_backup, verify_backup
        from .db import Database
        changed = False
        if auth_head and auth_head.get('id') and auth_head.get('id') != self.state.get('auth_head_id'):
            _, blob = client.download('auth', auth_head['id'])
            files = open_auth(blob, self.state.secret(session.vrk))
            auth_dir = self.root / 'UserData' / 'Auth'
            if 'auth.db' in files:
                # merge, never replace: local users/packages not sent yet survive; the merged result goes up next sync
                tmp = auth_dir / 'auth.cloud.db'
                tmp.write_bytes(files['auth.db'])
                try:
                    self.auth.merge_from(tmp)
                finally:
                    tmp.unlink(missing_ok=True)
            if 'vault.json' in files and not (auth_dir / 'vault.json').exists():
                (auth_dir / 'vault.json').write_bytes(files['vault.json'])
            self.state.set(auth_head_id=auth_head['id'])
            changed = True
        local_gen = int(self.state.get('generation') or 0)
        if self.state.get('bank_switch'):
            # S-07: Banco 1 changed. Empty new bank → this Servidor fills it; otherwise take what is there.
            if not head:
                self.state.set(bank_switch=False, generation=0)
                self.mark_dirty()
                return changed
            if int(head.get('generation') or 0) == local_gen:
                self.state.set(bank_switch=False)           # promoted mirror already in step
            elif self.state.get('dirty_since'):
                return changed                              # send local changes first (conflict check protects)
            else:
                local_gen = -1
                self.state.set(bank_switch=False)
        if head and int(head.get('generation') or 0) > local_gen:
            db = Database(self.root, 'production', session.db_key)
            if head.get('dataset_id') and head.get('dataset_id') != self.dataset_id(db):
                return changed
            if self.state.get('dirty_since'):
                return changed  # local changes not sent yet: the upload will report the conflict
            manifest, data = client.download('db', 'head')
            tmp = Path(tempfile.mkdtemp(prefix='ustracker-pull-', dir=str(self.root / 'UserData')))
            try:
                path = tmp / 'head.usbk'
                path.write_bytes(data)
                verify_backup(path, session.vrk)
                with self.db_gate:
                    restore_backup(self.root, db, session.vrk, path)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            names = client.call('list_blobs', {}).get('names', [])
            for name in names:
                target = blob_target(self.root, name)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    part = target.with_suffix(target.suffix + '.download')
                    part.write_bytes(client.get_blob(name))
                    part.replace(target)
            self.state.set(generation=int(manifest['generation']), uploaded_blobs=sorted(set(names) | set(self.state.get('uploaded_blobs', []))))
            changed = True
        if changed:
            self.data_version += 1
        return changed

    # -- S-05..S-07 placa de direção ---------------------------------------------
    def master(self, session, db, *, create: bool = False) -> dict | None:
        """Master key of the placa: sealed with the VRK inside the shared database."""
        from .placa import KEY_SETTING, new_master
        row = db.one('SELECT value FROM settings WHERE key=?', (KEY_SETTING,))
        if row:
            return json.loads(self.state.unseal(session.vrk, row[0]))
        if not create:
            return None
        master = new_master()
        with db.transaction() as con:
            con.execute('INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,?)',
                        (KEY_SETTING, self.state.seal(session.vrk, json.dumps(master)), _now_iso()))
        self.mark_dirty()
        return master

    def apply_banks(self, session, banks: list[dict], seq: int | None = None) -> dict:
        """Banco 1 = principal; the rest are mirrors. Switching Banco 1 is automatic and safe."""
        primary = banks[0]
        current_url = self.state.get('url')
        current_secret = self.state.secret(session.vrk) if self.state.get('secret') else None
        switched = bool(current_url) and (primary['url'] != current_url or primary['key'] != current_secret)
        mirrors = [{'url': b['url'], 'secret': self.state.seal(session.vrk, b['key'])} for b in banks[1:]]
        update = dict(enabled=True, url=primary['url'], mirrors=mirrors)
        if seq is not None:
            update['placa_seq'] = int(seq)
        if switched or not current_url:
            update.update(uploaded_blobs=[], auth_fingerprint=None, auth_head_id=None, conflict=None, bank_switch=True,
                          mirror_state={})
            self.lease_until = 0.0
        self.state.set(**update)
        self.state.store_secret(session.vrk, primary['key'])
        if switched or not current_url:
            self.last_pull = 0.0
        return {'primary': primary['url'], 'mirrors': len(mirrors), 'switched': switched}

    COMPANY_KEY_SETTING = 'placa_company_key'

    def company_key(self, session, db=None) -> str | None:
        """Company key (opens the placa): master in the database > activation copy > legacy Trust file."""
        from .db import Database
        from .placa import load_bootstrap
        db = db or Database(self.root, 'production', session.db_key)
        try:
            master = self.master(session, db)
            if master and master.get('company_key'):
                return master['company_key']
            row = db.one('SELECT value FROM settings WHERE key=?', (self.COMPANY_KEY_SETTING,))
            if row:
                return self.state.unseal(session.vrk, row[0])
        except Exception:
            pass
        return (load_bootstrap(self.root) or {}).get('company_key')

    def keep_company_key(self, session, company_key: str, db=None) -> None:
        """Activation: store the company key sealed with the VRK (travels with the cloud copy)."""
        from .db import Database
        db = db or Database(self.root, 'production', session.db_key)
        if db.one('SELECT 1 FROM settings WHERE key=?', (self.COMPANY_KEY_SETTING,)):
            return
        master = self.master(session, db)
        if master and master.get('company_key') == company_key:
            return
        with db.transaction() as con:
            con.execute('INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,?)',
                        (self.COMPANY_KEY_SETTING, self.state.seal(session.vrk, company_key), _now_iso()))
        self.mark_dirty()

    def check_placa(self, session, *, force: bool = False) -> dict:
        from .placa import fetch_placa, load_bootstrap, read_placa, strip_company_key
        boot = load_bootstrap(self.root)
        if not boot or not boot.get('placa_url'):
            return {'configured': False}
        key = self.company_key(session)
        placa = read_placa(fetch_placa(boot['placa_url']), boot, key)
        if boot.get('company_key'):  # 2.2.0: the plain copy leaves Trust/ once the database holds it
            self.keep_company_key(session, boot['company_key'])
            strip_company_key(self.root)
        self.status['placa_error'] = None
        if not force and placa['seq'] <= int(self.state.get('placa_seq') or 0) and self.enabled():
            return {'configured': True, 'seq': placa['seq'], 'changed': False}
        out = self.apply_banks(session, placa['banks'], placa['seq'])
        return {'configured': True, 'seq': placa['seq'], 'changed': True, **out}

    def _mirror(self, session, data: bytes, dataset: str, generation: int, force: bool) -> None:
        """Banco 2+: same snapshot, photos and access vault. Never blocks the main upload."""
        mirrors = self.state.get('mirrors') or []
        if not mirrors:
            return
        states = dict(self.state.get('mirror_state') or {})
        for m in mirrors:
            st = dict(states.get(m['url']) or {})
            try:
                client = self.client_factory(m['url'], self.state.unseal(session.vrk, m['secret']))
                sent = set(st.get('blobs') or [])
                if not st.get('listed'):
                    sent |= set(client.call('list_blobs', {}).get('names', []))
                    st['listed'] = True
                for name, path in sorted(blob_files(self.root).items()):
                    if name not in sent:
                        client.put_blob(name, path.read_bytes()); sent.add(name)
                fp = _auth_fingerprint(self.root)
                if fp != st.get('auth_fingerprint'):
                    client.upload(seal_auth(self.root, self.state.unseal(session.vrk, m['secret'])), {'kind': 'auth', 'dataset_id': dataset, 'force': True})
                    st['auth_fingerprint'] = fp
                client.upload(data, {'kind': 'db', 'environment': 'production', 'dataset_id': dataset, 'generation': generation,
                                     'base_generation': generation - 1, 'created_at': _now_iso(), 'force': True, 'meta': {'mirror': True}})
                st.update(blobs=sorted(sent), last_ok=_now_iso(), generation=generation, error=None)
            except Exception as exc:
                st.update(error=str(exc)[:200], last_error_at=_now_iso())
            states[m['url']] = st
        self.state.set(mirror_state=states)

    def sync_state(self) -> dict:
        return {'data_version': self.data_version, 'waiting_for': self.status.get('waiting_for'),
                'offline': bool(self.status.get('offline')), 'script_outdated': bool(self.status.get('script_outdated')), 'holding': self.lease_until > time.time(),
                'pending_changes': bool(self.state.get('dirty_since'))}

    # -- connect / status ---------------------------------------------------------
    def connect(self, session, url: str, secret: str, *, mode: str | None = None) -> dict:
        """mode=None: first look. mode='replace': this computer becomes the cloud's content."""
        from .db import Database
        client = self.client_factory(url, secret)
        head = client.call('ping', {}).get('head')
        db = Database(self.root, 'production', session.db_key)
        dataset = self.dataset_id(db)
        if head and head.get('dataset_id') != dataset and mode != 'replace':
            return {'needs_choice': True, 'head': head}
        self.state.set(enabled=True, url=url, uploaded_blobs=[], auth_fingerprint=None, conflict=None,
                       generation=int(head['generation']) if head and head.get('dataset_id') == dataset else 0)
        self.state.store_secret(session.vrk, secret)
        if head and head.get('dataset_id') == dataset:
            self.state.set(uploaded_blobs=client.call('list_blobs', {}).get('names', []))
        self.mark_dirty()
        result = self.sync_now(session, force=(mode == 'replace'))
        return {'connected': True, 'sync': result}

    def points(self, session) -> list[dict]:
        return self.client(session.vrk).call('list_snapshots', {'kind': 'db'}).get('items', [])

    def restore_point(self, session, snapshot_id: str) -> dict:
        """C-06 — bring the database back to a cloud restore point (last 14 days) and make it the new head."""
        from .backup import restore_backup, verify_backup
        from .db import Database
        with self.lock:
            client = self.client(session.vrk)
            head = client.call('ping', {}).get('head') or {}
            manifest, data = client.download('db', snapshot_id)
            tmp = Path(tempfile.mkdtemp(prefix='ustracker-point-', dir=str(self.root / 'UserData')))
            try:
                path = tmp / 'point.usbk'
                path.write_bytes(data)
                verify_backup(path, session.vrk)
                db = Database(self.root, 'production', session.db_key)
                from .backup import create_backup
                create_backup(self.root, db, session.vrk)  # local safety copy of the current state
                restore_backup(self.root, db, session.vrk, path)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            # missing photos referenced by the restored point
            for name in client.call('list_blobs', {}).get('names', []):
                target = blob_target(self.root, name)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(client.get_blob(name))
            self.state.set(generation=int(head.get('generation') or manifest['generation']))
            self.mark_dirty()
        result = self.sync_now(session)
        return {'restored': manifest['id'], 'created_at': manifest['created_at'], 'new_generation': result['generation']}

    def describe(self, vrk: bytes | None = None) -> dict:
        s = self.state
        return {'enabled': bool(s.get('enabled')), 'url': s.get('url'), 'generation': s.get('generation') or 0,
                'last_upload_at': s.get('last_upload_at'), 'last_upload_size': s.get('last_upload_size'),
                'pending_changes': bool(s.get('dirty_since')), 'last_error': s.get('last_error'),
                'conflict': s.get('conflict'), 'running': self.status['running'], 'files_in_cloud': len(s.get('uploaded_blobs', [])),
                'debounce_seconds': self.debounce, 'placa_seq': s.get('placa_seq'), 'placa_error': self.status.get('placa_error'),
                'mirrors': [{'url': m['url'], **{k: v for k, v in ((s.get('mirror_state') or {}).get(m['url']) or {}).items() if k in ('last_ok', 'error', 'generation')}}
                            for m in (s.get('mirrors') or [])]}


# ----------------------------------------------------------------------------- restore on a new machine
def restore_from_cloud(root: Path, url: str, secret: str, *, client_factory=CloudClient, snapshot_id: str = 'head') -> dict:
    """Bring a whole installation back from the cloud (before login).

    The local Auth/Production are first moved to ``UserData/Backups/PreCloudRestore-<ts>``.
    The database snapshot is applied at the next production login (it needs the VRK).
    """
    root = Path(root)
    client = client_factory(url, secret)
    ping = client.call('ping', {})
    if not ping.get('head') or not ping.get('auth_head'):
        raise CloudError('EMPTY', 'a nuvem ainda não tem dados para restaurar')
    _, auth_blob = client.download('auth', 'head')
    auth_files = open_auth(auth_blob, secret)
    manifest, snapshot = client.download('db', snapshot_id)
    names = client.call('list_blobs', {}).get('names', [])
    data_root = root / 'UserData'
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    keep = data_root / 'Backups' / f'PreCloudRestore-{stamp}'
    if (data_root / 'Auth').exists() or (data_root / 'Production').exists():
        keep.mkdir(parents=True, exist_ok=True)
        for sub in ('Auth', 'Production'):
            if (data_root / sub).exists():
                shutil.copytree(data_root / sub, keep / sub, dirs_exist_ok=True)
    fetched = 0
    for name in names:
        target = blob_target(root, name)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + '.download')
        tmp.write_bytes(client.get_blob(name))
        tmp.replace(target)
        fetched += 1
    auth_dir = data_root / 'Auth'
    auth_dir.mkdir(parents=True, exist_ok=True)
    for name, data in auth_files.items():
        (auth_dir / name).write_bytes(data)
    state_dir = data_root / 'State'
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / 'cloud_restore.usbk').write_bytes(snapshot)
    state = CloudState(root)
    state.data = {'enabled': True, 'url': url, 'generation': int(manifest['generation']), 'dataset_id': manifest['dataset_id'],
                  'uploaded_blobs': sorted(names), 'restore_pending': True, 'restored_from': manifest['id'],
                  'auth_head_id': (ping.get('auth_head') or {}).get('id')}
    state.save()
    return {'snapshot': manifest['id'], 'generation': manifest['generation'], 'created_at': manifest['created_at'],
            'files_downloaded': fetched, 'local_backup': str(keep.relative_to(root)) if keep.exists() else None,
            'counts': (manifest.get('meta') or {}).get('counts')}


def apply_pending_restore(root: Path, db, session, sync: CloudSync | None = None) -> dict | None:
    """At the first production login after a cloud restore: apply the snapshot, take the writer role."""
    from .backup import restore_backup
    from .station import ensure_station
    root = Path(root)
    pending = root / 'UserData' / 'State' / 'cloud_restore.usbk'
    if not pending.exists():
        return None
    try:
        restore_backup(root, db, session.vrk, pending)
    except Exception as exc:  # wrong key / damaged copy: keep the file, never start with an empty base
        raise ValueError(f'a cópia baixada da nuvem não pôde ser aplicada ({type(exc).__name__}); nada foi alterado') from exc
    pending.unlink(missing_ok=True)
    from .db import Database
    fresh = Database(root, 'production', session.db_key)
    station = ensure_station(root, fresh)
    with fresh.transaction() as con:  # S-01: one more Servidor; the cloud turn decides who writes
        con.execute("UPDATE stations SET is_writer=1,status='ACTIVE' WHERE id=?", (station['id'],))
    station = dict(fresh.one('SELECT * FROM stations WHERE id=?', (station['id'],)))
    state = CloudState(root)
    state.set(restore_pending=False, auth_fingerprint=_auth_fingerprint(root), dirty_since=None)
    if sync is not None and sync.pending_secret:
        state.store_secret(session.vrk, sync.pending_secret)
        sync.pending_secret = None
        sync.state = CloudState(root)
    return {'restored': True, 'station': station.get('id')}
