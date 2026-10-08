"""2.5.0 — cadastro global de usuários (um login vale em todos os computadores da empresa).

A nuvem guarda só texto cifrado: a chave do registro é HMAC(chave do cadastro, login) e o conteúdo é
AES-GCM(chave do cadastro). A chave do cadastro sai da chave da empresa (HKDF) e nunca vai para a nuvem.
A senha nunca sai do computador: o registro leva só o envelope do VRK (scrypt), igual à cópia local.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import unicodedata

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .crypto import aes_decrypt, aes_encrypt, b64d, b64e, canonical_json

LOGIN_RE = re.compile(r'^[a-z0-9._-]{3,32}$')
OFFLINE_DAYS = 1
LOGICAL_ERRORS = ('LOGIN_EXISTS', 'CONFLICT', 'DELETED')  # a nuvem respondeu; o resto = sem nuvem


def normalize_login(text: str) -> str:
    """Minúsculo, sem acento, sem espaços nas pontas; a-z 0-9 . _ - ; 3 a 32."""
    plain = unicodedata.normalize('NFD', str(text or '').strip())
    plain = ''.join(c for c in plain if unicodedata.category(c) != 'Mn').lower()
    if not LOGIN_RE.match(plain):
        raise ValueError('invalid login: use 3 to 32 letters, numbers, dot, dash or underscore')
    return plain


def dir_key(company_key: str) -> bytes:
    if not company_key:
        raise ValueError('company key required')
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b'UStracker/users', info=b'UStracker/users-dir/v1').derive(company_key.encode('utf-8'))


def login_key(dk: bytes, login: str) -> str:
    return hmac.new(dk, ('login\n' + normalize_login(login)).encode('utf-8'), hashlib.sha256).hexdigest()


def seal(dk: bytes, key: str, value: dict) -> str:
    nonce, cipher = aes_encrypt(dk, canonical_json(value), ('UStracker/users/' + key).encode())
    return b64e(nonce + cipher)


def open_record(dk: bytes, key: str, text: str) -> dict:
    raw = b64d(text)
    return json.loads(aes_decrypt(dk, raw[:12], raw[12:], ('UStracker/users/' + key).encode()).decode('utf-8'))


# ---------------------------------------------------------------- segredo da máquina (DPAPI no Windows)
def protect(data: bytes) -> str:
    if os.name == 'nt':
        try:
            return 'dpapi:' + b64e(_dpapi(data, True))
        except Exception:
            pass
    return 'plain:' + b64e(data)


def unprotect(text: str) -> bytes:
    kind, _, body = str(text).partition(':')
    if kind == 'dpapi':
        return _dpapi(b64d(body), False)
    return b64d(body)


def _dpapi(data: bytes, encrypt: bool) -> bytes:  # pragma: no cover - Windows only
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    src = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = BLOB()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if encrypt else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out)):  # UI_FORBIDDEN
        raise OSError('DPAPI failed')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


class Directory:
    """Cliente do cadastro global (ações users_get / user_put do Apps Script)."""

    def __init__(self, url: str, secret: str, dk: bytes):
        self.url, self.secret, self.dk = url, secret, dk

    def _client(self):
        from .cloud import CloudClient
        return CloudClient(self.url, self.secret, timeout=20)

    def get(self, since: int) -> dict:
        return self._client().call('users_get', {'since': int(since)}, retries=1)

    def put(self, key: str, value: dict, expected_rev: int, deleted: bool = False) -> int:
        out = self._client().call('user_put', {'key': key, 'record': seal(self.dk, key, value),
                                               'expected_rev': int(expected_rev), 'deleted': bool(deleted)}, retries=1)
        return int(out['rev'])
