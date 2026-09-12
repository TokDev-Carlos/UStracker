from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Iterable

ROUNDING_POLICY_ID = 'ROUND_V1_HALF_EVEN'


def _to_cents(value: str) -> int:
    try:
        dec = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid money value') from exc
    if not dec.is_finite():
        raise ValueError('money must be finite')
    if dec.as_tuple().exponent < -2:
        raise ValueError('money supports at most 2 decimal places')
    return int((dec * 100).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))


def parse_money_api(value: str | int | Decimal) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return _to_cents(format(value, 'f'))
    text = str(value).strip()
    if ',' in text or not text:
        raise ValueError('API money must use decimal point')
    return _to_cents(text)


def parse_money_ptbr(value: str) -> int:
    text = str(value).strip().replace(' ', '')
    if not text:
        raise ValueError('empty money value')
    if ',' in text:
        if text.count(',') != 1:
            raise ValueError('ambiguous money value')
        integer, frac = text.split(',')
        if len(frac) > 2:
            raise ValueError('money supports at most 2 decimal places')
        integer = integer.replace('.', '')
        normalized = integer + ('.' + frac if frac else '')
    else:
        if text.count('.') > 1:
            raise ValueError('ambiguous money value')
        normalized = text
    return _to_cents(normalized)


def split_cents(total: int, weights: Iterable[int | Decimal]) -> list[int]:
    ws = [Decimal(str(w)) for w in weights]
    if total < 0 or not ws or any(w < 0 for w in ws) or sum(ws) <= 0:
        raise ValueError('invalid split')
    total_weight = sum(ws)
    raw = [Decimal(total) * w / total_weight for w in ws]
    base = [int(x) for x in raw]
    remainder = total - sum(base)
    order = sorted(range(len(ws)), key=lambda i: (raw[i] - base[i], -i), reverse=True)
    for i in order[:remainder]:
        base[i] += 1
    return base


def due_date(competence: str, day: int) -> date:
    try:
        year_s, month_s = competence.split('-', 1)
        year, month = int(year_s), int(month_s)
    except Exception as exc:
        raise ValueError('competence must be YYYY-MM') from exc
    if day < 1 or day > 31:
        raise ValueError('due day must be 1..31')
    last = monthrange(year, month)[1]
    return date(year, month, min(day, last))
