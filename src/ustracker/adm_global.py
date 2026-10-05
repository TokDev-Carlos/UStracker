"""G-04 — Adm Global: um acesso do dono que entra em qualquer instalação do UStracker.

* **Token Mestre** (repositório privado ``acesso-UStracker``): status (ativo/revogado), as chaves do Adm Global
  cifradas com o PIN e a assinatura Ed25519. Nunca contém o PIN.
* **Trust/adm-global.json** (vai no instalador): nome de acesso, chaves PÚBLICAS, endereço do Token Mestre e o
  token *só de leitura* desse repositório.
* Cada instalação guarda a VRK (chave dos dados) cifrada para a chave pública do Adm Global (X25519). Só quem
  abre o Token Mestre com o PIN consegue a chave privada que destrava.
* **Passe** (pendrive ou envio remoto): o mesmo Token Mestre com validade de 1 dia, assinado; serve sem internet.
* **Pergunta falsa**: depois de login + PIN o sistema faz uma pergunta qualquer; a resposta certa é o próprio PIN.
  Erros mostram pistas inventadas (nunca ligadas ao PIN) e contam para o bloqueio de 30 minutos.
"""
from __future__ import annotations

import base64
import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

TRUST_FILE = ('Trust', 'adm-global.json')
PASS_FILE = ('Trust', 'passe-adm-global.json')
TOKEN_FORMAT = 'ustracker-token-mestre/1'
DEFAULT_URL = 'https://api.github.com/repos/TokDev-Carlos/acesso-UStracker/contents/token-mestre.json'
TRUST_FORMAT = 'ustracker-adm-global/1'
SCRYPT_N = 2 ** 16
LOCK_ATTEMPTS = 5
LOCK_MINUTES = 30
UTC = timezone.utc
AAD_KEYS = b'UStracker/adm-global/keys/v1'
AAD_WRAP = b'UStracker/adm-global/vrk/v1'


class AccessDenied(ValueError):
    pass


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _b64d(s: str) -> bytes:
    return base64.b64decode(s)


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _raw(key) -> bytes:
    if hasattr(key, 'private_bytes'):
        return key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _pin_key(pin: str, salt: bytes, n: int = SCRYPT_N) -> bytes:
    pin = str(pin or '')
    if len(pin) < 4:
        raise AccessDenied('invalid credentials')
    return Scrypt(salt=salt, length=32, n=n, r=8, p=1).derive(pin.encode('utf-8'))


def _now() -> datetime:
    return datetime.now(UTC)


# ----------------------------------------------------------------------------- Token Mestre
def _seal_keys(keys: dict, pin: str) -> tuple[dict, dict]:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    plain = _canonical({'x': keys['x_priv'], 'ed': keys['ed_priv']})
    cipher = AESGCM(_pin_key(pin, salt)).encrypt(nonce, plain, AAD_KEYS)
    return {'salt': _b64e(salt), 'n': SCRYPT_N}, {'nonce': _b64e(nonce), 'cipher': _b64e(cipher)}


def _sign(body: dict, keys: dict) -> dict:
    priv = Ed25519PrivateKey.from_private_bytes(_b64d(keys['ed_priv']))
    return {**body, 'sig': _b64e(priv.sign(_canonical(body)))}


def create(login: str, pin: str, *, url: str, read_token: str) -> tuple[dict, dict, dict]:
    """First setup. Returns (trust for the installer, Token Mestre for the private repo, opened keys)."""
    login = str(login or '').strip()
    if not login:
        raise ValueError('login is required')
    x, ed = X25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    keys = {'x_priv': _b64e(_raw(x)), 'x_pub': _b64e(_raw(x.public_key())),
            'ed_priv': _b64e(_raw(ed)), 'ed_pub': _b64e(_raw(ed.public_key()))}
    trust = {'format': TRUST_FORMAT, 'login': login, 'x_pub': keys['x_pub'], 'ed_pub': keys['ed_pub'],
             'url': url, 'read_token': read_token}
    return trust, change_pin({'login': login}, keys, pin), keys


def change_pin(token: dict, keys: dict, new_pin: str, status: str = 'active') -> dict:
    kdf, sealed = _seal_keys(keys, new_pin)
    body = {'format': TOKEN_FORMAT, 'kind': 'online', 'login': token['login'], 'status': status,
            'issued_at': _now().isoformat(), 'kdf': kdf, 'keys': sealed}
    return _sign(body, keys)


def make_pass(token: dict, keys: dict, hours: float = 24) -> dict:
    body = {k: v for k, v in token.items() if k != 'sig'}
    body.update(kind='pass', issued_at=_now().isoformat(), expires_at=(_now() + timedelta(hours=hours)).isoformat())
    return _sign(body, keys)


def verify(token: dict, trust: dict, *, offline: bool = False) -> dict:
    """Signature, owner, status and (for a pass) validity. Raises AccessDenied."""
    if not isinstance(token, dict) or token.get('format') != TOKEN_FORMAT:
        raise AccessDenied('token em formato desconhecido')
    body = {k: v for k, v in token.items() if k != 'sig'}
    try:
        Ed25519PublicKey.from_public_bytes(_b64d(trust['ed_pub'])).verify(_b64d(token.get('sig') or ''), _canonical(body))
    except Exception as exc:
        raise AccessDenied('assinatura inválida') from exc
    if str(token.get('login', '')).casefold() != str(trust.get('login', '')).casefold():
        raise AccessDenied('token de outro acesso')
    if token.get('status') != 'active':
        raise AccessDenied('acesso revogado')
    if offline:
        if token.get('kind') != 'pass':
            raise AccessDenied('passe inválido')
        if datetime.fromisoformat(token['expires_at']) <= _now():
            raise AccessDenied('passe vencido')
    elif token.get('kind') != 'online':
        raise AccessDenied('token inválido')
    return token


