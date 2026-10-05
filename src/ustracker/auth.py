from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .crypto import (
    aes_decrypt,
    aes_encrypt,
    b64d,
    b64e,
    canonical_json,
    derive_password_key,
    derive_ticket_key,
    random_bytes,
)

UTC = timezone.utc
IDLE_LIMIT = timedelta(minutes=60)
ABSOLUTE_LIMIT = timedelta(hours=12)
ENROLLMENT_TTL = timedelta(minutes=15)
USER_SLOT_BASE = 1000  # actor id of user N in audit trails = 1000 + N


@dataclass(slots=True)
class Session:
    token: str
    csrf: str
    slot: int
    name: str
    environment: str
    created_at: datetime
    last_human_activity: datetime
    vrk: bytes
    db_key: bytes
    media_key: bytes
    kind: str = 'admin'            # 'admin' (posições 1..3) ou 'user'
    package: str = 'ADMIN'
    package_title: str = 'Administrador'
    permissions: frozenset = frozenset()
    global_keys: dict | None = None

    @property
    def is_admin(self) -> bool:
        return self.kind in ('admin', 'global')

    @property
    def is_global(self) -> bool:
        return self.kind == 'global'

    def can(self, permission) -> bool:
        from .access import has
        return self.is_admin or has(self.permissions, permission)


