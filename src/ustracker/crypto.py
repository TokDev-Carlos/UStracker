from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii')


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode('ascii'))


def random_bytes(size: int = 32) -> bytes:
    return os.urandom(size)


def derive_password_key(password: str, salt: bytes) -> bytes:
    if len(password) < 4:
        raise ValueError('secret must have at least 4 characters')
    # PECSUS D15/T04: scrypt N=131072,r=8,p=1.
    kdf = Scrypt(salt=salt, length=32, n=131072, r=8, p=1)
    return kdf.derive(password.encode('utf-8'))


def derive_ticket_key(ticket: str, salt: bytes) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b'UStracker/enrollment/v1')
    return hkdf.derive(ticket.encode('utf-8'))


def derive_backup_key(vrk: bytes, salt: bytes) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b'UStracker/local-backup/v1')
    return hkdf.derive(vrk)


def aes_encrypt(key: bytes, plaintext: bytes, aad: bytes = b'') -> tuple[bytes, bytes]:
    nonce = random_bytes(12)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b'') -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext, aad)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