def open_keys(token: dict, pin: str, trust: dict) -> dict:
    try:
        kdf, sealed = token['kdf'], token['keys']
        plain = AESGCM(_pin_key(pin, _b64d(kdf['salt']), int(kdf.get('n') or SCRYPT_N))).decrypt(
            _b64d(sealed['nonce']), _b64d(sealed['cipher']), AAD_KEYS)
        data = json.loads(plain)
        x = X25519PrivateKey.from_private_bytes(_b64d(data['x']))
        ed = Ed25519PrivateKey.from_private_bytes(_b64d(data['ed']))
    except AccessDenied:
        raise
    except Exception as exc:
        raise AccessDenied('invalid credentials') from exc
    keys = {'x_priv': data['x'], 'x_pub': _b64e(_raw(x.public_key())), 'ed_priv': data['ed'], 'ed_pub': _b64e(_raw(ed.public_key()))}
    if keys['x_pub'] != trust['x_pub'] or keys['ed_pub'] != trust['ed_pub']:
        raise AccessDenied('invalid credentials')
    return keys


# ----------------------------------------------------------------------------- VRK para o Adm Global
def _wrap_key(shared: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=AAD_WRAP).derive(shared)


def wrap(vrk: bytes, trust: dict) -> dict:
    eph = X25519PrivateKey.generate()
    shared = eph.exchange(X25519PublicKey.from_public_bytes(_b64d(trust['x_pub'])))
    nonce = secrets.token_bytes(12)
    return {'x_pub': trust['x_pub'], 'eph': _b64e(_raw(eph.public_key())), 'nonce': _b64e(nonce),
            'cipher': _b64e(AESGCM(_wrap_key(shared)).encrypt(nonce, vrk, AAD_WRAP))}


def unwrap(wrapped: dict, keys: dict) -> bytes:
    try:
        priv = X25519PrivateKey.from_private_bytes(_b64d(keys['x_priv']))
        shared = priv.exchange(X25519PublicKey.from_public_bytes(_b64d(wrapped['eph'])))
        return AESGCM(_wrap_key(shared)).decrypt(_b64d(wrapped['nonce']), _b64d(wrapped['cipher']), AAD_WRAP)
    except Exception as exc:
        raise AccessDenied('invalid credentials') from exc


# ----------------------------------------------------------------------------- pergunta falsa e pistas
QUESTIONS = [
    (1, 'Qual o seu time favorito?', ['Dica: o nome tem 8 letras.', 'Dica: o mascote é uma ave.', 'Dica: já foi campeão nacional mais de uma vez.']),
    (2, 'Qual o nome do seu primeiro animal de estimação?', ['Dica: começa com a letra B.', 'Dica: tem 5 letras.', 'Dica: era um cachorro de pelo claro.']),
    (3, 'Em que cidade você nasceu?', ['Dica: fica no litoral.', 'Dica: o nome é composto.', 'Dica: começa com a letra S.']),
    (4, 'Qual a sua comida preferida?', ['Dica: leva arroz.', 'Dica: é um prato típico.', 'Dica: costuma ser servida aos sábados.']),
    (5, 'Qual o modelo do seu primeiro carro?', ['Dica: era de uma marca alemã.', 'Dica: o nome tem 4 letras.', 'Dica: era da cor prata.']),
    (6, 'Qual o nome da sua escola no ensino fundamental?', ['Dica: tem o nome de um santo.', 'Dica: é uma escola estadual.', 'Dica: são duas palavras.']),
]


def question() -> dict:
    qid, text, _ = secrets.choice(QUESTIONS)
    return {'id': qid, 'question': text}


def hints(qid) -> list[str]:
    for q, _, h in QUESTIONS:
        if str(q) == str(qid):
            return h
    return QUESTIONS[0][2]


def hint_for(qid, attempt: int) -> str:
    h = hints(qid)
    return h[max(0, attempt - 1) % len(h)]


# ----------------------------------------------------------------------------- arquivos e Git
def save_trust(root, trust: dict) -> Path:
    path = Path(root).joinpath(*TRUST_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trust, indent=2), encoding='utf-8')
    return path


def load_trust(root) -> dict | None:
    path = Path(root).joinpath(*TRUST_FILE)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if data.get('format') == TRUST_FORMAT and data.get('login') else None
    except Exception:
        return None


def save_pass(root, token: dict) -> Path:
    path = Path(root).joinpath(*PASS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token, indent=2), encoding='utf-8')
    return path


def load_pass(root) -> dict | None:
    try:
        return json.loads(Path(root).joinpath(*PASS_FILE).read_text(encoding='utf-8'))
    except Exception:
        return None


def fetch_token(trust: dict, timeout: float = 10.0, opener=None) -> dict:
    """Read the Token Mestre from the private repo with the read-only token. Raises OSError when offline."""
    req = urllib.request.Request(trust['url'], headers={
        'Authorization': f"Bearer {trust.get('read_token', '')}", 'Accept': 'application/vnd.github.raw',
        'Cache-Control': 'no-cache', 'User-Agent': 'UStracker'})
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise AccessDenied('token mestre indisponível') from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OSError('offline') from exc


def current_token(root, trust: dict) -> dict:
    """Online Token Mestre; without internet, the 1-day pass in Trust/. Raises AccessDenied."""
    try:
        token = fetch_token(trust)
    except OSError:
        token = load_pass(root)
        if not token:
            raise AccessDenied('sem internet e sem passe')
        return verify(token, trust, offline=True)
    return verify(token, trust)
