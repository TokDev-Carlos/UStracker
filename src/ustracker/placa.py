"""S-05..S-07 — Placa de direção: diz a todos os Servidores onde estão os bancos na nuvem.

O dono escreve um formulário simples:

    #Banco 1
    Endereço Web: https://script.google.com/macros/s/…/exec
    Chave de Conexão: 3f9a…

    #Banco 2
    …

"Publicar placa" transforma isso em ``placa.json``: as chaves de conexão saem CIFRADAS com a chave da
empresa e o arquivo inteiro é ASSINADO (Ed25519) com a chave mestre. O arquivo fica num lugar público
(GitHub). Cada Servidor baixa, confere a assinatura com a chave pública que veio no instalador e usa:
Banco 1 = principal; Banco 2+ = espelhos (recebem cópia de tudo).

Arquivos:
* ``APP_ROOT/Trust/placa-bootstrap.json`` (vai DENTRO do UStracker_install_x64.exe): endereço da placa, chave pública, chave da empresa.
* chave mestre (privada): no banco, cifrada com a VRK (só administradores usam; viaja com a nuvem).
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT = 'ustracker-placa/1'
BOOTSTRAP = ('Trust', 'placa-bootstrap.json')
KEY_SETTING = 'placa_master_key'     # sealed with the VRK, inside the shared database
UTC = timezone.utc


class PlacaError(ValueError):
    pass


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _b64d(s: str) -> bytes:
    return base64.b64decode(s)


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _fold(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


# ----------------------------------------------------------------------------- formulário
def parse_form(text: str) -> list[dict]:
    """'#Banco 1 / Endereço Web: … / Chave de Conexão: …' → [{'n':1,'url':…,'key':…}] (ordem = prioridade)."""
    banks: list[dict] = []
    current: dict | None = None
    for raw in str(text or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        folded = _fold(line)
        m = re.match(r'^#\s*banco\s*(\d+)', folded)
        if m:
            current = {'n': int(m.group(1)), 'url': '', 'key': ''}
            banks.append(current)
            continue
        if line.startswith('#') or current is None or ':' not in line:
            continue
        label, value = line.split(':', 1)
        label = _fold(label)
        value = value.strip()
        if 'endereco' in label or 'url' in label:
            current['url'] = value
        elif 'chave' in label or 'codigo' in label:
            current['key'] = ''.join(value.split())
    banks = [b for b in banks if b['url'] or b['key']]
    for b in banks:
        if not b['url'].startswith('https://') and not b['url'].startswith('http://127.0.0.1'):
            raise PlacaError(f"Banco {b['n']}: o Endereço Web deve começar com https://")
        if len(b['key']) < 16:
            raise PlacaError(f"Banco {b['n']}: Chave de Conexão incompleta")
    if not banks:
        raise PlacaError('informe ao menos o Banco 1')
    banks.sort(key=lambda b: b['n'])
    return banks


def render_form(banks: list[dict]) -> str:
    out = ['# UStracker — bancos de dados em nuvem', '# Banco 1 = principal. Banco 2 em diante = cópias (espelhos).', '']
    for i, b in enumerate(banks, 1):
        out += [f'#Banco {i}', f"Endereço Web: {b.get('url', '')}", f"Chave de Conexão: {b.get('key', '')}", '']
    return '\n'.join(out)


# ----------------------------------------------------------------------------- chaves
def new_master() -> dict:
    """Master signing key (private) + company key that hides the connection keys."""
    private = Ed25519PrivateKey.generate()
    return {
        'private': _b64e(private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())),
        'public': _b64e(private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)),
        'company_key': _b64e(secrets.token_bytes(32)),
    }


def build_placa(banks: list[dict], master: dict, seq: int) -> dict:
    company = AESGCM(_b64d(master['company_key']))
    items = []
    for i, b in enumerate(banks, 1):
        nonce = secrets.token_bytes(12)
        items.append({'n': i, 'url': b['url'], 'key': _b64e(nonce + company.encrypt(nonce, b['key'].encode(), b'UStracker/placa/key'))})
    body = {'format': FORMAT, 'seq': int(seq), 'issued_at': datetime.now(UTC).isoformat(), 'banks': items}
    private = Ed25519PrivateKey.from_private_bytes(_b64d(master['private']))
    return {**body, 'sig': _b64e(private.sign(_canonical(body)))}


def read_placa(placa: dict, bootstrap: dict) -> dict:
    """Verify the signature and reveal the banks. Raises PlacaError on anything wrong."""
    if not isinstance(placa, dict) or placa.get('format') != FORMAT:
        raise PlacaError('placa em formato desconhecido')
    body = {k: v for k, v in placa.items() if k != 'sig'}
    try:
        Ed25519PublicKey.from_public_bytes(_b64d(bootstrap['public'])).verify(_b64d(placa.get('sig') or ''), _canonical(body))
    except Exception as exc:
        raise PlacaError('assinatura da placa inválida (placa ignorada)') from exc
    company = AESGCM(_b64d(bootstrap['company_key']))
    banks = []
    for item in sorted(body.get('banks') or [], key=lambda b: int(b.get('n') or 0)):
        raw = _b64d(item['key'])
        banks.append({'n': int(item['n']), 'url': item['url'], 'key': company.decrypt(raw[:12], raw[12:], b'UStracker/placa/key').decode()})
    if not banks:
        raise PlacaError('placa sem bancos')
    return {'seq': int(body.get('seq') or 0), 'issued_at': body.get('issued_at'), 'banks': banks}


# ----------------------------------------------------------------------------- arquivos
def bootstrap_path(root: Path | str) -> Path:
    return Path(root).joinpath(*BOOTSTRAP)


def load_bootstrap(root: Path | str) -> dict | None:
    path = bootstrap_path(root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if data.get('public') and data.get('company_key') else None
    except Exception:
        return None


def save_bootstrap(root: Path | str, *, url: str, master: dict) -> dict:
    data = {'format': 'ustracker-placa-bootstrap/1', 'placa_url': url.strip(), 'public': master['public'], 'company_key': master['company_key']}
    path = bootstrap_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    tmp.replace(path)
    # Release 2: the build embeds this file inside UStracker_install_x64.exe (no kit folder)
    return data


def fetch_placa(url: str, timeout: float = 20.0, opener=None) -> dict:
    sep = '&' if '?' in url else '?'
    req = urllib.request.Request(f'{url}{sep}t={int(datetime.now().timestamp())}', headers={'Cache-Control': 'no-cache'})
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise PlacaError(f'não foi possível baixar a placa (o endereço respondeu {exc.code})') from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise PlacaError('não foi possível baixar a placa (sem internet ou endereço errado)') from exc
    except ValueError as exc:
        raise PlacaError('o endereço da placa não devolveu uma placa válida') from exc


def github_publish(placa: dict, *, repo: str, path: str, token: str, branch: str = 'main', opener=None) -> dict:
    """Optional: write placa.json to GitHub through the contents API (fine-grained token, contents: write)."""
    api = f'https://api.github.com/repos/{repo.strip()}/contents/{path.strip().lstrip("/")}'
    headers = {'Authorization': f'Bearer {token.strip()}', 'Accept': 'application/vnd.github+json', 'User-Agent': 'UStracker'}
    op = opener or urllib.request.build_opener()
    sha = None
    try:
        with op.open(urllib.request.Request(f'{api}?ref={branch}', headers=headers), timeout=20) as resp:
            sha = json.loads(resp.read()).get('sha')
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise PlacaError(f'GitHub respondeu {exc.code} ao ler a placa') from exc
    except (urllib.error.URLError, OSError) as exc:
        raise PlacaError('não foi possível falar com o GitHub (sem internet?)') from exc
    body = {'message': f"UStracker: placa seq {placa.get('seq')}", 'branch': branch,
            'content': _b64e(json.dumps(placa, indent=2, ensure_ascii=False).encode())}
    if sha:
        body['sha'] = sha
    req = urllib.request.Request(api, data=json.dumps(body).encode(), method='PUT', headers={**headers, 'Content-Type': 'application/json'})
    try:
        with op.open(req, timeout=30) as resp:
            out = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise PlacaError(f'GitHub recusou a publicação ({exc.code}); confira o token e o repositório') from exc
    except (urllib.error.URLError, OSError) as exc:
        raise PlacaError('não foi possível falar com o GitHub (sem internet?)') from exc
    return {'committed': True, 'path': out.get('content', {}).get('path')}


def raw_url(repo: str, path: str, branch: str = 'main') -> str:
    return f'https://raw.githubusercontent.com/{repo.strip()}/{branch}/{path.strip().lstrip("/")}'