class AuthService:
    """Three-slot AuthStore + VRK envelopes and in-memory sessions."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.auth_dir = self.root / 'UserData' / 'Auth'
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.auth_dir / 'auth.db'
        self.vault_path = self.auth_dir / 'vault.json'
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}
        self._login_failures: dict[str, tuple[int, datetime]] = {}
        self._init_store()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        return con

    @contextmanager
    def _connection(self):
        con = self._connect()
        try:
            with con:
                yield con
        finally:
            con.close()

    def _init_store(self) -> None:
        with self._connection() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS admins(
              slot INTEGER PRIMARY KEY CHECK(slot BETWEEN 1 AND 3),
              name TEXT UNIQUE,
              salt TEXT,
              vrk_nonce TEXT,
              vrk_cipher TEXT,
              status TEXT NOT NULL DEFAULT 'PENDING_ENROLLMENT',
              revision INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS enrollment(
              slot INTEGER PRIMARY KEY,
              ticket_hash TEXT NOT NULL,
              salt TEXT NOT NULL,
              vrk_nonce TEXT NOT NULL,
              vrk_cipher TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              FOREIGN KEY(slot) REFERENCES admins(slot) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS packages(
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL UNIQUE,
              description TEXT NOT NULL DEFAULT '',
              permissions TEXT NOT NULL DEFAULT '[]',
              builtin INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE COLLATE NOCASE,
              full_name TEXT NOT NULL DEFAULT '',
              package_id TEXT NOT NULL REFERENCES packages(id),
              salt TEXT NOT NULL, vrk_nonce TEXT NOT NULL, vrk_cipher TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              revision INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recovery(
              slot INTEGER PRIMARY KEY,
              salt TEXT NOT NULL, nonce TEXT NOT NULL, cipher TEXT NOT NULL,
              shown INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS global_access(
              id INTEGER PRIMARY KEY CHECK(id = 1),
              wrap TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_lock(
              identity TEXT PRIMARY KEY,
              attempts INTEGER NOT NULL DEFAULT 0,
              question_id INTEGER,
              locked_until TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_audit(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              at TEXT NOT NULL,
              actor_slot INTEGER,
              action TEXT NOT NULL,
              detail TEXT NOT NULL
            );
            ''')
            now = self._now().isoformat()
            # G-04: one local administrator. Never-used reserve slots (2, 3) go away.
            con.execute('INSERT OR IGNORE INTO admins(slot,status,updated_at) VALUES(1,?,?)', ('PENDING_ENROLLMENT', now))
            con.execute("DELETE FROM enrollment")
            con.execute("DELETE FROM admins WHERE slot IN (2, 3) AND status <> 'ENROLLED'")
            from .access import BUILTIN_PACKAGES
            for pid, (title, desc, perms) in BUILTIN_PACKAGES.items():
                # built-in packages are refreshed on every start so new permissions reach them
                con.execute('''INSERT INTO packages(id,title,description,permissions,builtin,updated_at) VALUES(?,?,?,?,1,?)
                               ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,
                               permissions=excluded.permissions,builtin=1''',
                            (pid, title, desc, json.dumps(sorted(perms)), now))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def setup_status(self) -> dict:
        with self._connection() as con:
            rows = con.execute('SELECT slot,name,status FROM admins ORDER BY slot').fetchall()
        enrolled = sum(1 for r in rows if r['status'] == 'ENROLLED')
        return {
            'slots': 1,
            'enrolled': enrolled,
            'complete': enrolled >= 1,
            'admins': [{'slot': r['slot'], 'name': r['name'], 'status': r['status']} for r in rows],
        }

    def _create_admin_envelope(self, vrk: bytes, password: str) -> tuple[str, str, str]:
        self._validate_secret(password)
        salt = random_bytes(16)
        key = derive_password_key(password, salt)
        nonce, cipher = aes_encrypt(key, vrk, b'UStracker/VRK/admin/v1')
        return b64e(salt), b64e(nonce), b64e(cipher)

    @staticmethod
    def _validate_secret(secret: str) -> None:
        if len(secret) < 4:
            raise ValueError('secret must have at least 4 characters')

    def _check_login_throttle(self, identity: str) -> None:
        attempts, blocked_until = self._login_failures.get(identity, (0, self._now()))
        if blocked_until > self._now():
            remaining = max(1, int((blocked_until - self._now()).total_seconds() + 0.999))
            raise ValueError(f'login temporarily locked; try again in {remaining} seconds')

    def _record_login_failure(self, identity: str) -> None:
        attempts, _ = self._login_failures.get(identity, (0, self._now()))
        attempts += 1
        delay = min(300, 2 ** (attempts - 3)) if attempts >= 3 else 0
        self._login_failures[identity] = (attempts, self._now() + timedelta(seconds=delay))

    def _write_vault(self, vrk: bytes) -> None:
        payload = {
            'version': 1,
            'production': {'db_key': b64e(random_bytes(32)), 'media_key': b64e(random_bytes(32))},
            'test': {'db_key': b64e(random_bytes(32)), 'media_key': b64e(random_bytes(32))},
        }
        nonce, cipher = aes_encrypt(vrk, canonical_json(payload), b'UStracker/VaultStore/v1')
        tmp = self.vault_path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'version': 1, 'nonce': b64e(nonce), 'cipher': b64e(cipher)}, indent=2), encoding='utf-8')
        tmp.replace(self.vault_path)

    def _read_vault(self, vrk: bytes) -> dict:
        try:
            raw = json.loads(self.vault_path.read_text(encoding='utf-8'))
            plain = aes_decrypt(vrk, b64d(raw['nonce']), b64d(raw['cipher']), b'UStracker/VaultStore/v1')
            return json.loads(plain.decode('utf-8'))
        except FileNotFoundError as exc:
            raise ValueError('access vault missing on this computer') from exc
        except Exception as exc:  # InvalidTag / corrupted file: never a 500
            raise ValueError('access vault does not match this key') from exc

    def _issue_enrollment(self, con: sqlite3.Connection, slot: int, vrk: bytes) -> str:
        ticket = secrets.token_urlsafe(32)
        salt = random_bytes(16)
        key = derive_ticket_key(ticket, salt)
        nonce, cipher = aes_encrypt(key, vrk, f'UStracker/enroll/{slot}/v1'.encode())
        ticket_hash = hashlib.sha256(ticket.encode()).hexdigest()
        expires = (self._now() + ENROLLMENT_TTL).isoformat()
        con.execute('DELETE FROM enrollment WHERE slot=?', (slot,))
        con.execute('INSERT INTO enrollment(slot,ticket_hash,salt,vrk_nonce,vrk_cipher,expires_at) VALUES(?,?,?,?,?,?)',
                    (slot, ticket_hash, b64e(salt), b64e(nonce), b64e(cipher), expires))
        return ticket

    def bootstrap(self, name: str, password: str) -> dict:
        name = name.strip()
        if not name:
            raise ValueError('admin name is required')
        with self._lock, self._connection() as con:
            if con.execute("SELECT COUNT(*) FROM admins WHERE status='ENROLLED'").fetchone()[0] != 0:
                raise ValueError('bootstrap already completed')
            vrk = random_bytes(32)
            salt, nonce, cipher = self._create_admin_envelope(vrk, password)
            now = self._now().isoformat()
            con.execute('UPDATE admins SET name=?,salt=?,vrk_nonce=?,vrk_cipher=?,status=?,revision=revision+1,updated_at=? WHERE slot=1',
                        (name, salt, nonce, cipher, 'ENROLLED', now))
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (now, 1, 'BOOTSTRAP', '{}'))
            self._write_vault(vrk)
            code = self._store_recovery(con, vrk, shown=True)
            return {'slot': 1, 'recovery_key': code}

    def enroll(self, ticket: str, name: str, password: str) -> dict:
        raise ValueError('only one local administrator (G-04)')
        name = name.strip()
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        with self._lock, self._connection() as con:
            row = con.execute('SELECT * FROM enrollment WHERE ticket_hash=?', (digest,)).fetchone()
            if not row:
                raise ValueError('invalid enrollment ticket')
            if datetime.fromisoformat(row['expires_at']) < self._now():
                con.execute('DELETE FROM enrollment WHERE slot=?', (row['slot'],))
                raise ValueError('expired enrollment ticket')
            key = derive_ticket_key(ticket, b64d(row['salt']))
            vrk = aes_decrypt(key, b64d(row['vrk_nonce']), b64d(row['vrk_cipher']),
                              f"UStracker/enroll/{row['slot']}/v1".encode())
            # Validates that the ticket yielded the same VRK before persisting a new envelope.
            self._read_vault(vrk)
            salt, nonce, cipher = self._create_admin_envelope(vrk, password)
            now = self._now().isoformat()
            try:
                con.execute('UPDATE admins SET name=?,salt=?,vrk_nonce=?,vrk_cipher=?,status=?,revision=revision+1,updated_at=? WHERE slot=?',
                            (name, salt, nonce, cipher, 'ENROLLED', now, row['slot']))
            except sqlite3.IntegrityError as exc:
                raise ValueError('admin name already in use') from exc
            con.execute('DELETE FROM enrollment WHERE slot=?', (row['slot'],))
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (now, row['slot'], 'ENROLL', '{}'))
            return {'slot': row['slot'], 'name': name}

    def login(self, name: str, password: str, environment: str = 'production') -> Session:
        if environment not in ('production', 'test'):
            raise ValueError('invalid environment')
        identity = name.strip().casefold()
        with self._lock, self._connection() as con:
            self._check_login_throttle(identity)
            row = con.execute("SELECT * FROM admins WHERE name=? AND status='ENROLLED'", (name.strip(),)).fetchone()
            if not row and not con.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone():
                self._init_store()
            user = None if row else con.execute('SELECT * FROM users WHERE name=? AND active=1', (name.strip(),)).fetchone()
            if not row and not user:
                self._record_login_failure(identity)
                raise ValueError('invalid credentials')
            env = row or user
            aad = b'UStracker/VRK/admin/v1' if row else b'UStracker/VRK/user/v1'
            try:
                key = derive_password_key(password, b64d(env['salt']))
                vrk = aes_decrypt(key, b64d(env['vrk_nonce']), b64d(env['vrk_cipher']), aad)
                vault = self._read_vault(vrk)
            except Exception as exc:
                self._record_login_failure(identity)
                raise ValueError('invalid credentials') from exc
            self._login_failures.pop(identity, None)
            if environment == 'test' and not row:
                raise ValueError('test environment is for administrators only')
            now = self._now()
            extra = {}
            if user:
                pkg = con.execute('SELECT * FROM packages WHERE id=?', (user['package_id'],)).fetchone()
                from .access import clean
                extra = {'kind': 'user', 'package': user['package_id'], 'package_title': pkg['title'] if pkg else '',
                         'permissions': clean(json.loads(pkg['permissions']) if pkg else [])}
            slot = row['slot'] if row else USER_SLOT_BASE + user['id']
            session = Session(
                token=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(24), slot=slot, name=env['name'],
                environment=environment, created_at=now, last_human_activity=now, vrk=vrk,
                db_key=b64d(vault[environment]['db_key']), media_key=b64d(vault[environment]['media_key']), **extra
            )
            self._sessions[session.token] = session
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (now.isoformat(), slot, 'LOGIN', json.dumps({'environment': environment})))
            return session

    def switch_environment(self, session: Session, environment: str) -> Session:
        """G-03 — an Administrator moves between Real and Teste without typing the password again."""
        if environment not in ('production', 'test'):
            raise ValueError('invalid environment')
        if not session.is_admin:
            raise PermissionError('administrator required')
        vault = self._read_vault(session.vrk)
        now = self._now()
        new = Session(token=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(24), slot=session.slot, name=session.name,
                      environment=environment, created_at=now, last_human_activity=now, vrk=session.vrk,
                      db_key=b64d(vault[environment]['db_key']), media_key=b64d(vault[environment]['media_key']),
                      kind=session.kind, package=session.package, package_title=session.package_title, global_keys=session.global_keys)
        with self._lock, self._connection() as con:
            self._sessions[new.token] = new
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (now.isoformat(), session.slot, 'ENVIRONMENT', json.dumps({'environment': environment})))
        return new

    def clear_sessions(self) -> None:
        """After a cloud restore replaced the access vault, every open session is void."""
        with self._lock:
            self._sessions.clear()

    def get_session(self, token: str | None, *, human_activity: bool = False) -> Session | None:
        if not token:
            return None
        with self._lock:
            session = self._sessions.get(token)
            if not session:
                return None
            now = self._now()
            if now - session.created_at > ABSOLUTE_LIMIT or now - session.last_human_activity > IDLE_LIMIT:
                self._sessions.pop(token, None)
                return None
            if human_activity:
                session.last_human_activity = now
            return session

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def change_password(self, session: Session, current_password: str, new_password: str) -> None:
        try:
            return self._change_password(session, current_password, new_password)
        except (ValueError, PermissionError, KeyError):
            raise
        except Exception as exc:  # wrong current password -> authentication tag mismatch
            raise ValueError('invalid credentials') from exc

    def _change_password(self, session: Session, current_password: str, new_password: str) -> None:
        if not session.is_admin:
            return self._change_user_password(session, current_password, new_password)
        with self._lock, self._connection() as con:
            row = con.execute('SELECT * FROM admins WHERE slot=?', (session.slot,)).fetchone()
            old = derive_password_key(current_password, b64d(row['salt']))
            vrk = aes_decrypt(old, b64d(row['vrk_nonce']), b64d(row['vrk_cipher']), b'UStracker/VRK/admin/v1')
            salt, nonce, cipher = self._create_admin_envelope(vrk, new_password)
            con.execute('UPDATE admins SET salt=?,vrk_nonce=?,vrk_cipher=?,revision=revision+1,updated_at=? WHERE slot=?',
                        (salt, nonce, cipher, self._now().isoformat(), session.slot))
            for token, existing in list(self._sessions.items()):
                if existing.slot == session.slot:
                    self._sessions.pop(token, None)

    def remove_all_users(self, session: Session) -> dict:
        """G-02 — keep only the administrators: every user and every custom package goes (built-ins stay)."""
        if not session.is_admin:
            raise PermissionError('administrator required')
        with self._lock, self._connection() as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone():
                self._init_store()
            users = con.execute('DELETE FROM users').rowcount
            packages = con.execute('DELETE FROM packages WHERE builtin=0').rowcount
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (self._now().isoformat(), session.slot, 'FACTORY_RESET', json.dumps({'users': users, 'packages': packages})))
        for token, existing in list(self._sessions.items()):
            if existing.slot >= USER_SLOT_BASE:
                self._sessions.pop(token, None)
        return {'users': users, 'packages': packages}

    def reset_admin(self, session: Session, slot: int, reason: str) -> str:
        raise ValueError('use the Adm Global to reset the local administrator (G-04)')
        if slot == session.slot or slot not in (1, 2, 3) or not reason.strip():
            raise ValueError('invalid reset request')
        with self._lock, self._connection() as con:
            row = con.execute('SELECT status FROM admins WHERE slot=?', (slot,)).fetchone()
            if not row or row['status'] != 'ENROLLED':
                raise ValueError('slot is not enrolled')
            enrolled = con.execute("SELECT COUNT(*) FROM admins WHERE status='ENROLLED'").fetchone()[0]
            if enrolled < 2:
                raise ValueError('cannot remove last usable admin envelope')
            con.execute('UPDATE admins SET name=NULL,salt=NULL,vrk_nonce=NULL,vrk_cipher=NULL,status=?,revision=revision+1,updated_at=? WHERE slot=?',
                        ('PENDING_ENROLLMENT', self._now().isoformat(), slot))
            for token, existing in list(self._sessions.items()):
                if existing.slot == slot:
                    self._sessions.pop(token, None)
            ticket = self._issue_enrollment(con, slot, session.vrk)
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (self._now().isoformat(), session.slot, 'RESET_ADMIN', json.dumps({'slot': slot, 'reason': reason[:200]})))
            return ticket

    # ------------------------------------------------------------------ G-04 Chave de Recuperação do Adm Local
    RECOVERY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

    @staticmethod
    def _norm_code(code: str) -> str:
        return ''.join(c for c in str(code or '').upper() if c.isalnum())

    def _store_recovery(self, con, vrk: bytes, *, shown: bool) -> str:
        raw = ''.join(secrets.choice(self.RECOVERY_ALPHABET) for _ in range(24))
        code = '-'.join(raw[i:i + 4] for i in range(0, 24, 4))
        salt = random_bytes(16)
        nonce, cipher = aes_encrypt(derive_password_key(raw, salt), vrk, b'UStracker/VRK/recovery/v1')
        con.execute('INSERT OR REPLACE INTO recovery(slot,salt,nonce,cipher,shown,updated_at) VALUES(1,?,?,?,?,?)',
                    (b64e(salt), b64e(nonce), b64e(cipher), 1 if shown else 0, self._now().isoformat()))
        return code

    def ensure_recovery(self, session: Session) -> str | None:
        """Old installations: the local administrator gets a recovery key once (shown at that login)."""
        if session.kind != 'admin':
            return None
        with self._lock, self._connection() as con:
            if con.execute('SELECT 1 FROM recovery WHERE slot=1').fetchone():
                return None
            code = self._store_recovery(con, session.vrk, shown=True)
            self._audit(con, session.slot, 'RECOVERY_KEY', {'created': True})
            return code

    def recover(self, code: str, new_password: str) -> dict:
        identity = 'recovery'
        with self._lock, self._connection() as con:
            self._check_login_throttle(identity)
            row = con.execute('SELECT * FROM recovery WHERE slot=1').fetchone()
            try:
                vrk = aes_decrypt(derive_password_key(self._norm_code(code), b64d(row['salt'])), b64d(row['nonce']),
                                  b64d(row['cipher']), b'UStracker/VRK/recovery/v1')
                self._read_vault(vrk)
            except Exception as exc:
                self._record_login_failure(identity)
                raise ValueError('invalid recovery key') from exc
            self._set_local_password(con, vrk, new_password)
            self._audit(con, 1, 'RECOVERY_USED', {})
            self._login_failures.pop(identity, None)
            return {'ok': True}

    def _set_local_password(self, con, vrk: bytes, new_password: str) -> None:
        salt, nonce, cipher = self._create_admin_envelope(vrk, new_password)
        con.execute('UPDATE admins SET salt=?,vrk_nonce=?,vrk_cipher=?,revision=revision+1,updated_at=? WHERE slot=1',
                    (salt, nonce, cipher, self._now().isoformat()))
        for token, existing in list(self._sessions.items()):
            if existing.slot == 1:
                self._sessions.pop(token, None)

    def reset_local_admin(self, session: Session, new_password: str) -> dict:
        if not session.is_global:
            raise PermissionError('Adm Global required')
        with self._lock, self._connection() as con:
            self._set_local_password(con, session.vrk, new_password)
            self._audit(con, session.slot, 'LOCAL_ADMIN_RESET', {})
        return {'ok': True}

    def regenerate_recovery(self, session: Session) -> str:
        if not session.is_global:
            raise PermissionError('Adm Global required')
        with self._lock, self._connection() as con:
            code = self._store_recovery(con, session.vrk, shown=True)
            self._audit(con, session.slot, 'RECOVERY_KEY', {'regenerated': True})
            return code

    # ------------------------------------------------------------------ G-04 Adm Global
    GLOBAL_SLOT = 0

    def ensure_global_wrap(self, session: Session, trust: dict | None) -> bool:
        """Local administrator logged in: keep a copy of the VRK sealed for the Adm Global's public key."""
        from . import adm_global
        if not trust or session.kind != 'admin':
            return False
        with self._lock, self._connection() as con:
            row = con.execute('SELECT wrap FROM global_access WHERE id=1').fetchone()
            if row and json.loads(row['wrap']).get('x_pub') == trust['x_pub']:
                return False
            con.execute('INSERT OR REPLACE INTO global_access(id,wrap,updated_at) VALUES(1,?,?)',
                        (json.dumps(adm_global.wrap(session.vrk, trust)), self._now().isoformat()))
            self._audit(con, session.slot, 'GLOBAL_ACCESS_READY', {})
            return True

    def global_lock_state(self, identity: str) -> dict:
        self._init_store()  # auth.db may have come from the cloud (older version)
        with self._connection() as con:
            row = con.execute('SELECT * FROM login_lock WHERE identity=?', (identity,)).fetchone()
        out = {'attempts': row['attempts'] if row else 0, 'question_id': row['question_id'] if row else None, 'locked_minutes': 0}
        if row and row['locked_until']:
            left = (datetime.fromisoformat(row['locked_until']) - self._now()).total_seconds()
            if left > 0:
                out['locked_minutes'] = int(left // 60) + 1
        return out

    def global_question(self, identity: str) -> dict:
        """The same fake question stays until success or lock, so the hints look consistent."""
        from . import adm_global
        state = self.global_lock_state(identity)
        if state['question_id']:
            text = next((t for q, t, _ in adm_global.QUESTIONS if q == state['question_id']), None)
            if text:
                return {'id': state['question_id'], 'question': text}
        q = adm_global.question()
        with self._lock, self._connection() as con:
            con.execute('INSERT INTO login_lock(identity,attempts,question_id) VALUES(?,0,?) ON CONFLICT(identity) DO UPDATE SET question_id=excluded.question_id',
                        (identity, q['id']))
        return q

    def global_failure(self, identity: str, reason: str) -> dict:
        from . import adm_global
        self._init_store()
        with self._lock, self._connection() as con:
            row = con.execute('SELECT * FROM login_lock WHERE identity=?', (identity,)).fetchone()
            attempts = (row['attempts'] if row else 0) + 1
            qid = row['question_id'] if row and row['question_id'] else adm_global.QUESTIONS[0][0]
            locked = (self._now() + timedelta(minutes=adm_global.LOCK_MINUTES)).isoformat() if attempts >= adm_global.LOCK_ATTEMPTS else None
            con.execute('INSERT OR REPLACE INTO login_lock(identity,attempts,question_id,locked_until) VALUES(?,?,?,?)',
                        (identity, 0 if locked else attempts, None if locked else qid, locked))
            self._audit(con, None, 'GLOBAL_DECOY', {'reason': reason, 'attempt': attempts, 'locked': bool(locked)})
        return {'hint': adm_global.hint_for(qid, attempts), 'locked': bool(locked)}

    def global_login(self, root, trust: dict, pin: str, environment: str = 'production') -> Session:
        from . import adm_global
        token = adm_global.current_token(root, trust)
        keys = adm_global.open_keys(token, pin, trust)
        return self.global_session(trust, keys, environment)

    def global_session(self, trust: dict, keys: dict, environment: str = 'production') -> Session:
        """Keys already opened with the PIN (Token Mestre): unlock this installation's VRK."""
        from . import adm_global
        self._init_store()
        with self._connection() as con:
            row = con.execute('SELECT wrap FROM global_access WHERE id=1').fetchone()
        if not row:
            raise adm_global.AccessDenied('installation not prepared')
        wrapped = json.loads(row['wrap'])
        if wrapped.get('x_pub') != trust['x_pub']:
            raise adm_global.AccessDenied('installation not prepared')
        vrk = adm_global.unwrap(wrapped, keys)
        try:
            vault = self._read_vault(vrk)
        except ValueError as exc:
            raise adm_global.AccessDenied('installation not prepared') from exc
        now = self._now()
        session = Session(token=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(24), slot=self.GLOBAL_SLOT, name=trust['login'],
                          environment=environment, created_at=now, last_human_activity=now, vrk=vrk,
                          db_key=b64d(vault[environment]['db_key']), media_key=b64d(vault[environment]['media_key']),
                          kind='global', package='GLOBAL', package_title='Adm Global')
        session.global_keys = keys
        with self._lock, self._connection() as con:
            self._sessions[session.token] = session
            con.execute('DELETE FROM login_lock WHERE identity=?', (trust['login'].casefold(),))
            self._audit(con, self.GLOBAL_SLOT, 'LOGIN', {'environment': environment, 'global': True})
        return session

    # ------------------------------------------------------------------ U-01..U-04 usuários e pacotes
    def _user_envelope(self, vrk: bytes, password: str) -> tuple[str, str, str]:
        self._validate_secret(password)
        salt = random_bytes(16)
        nonce, cipher = aes_encrypt(derive_password_key(password, salt), vrk, b'UStracker/VRK/user/v1')
        return b64e(salt), b64e(nonce), b64e(cipher)

    def _audit(self, con, actor: int, action: str, detail: dict) -> None:
        con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                    (self._now().isoformat(), actor, action, json.dumps(detail, ensure_ascii=False)))

    @staticmethod
    def _require_admin(session: Session) -> None:
        if not session or not session.is_admin:
            raise PermissionError('administrator required')

    def list_packages(self) -> list[dict]:
        self._init_store()  # auth.db may have arrived from an older version (cloud)
        with self._connection() as con:
            rows = con.execute('SELECT * FROM packages ORDER BY builtin DESC, title').fetchall()
            counts = {r[0]: r[1] for r in con.execute('SELECT package_id,COUNT(*) FROM users GROUP BY package_id')}
        return [{'id': r['id'], 'title': r['title'], 'description': r['description'], 'builtin': bool(r['builtin']),
                 'permissions': json.loads(r['permissions']), 'users': counts.get(r['id'], 0)} for r in rows]

    def save_package(self, session: Session, p: dict, package_id: str | None = None) -> dict:
        from .access import clean
        self._require_admin(session)
        title = str(p.get('title') or '').strip()
        if not title:
            raise ValueError('package title required')
        perms = sorted(clean(p.get('permissions')))
        desc = str(p.get('description') or '').strip()[:300]
        now = self._now().isoformat()
        with self._lock, self._connection() as con:
            if package_id:
                row = con.execute('SELECT builtin FROM packages WHERE id=?', (package_id,)).fetchone()
                if not row:
                    raise KeyError('package not found')
                if row['builtin']:
                    raise ValueError('built-in package cannot be changed')
                try:
                    con.execute('UPDATE packages SET title=?,description=?,permissions=?,updated_at=? WHERE id=?',
                                (title, desc, json.dumps(perms), now, package_id))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('package title already in use') from exc
            else:
                package_id = 'P' + secrets.token_hex(6).upper()
                try:
                    con.execute('INSERT INTO packages(id,title,description,permissions,builtin,updated_at) VALUES(?,?,?,?,0,?)',
                                (package_id, title, desc, json.dumps(perms), now))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('package title already in use') from exc
            self._audit(con, session.slot, 'PACKAGE_SAVE', {'id': package_id, 'title': title})
        self._refresh_sessions()
        return next(x for x in self.list_packages() if x['id'] == package_id)

    def delete_package(self, session: Session, package_id: str) -> dict:
        self._require_admin(session)
        with self._lock, self._connection() as con:
            row = con.execute('SELECT builtin FROM packages WHERE id=?', (package_id,)).fetchone()
            if not row:
                raise KeyError('package not found')
            if row['builtin']:
                raise ValueError('built-in package cannot be changed')
            if con.execute('SELECT 1 FROM users WHERE package_id=?', (package_id,)).fetchone():
                raise ValueError('package in use by users')
            con.execute('DELETE FROM packages WHERE id=?', (package_id,))
            self._audit(con, session.slot, 'PACKAGE_DELETE', {'id': package_id})
        return {'id': package_id, 'deleted': True}

    def list_users(self) -> list[dict]:
        self._init_store()
        with self._connection() as con:
            rows = con.execute('''SELECT u.id,u.name,u.full_name,u.package_id,u.active,u.created_at,u.updated_at,p.title AS package_title
                                    FROM users u LEFT JOIN packages p ON p.id=u.package_id ORDER BY u.active DESC,u.name''').fetchall()
        return [{**dict(r), 'active': bool(r['active'])} for r in rows]

    def _name_free(self, con, name: str, user_id: int | None = None) -> None:
        if con.execute('SELECT 1 FROM admins WHERE name=? COLLATE NOCASE', (name,)).fetchone():
            raise ValueError('admin name already in use')
        if con.execute('SELECT 1 FROM users WHERE name=? AND id<>?', (name, user_id or -1)).fetchone():
            raise ValueError('admin name already in use')

    def create_user(self, session: Session, p: dict) -> dict:
        self._require_admin(session)
        self._init_store()
        name = str(p.get('name') or '').strip()
        if not name:
            raise ValueError('admin name is required')
        package_id = str(p.get('package_id') or 'OPERADOR')
        salt, nonce, cipher = self._user_envelope(session.vrk, str(p.get('password') or ''))
        now = self._now().isoformat()
        with self._lock, self._connection() as con:
            if not con.execute('SELECT 1 FROM packages WHERE id=?', (package_id,)).fetchone():
                raise KeyError('package not found')
            self._name_free(con, name)
            cur = con.execute('''INSERT INTO users(name,full_name,package_id,salt,vrk_nonce,vrk_cipher,active,created_at,updated_at)
                                 VALUES(?,?,?,?,?,?,1,?,?)''', (name, str(p.get('full_name') or '').strip(), package_id, salt, nonce, cipher, now, now))
            uid_ = cur.lastrowid
            self._audit(con, session.slot, 'USER_CREATE', {'id': uid_, 'name': name, 'package': package_id})
        return next(u for u in self.list_users() if u['id'] == uid_)

    def update_user(self, session: Session, user_id: int, p: dict) -> dict:
        self._require_admin(session)
        now = self._now().isoformat()
        with self._lock, self._connection() as con:
            row = con.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not row:
                raise KeyError('user not found')
            name = str(p.get('name') or row['name']).strip()
            self._name_free(con, name, user_id)
            package_id = str(p.get('package_id') or row['package_id'])
            if not con.execute('SELECT 1 FROM packages WHERE id=?', (package_id,)).fetchone():
                raise KeyError('package not found')
            active = int(p['active'] in (True, 1, '1', 'true')) if 'active' in p else row['active']
            con.execute('UPDATE users SET name=?,full_name=?,package_id=?,active=?,revision=revision+1,updated_at=? WHERE id=?',
                        (name, str(p.get('full_name', row['full_name']) or '').strip(), package_id, active, now, user_id))
            if p.get('password'):
                salt, nonce, cipher = self._user_envelope(session.vrk, str(p['password']))
                con.execute('UPDATE users SET salt=?,vrk_nonce=?,vrk_cipher=? WHERE id=?', (salt, nonce, cipher, user_id))
            self._audit(con, session.slot, 'USER_UPDATE', {'id': user_id, 'package': package_id, 'active': active, 'password_reset': bool(p.get('password'))})
        self._drop_user_sessions(user_id)
        return next(u for u in self.list_users() if u['id'] == user_id)

    def _change_user_password(self, session: Session, current_password: str, new_password: str) -> None:
        user_id = session.slot - USER_SLOT_BASE
        with self._lock, self._connection() as con:
            row = con.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            old = derive_password_key(current_password, b64d(row['salt']))
            vrk = aes_decrypt(old, b64d(row['vrk_nonce']), b64d(row['vrk_cipher']), b'UStracker/VRK/user/v1')
            salt, nonce, cipher = self._user_envelope(vrk, new_password)
            con.execute('UPDATE users SET salt=?,vrk_nonce=?,vrk_cipher=?,revision=revision+1,updated_at=? WHERE id=?',
                        (salt, nonce, cipher, self._now().isoformat(), user_id))
        self._drop_user_sessions(user_id)

    def _drop_user_sessions(self, user_id: int) -> None:
        with self._lock:
            for token, existing in list(self._sessions.items()):
                if existing.slot == USER_SLOT_BASE + user_id:
                    self._sessions.pop(token, None)

    def _refresh_sessions(self) -> None:
        """A package changed: open sessions pick up the new permissions immediately."""
        from .access import clean
        packages = {p['id']: p for p in self.list_packages()}
        with self._lock:
            for existing in self._sessions.values():
                if existing.kind == 'user' and existing.package in packages:
                    existing.permissions = clean(packages[existing.package]['permissions'])
                    existing.package_title = packages[existing.package]['title']

    # ------------------------------------------------------------------ S-02 acesso vindo de outro Servidor
    def merge_from(self, other_db: Path) -> dict:
        """Merge another Servidor's auth.db into this one (never a blind replace).

        admins by slot, users by name, packages by id: the newest ``updated_at`` wins; audit rows are
        added once. Local changes not yet sent are kept, remote ones arrive."""
        self._init_store()
        added = {'admins': 0, 'users': 0, 'packages': 0}
        with self._lock, self._connection() as con:
            con.execute('ATTACH DATABASE ? AS r', (str(other_db),))
            try:
                tables = {r[0] for r in con.execute("SELECT name FROM r.sqlite_master WHERE type='table'")}
                if 'admins' in tables:
                    for row in con.execute('SELECT * FROM r.admins').fetchall():
                        if row['slot'] != 1 and row['status'] != 'ENROLLED':
                            continue  # G-04: reserve slots are gone
                        mine = con.execute('SELECT updated_at FROM admins WHERE slot=?', (row['slot'],)).fetchone()
                        if not mine or str(row['updated_at']) > str(mine['updated_at']):
                            con.execute('UPDATE admins SET name=NULL WHERE name=? AND slot<>?', (row['name'], row['slot']))
                            con.execute('INSERT OR REPLACE INTO admins(slot,name,salt,vrk_nonce,vrk_cipher,status,revision,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                                        (row['slot'], row['name'], row['salt'], row['vrk_nonce'], row['vrk_cipher'], row['status'], row['revision'], row['updated_at']))
                            added['admins'] += 1
                if 'packages' in tables:
                    for row in con.execute('SELECT * FROM r.packages WHERE builtin=0').fetchall():
                        mine = con.execute('SELECT updated_at FROM packages WHERE id=?', (row['id'],)).fetchone()
                        if not mine or str(row['updated_at']) > str(mine['updated_at']):
                            con.execute('DELETE FROM packages WHERE title=? AND id<>? AND builtin=0', (row['title'], row['id']))
                            con.execute('INSERT OR REPLACE INTO packages(id,title,description,permissions,builtin,updated_at) VALUES(?,?,?,?,0,?)',
                                        (row['id'], row['title'], row['description'], row['permissions'], row['updated_at']))
                            added['packages'] += 1
                if 'users' in tables:
                    for row in con.execute('SELECT * FROM r.users').fetchall():
                        mine = con.execute('SELECT id,updated_at FROM users WHERE name=?', (row['name'],)).fetchone()
                        if mine and str(row['updated_at']) <= str(mine['updated_at']):
                            continue
                        if not con.execute('SELECT 1 FROM packages WHERE id=?', (row['package_id'],)).fetchone():
                            continue
                        values = (row['name'], row['full_name'], row['package_id'], row['salt'], row['vrk_nonce'], row['vrk_cipher'],
                                  row['active'], row['revision'], row['created_at'], row['updated_at'])
                        if mine:
                            con.execute('UPDATE users SET name=?,full_name=?,package_id=?,salt=?,vrk_nonce=?,vrk_cipher=?,active=?,revision=?,created_at=?,updated_at=? WHERE id=?',
                                        values + (mine['id'],))
                        else:
                            free = not con.execute('SELECT 1 FROM users WHERE id=?', (row['id'],)).fetchone()
                            con.execute('INSERT INTO users(id,name,full_name,package_id,salt,vrk_nonce,vrk_cipher,active,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                                        ((row['id'] if free else None),) + values)
                        added['users'] += 1
                from .adm_global import load_trust
                trust = load_trust(self.root)
                for table, key in (('recovery', 'slot'), ('global_access', 'id')):
                    if table in tables:
                        for row in con.execute(f'SELECT * FROM r.{table}').fetchall():
                            if table == 'global_access':
                                try:
                                    if not trust or json.loads(row['wrap']).get('x_pub') != trust['x_pub']:
                                        continue  # only the Adm Global this installer trusts
                                except Exception:
                                    continue
                            mine = con.execute(f'SELECT updated_at FROM {table} WHERE {key}=?', (row[key],)).fetchone()
                            if not mine or str(row['updated_at']) > str(mine['updated_at']):
                                cols = row.keys()
                                con.execute(f"INSERT OR REPLACE INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(row))
                if 'auth_audit' in tables:
                    con.execute('''INSERT INTO auth_audit(at,actor_slot,action,detail)
                                   SELECT a.at,a.actor_slot,a.action,a.detail FROM r.auth_audit a
                                   WHERE NOT EXISTS(SELECT 1 FROM auth_audit b WHERE b.at=a.at AND b.actor_slot IS a.actor_slot AND b.action=a.action)''')
                con.commit()
            finally:
                con.execute('DETACH DATABASE r')
        self._refresh_sessions()
        return added
