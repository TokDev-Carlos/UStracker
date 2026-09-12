from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
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
        self._init_store()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        return con

    def _init_store(self) -> None:
        with self._connect() as con:
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
            CREATE TABLE IF NOT EXISTS auth_audit(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              at TEXT NOT NULL,
              actor_slot INTEGER,
              action TEXT NOT NULL,
              detail TEXT NOT NULL
            );
            ''')
            now = self._now().isoformat()
            for slot in (1, 2, 3):
                con.execute('INSERT OR IGNORE INTO admins(slot,status,updated_at) VALUES(?,?,?)',
                            (slot, 'PENDING_ENROLLMENT', now))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def setup_status(self) -> dict:
        with self._connect() as con:
            rows = con.execute('SELECT slot,name,status FROM admins ORDER BY slot').fetchall()
        enrolled = sum(1 for r in rows if r['status'] == 'ENROLLED')
        return {
            'slots': 3,
            'enrolled': enrolled,
            'complete': enrolled == 3,
            'admins': [{'slot': r['slot'], 'name': r['name'], 'status': r['status']} for r in rows],
        }

    def _create_admin_envelope(self, vrk: bytes, password: str) -> tuple[str, str, str]:
        salt = random_bytes(16)
        key = derive_password_key(password, salt)
        nonce, cipher = aes_encrypt(key, vrk, b'UStracker/VRK/admin/v1')
        return b64e(salt), b64e(nonce), b64e(cipher)

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
        raw = json.loads(self.vault_path.read_text(encoding='utf-8'))
        plain = aes_decrypt(vrk, b64d(raw['nonce']), b64d(raw['cipher']), b'UStracker/VaultStore/v1')
        return json.loads(plain.decode('utf-8'))

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
        with self._lock, self._connect() as con:
            if con.execute("SELECT COUNT(*) FROM admins WHERE status='ENROLLED'").fetchone()[0] != 0:
                raise ValueError('bootstrap already completed')
            vrk = random_bytes(32)
            salt, nonce, cipher = self._create_admin_envelope(vrk, password)
            now = self._now().isoformat()
            con.execute('UPDATE admins SET name=?,salt=?,vrk_nonce=?,vrk_cipher=?,status=?,revision=revision+1,updated_at=? WHERE slot=1',
                        (name, salt, nonce, cipher, 'ENROLLED', now))
            tickets = [self._issue_enrollment(con, slot, vrk) for slot in (2, 3)]
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (now, 1, 'BOOTSTRAP', '{}'))
            self._write_vault(vrk)
            return {'slot': 1, 'tickets': tickets, 'expires_in_seconds': int(ENROLLMENT_TTL.total_seconds())}

    def enroll(self, ticket: str, name: str, password: str) -> dict:
        name = name.strip()
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        with self._lock, self._connect() as con:
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
        with self._lock, self._connect() as con:
            row = con.execute("SELECT * FROM admins WHERE name=? AND status='ENROLLED'", (name.strip(),)).fetchone()
            if not row:
                raise ValueError('invalid credentials')
            try:
                key = derive_password_key(password, b64d(row['salt']))
                vrk = aes_decrypt(key, b64d(row['vrk_nonce']), b64d(row['vrk_cipher']), b'UStracker/VRK/admin/v1')
                vault = self._read_vault(vrk)
            except Exception as exc:
                raise ValueError('invalid credentials') from exc
            now = self._now()
            session = Session(
                token=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(24), slot=row['slot'], name=row['name'],
                environment=environment, created_at=now, last_human_activity=now, vrk=vrk,
                db_key=b64d(vault[environment]['db_key']), media_key=b64d(vault[environment]['media_key'])
            )
            self._sessions[session.token] = session
            con.execute('INSERT INTO auth_audit(at,actor_slot,action,detail) VALUES(?,?,?,?)',
                        (now.isoformat(), row['slot'], 'LOGIN', json.dumps({'environment': environment})))
            return session

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
        with self._lock, self._connect() as con:
            row = con.execute('SELECT * FROM admins WHERE slot=?', (session.slot,)).fetchone()
            old = derive_password_key(current_password, b64d(row['salt']))
            vrk = aes_decrypt(old, b64d(row['vrk_nonce']), b64d(row['vrk_cipher']), b'UStracker/VRK/admin/v1')
            salt, nonce, cipher = self._create_admin_envelope(vrk, new_password)
            con.execute('UPDATE admins SET salt=?,vrk_nonce=?,vrk_cipher=?,revision=revision+1,updated_at=? WHERE slot=?',
                        (salt, nonce, cipher, self._now().isoformat(), session.slot))
            for token, existing in list(self._sessions.items()):
                if existing.slot == session.slot:
                    self._sessions.pop(token, None)

    def reset_admin(self, session: Session, slot: int, reason: str) -> str:
        if slot == session.slot or slot not in (1, 2, 3) or not reason.strip():
            raise ValueError('invalid reset request')
        with self._lock, self._connect() as con:
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
