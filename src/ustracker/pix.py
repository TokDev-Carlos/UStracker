"""2.8.0 — PIX estático da empresa (BR Code do Banco Central) e QR Code.

Sem banco intermediário: o código leva a chave PIX da empresa, o nome, a cidade, o valor e um
identificador (txid). O recebimento é conferido pela empresa e lançado no sistema.
Especificação: Manual de Padrões para Iniciação do Pix (BR Code, EMV-MPM), CRC16-CCITT-FALSE.
"""
from __future__ import annotations

import re
import unicodedata

from ._vendor import segno

EVP = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _cpf_ok(d: str) -> bool:
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def _cnpj_ok(d: str) -> bool:
    if len(d) != 14 or d == d[0] * 14:
        return False
    for n, w in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]), (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        r = sum(int(d[i]) * w[i] for i in range(n)) % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


def normalize_key(key: str) -> tuple[str, str]:
    """Tipo e forma correta da chave PIX (CPF, CNPJ, telefone +55, e-mail ou aleatória)."""
    raw = str(key or '').strip()
    if EVP.match(raw.lower()):
        return 'ALEATORIA', raw.lower()
    if EMAIL.match(raw):
        return 'EMAIL', raw.lower()
    digits = re.sub(r'\D', '', raw)
    if raw.startswith('+') and 12 <= len(digits) <= 13:
        return 'TELEFONE', '+' + digits
    phone_like = '(' in raw or re.match(r'^\d{2}\s', raw) or re.search(r'\d{4,5}-\d{4}$', raw)
    if len(digits) == 11 and _cpf_ok(digits) and not phone_like:
        return 'CPF', digits
    if len(digits) == 14 and _cnpj_ok(digits):
        return 'CNPJ', digits
    if len(digits) in (10, 11):
        return 'TELEFONE', '+55' + digits
    raise ValueError('invalid pix key')


def _plain(text: str, limit: int) -> str:
    """Sem acentos e só caracteres aceitos pelo BR Code."""
    s = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^A-Za-z0-9 .,/&-]', '', s).strip()
    return re.sub(r'\s+', ' ', s)[:limit].strip()


def _f(tag: str, value: str) -> str:
    return f'{tag}{len(value):02d}{value}'


def crc16(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f'{crc:04X}'


def txid_from(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', str(text or ''))[:25] or '***'


def br_code(key: str, name: str, city: str, amount_cents: int | None = None, txid: str = '***', description: str | None = None) -> str:
    """Código "copia e cola" do PIX estático."""
    _, k = normalize_key(key)
    merchant = _f('00', 'br.gov.bcb.pix') + _f('01', k)
    if description:
        merchant += _f('02', _plain(description, 40))
    name_p, city_p = _plain(name, 25), _plain(city, 15)
    if not name_p or not city_p:
        raise ValueError('pix name and city required')
    out = _f('00', '01') + _f('26', merchant) + _f('52', '0000') + _f('53', '986')
    if amount_cents:
        out += _f('54', f'{int(amount_cents) / 100:.2f}')
    out += _f('58', 'BR') + _f('59', name_p) + _f('60', city_p)
    out += _f('62', _f('05', txid_from(txid) if txid != '***' else '***'))
    out += '6304'
    return out + crc16(out)


def qr_matrix(payload: str, border: int = 4) -> list[list[bool]]:
    """Módulos do QR Code (True = escuro), com a margem branca."""
    qr = segno.make(payload, error='m', micro=False)
    return [[bool(v) for v in row] for row in qr.matrix_iter(scale=1, border=border)]
