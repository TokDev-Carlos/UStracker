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
PROTOCOL = 1
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
class CloudClient:
    def __init__(self, url: str, secret: str, *, timeout: float = 120.0, opener=None):
        url = str(url or '').strip()
        if not url.startswith('https://') and not url.startswith('http://127.0.0.1') and not url.startswith('http://localhost'):
            raise CloudError('BAD_URL', 'a URL do App da Web deve começar com https://')
        if not secret or len(secret.strip()) < 16:
            raise CloudError('BAD_SECRET', 'código de conexão inválido')
        self.url = url
        self.secret = secret.strip()
        self.timeout = timeout
        self.opener = opener or urllib.request.build_opener()

    def call(self, action: str, body: dict | None = None, *, retries: int = 3) -> dict:
        last: Exception | None = None
        for attempt in range(retries):
            body_text = json.dumps(body or {}, separators=(',', ':'))
            ts = int(time.time() * 1000)
            nonce = secrets.token_hex(16)
            sig = hmac.new(self.secret.encode(), f'{action}\n{ts}\n{nonce}\n{body_text}'.encode(), hashlib.sha256).hexdigest()
            payload = json.dumps({'v': PROTOCOL, 'action': action, 'ts': ts, 'nonce': nonce, 'body': body_text, 'sig': sig}).encode()
            req = urllib.request.Request(self.url, data=payload, method='POST', headers={'Content-Type': 'text/plain;charset=utf-8'})
            try:
                with self.opener.open(req, timeout=self.timeout) as resp:  # Apps Script answers 302 -> GET (handled by urllib)
                    raw = resp.read()
                out = json.loads(raw.decode('utf-8'))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last = CloudError('NETWORK', str(exc))
                time.sleep(min(2 ** attempt, 8) if attempt + 1 < retries else 0)
                continue
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
        self.status = {'running': False, 'last_error': None}
        self.pending_secret: str | None = None  # after a cloud restore, until the first login

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
        last_purge = 0.0
        while not self.stop_event.wait(10):
            try:
                session = self._session()
                if not session:
                    continue
                if time.time() - last_purge > 3600:
                    last_purge = time.time()
                    self.purge_trash(session)
                if self.enabled() and self.state.get('dirty_since') and time.time() - float(self.state.get('last_change') or 0) >= self.debounce:
                    self.sync_now(session)
            except Exception as exc:  # never kill the loop
                self.status['last_error'] = str(exc)

    def flush(self, timeout: float = 60.0) -> bool:
        """Called when the system closes: upload pending changes right away."""
        session = self._session()
        if not (session and self.enabled() and self.state.get('dirty_since')):
            return False
        done = threading.Event()
        def run():
            try:
                self.sync_now(session)
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

    def sync_now(self, session, *, force: bool = False) -> dict:
        from .backup import create_backup
        from .db import Database
        from .station import local_identity
        with self.lock:
            if not self.enabled():
                raise CloudError('DISABLED', 'nuvem não conectada')
            self.status['running'] = True
            try:
                client = self.client(session.vrk)
                db = Database(self.root, 'production', session.db_key)
                from .station import ensure_station
                if not bool(ensure_station(self.root, db)['is_writer']):
                    raise CloudError('READ_ONLY', 'esta estação é só leitura; apenas a estação escritora envia à nuvem')
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
                # 2) deletions requested by the Lixeira (14 days are over)
                pending = list(self.state.get('pending_delete', []))
                if pending:
                    client.call('delete_blobs', {'names': pending})
                    self.state.set(pending_delete=[], uploaded_blobs=sorted(known - set(pending)))
                # 3) access vault when it changed
                fp = _auth_fingerprint(self.root)
                if fp != self.state.get('auth_fingerprint'):
                    client.upload(seal_auth(self.root, self.state.secret(session.vrk)), {'kind': 'auth', 'dataset_id': dataset, 'force': force})
                    self.state.set(auth_fingerprint=fp)
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
                'debounce_seconds': self.debounce}


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
                  'uploaded_blobs': sorted(names), 'restore_pending': True, 'restored_from': manifest['id']}
    state.save()
    return {'snapshot': manifest['id'], 'generation': manifest['generation'], 'created_at': manifest['created_at'],
            'files_downloaded': fetched, 'local_backup': str(keep.relative_to(root)) if keep.exists() else None,
            'counts': (manifest.get('meta') or {}).get('counts')}


def apply_pending_restore(root: Path, db, session, sync: CloudSync | None = None) -> dict | None:
    """At the first production login after a cloud restore: apply the snapshot, take the writer role."""
    from .backup import restore_backup
    from .station import emergency_takeover
    root = Path(root)
    pending = root / 'UserData' / 'State' / 'cloud_restore.usbk'
    if not pending.exists():
        return None
    restore_backup(root, db, session.vrk, pending)
    pending.unlink(missing_ok=True)
    from .db import Database
    fresh = Database(root, 'production', session.db_key)
    station = emergency_takeover(root, fresh, 'ASSUMIR EMERGENCIA', 'Restaurado da nuvem nesta máquina')
    state = CloudState(root)
    state.set(restore_pending=False, auth_fingerprint=_auth_fingerprint(root), dirty_since=None)
    if sync is not None and sync.pending_secret:
        state.store_secret(session.vrk, sync.pending_secret)
        sync.pending_secret = None
        sync.state = CloudState(root)
    return {'restored': True, 'station': station.get('id')}
