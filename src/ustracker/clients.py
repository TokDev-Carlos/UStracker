from __future__ import annotations

import re
from typing import Any

DOCUMENT_TYPES = {'CPF', 'RG', 'CNH', 'CNPJ'}


def normalize_document_number(value: Any) -> str:
    return re.sub(r'[^0-9A-Za-z]', '', str(value or '')).upper()


def _cpf_valid(number: str) -> bool:
    if len(number) != 11 or not number.isdigit() or len(set(number)) == 1:
        return False
    digits = [int(c) for c in number]
    for index in (9, 10):
        weight = index + 1
        total = sum(digits[i] * (weight - i) for i in range(index))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if digits[index] != check:
            return False
    return True


def _cnpj_valid(number: str) -> bool:
    if len(number) != 14 or not number.isdigit() or len(set(number)) == 1:
        return False
    digits = [int(c) for c in number]
    for size in (12, 13):
        weights = list(range(size - 7, 1, -1)) + list(range(9, 1, -1))
        total = sum(d * w for d, w in zip(digits[:size], weights))
        check = 0 if total % 11 < 2 else 11 - total % 11
        if digits[size] != check:
            return False
    return True


def infer_document_type(number: Any) -> str:
    normalized = normalize_document_number(number)
    if normalized.isdigit() and len(normalized) == 11 and _cpf_valid(normalized):
        return 'CPF'
    if normalized.isdigit() and len(normalized) == 14 and _cnpj_valid(normalized):
        return 'CNPJ'
    return 'RG'


def validate_document(payload: dict) -> dict:
    dtype = str(payload.get('type') or '').strip().upper()
    number = str(payload.get('number') or '').strip()
    if dtype not in DOCUMENT_TYPES:
        raise ValueError('document type must be CPF, CNPJ, RG or CNH')
    normalized = normalize_document_number(number)
    if not normalized:
        raise ValueError('document number required')
    if dtype == 'CPF' and not _cpf_valid(normalized):
        raise ValueError('invalid CPF')
    if dtype == 'CNPJ' and not _cnpj_valid(normalized):
        raise ValueError('invalid CNPJ')
    if dtype == 'CNH' and (not normalized.isdigit() or len(normalized) != 11):
        raise ValueError('invalid CNH')
    if dtype == 'RG' and not (5 <= len(normalized) <= 20):
        raise ValueError('invalid RG')
    return {
        'type': dtype,
        'number': number,
        'normalized_number': normalized,
        'is_primary': 1 if payload.get('is_primary') else 0,
    }


def documents_from_payload(payload: dict) -> list[dict]:
    docs = payload.get('documents')
    if docs is None:
        legacy = str(payload.get('document') or '').strip()
        if not legacy:
            return []
        docs = [{'type': payload.get('document_type') or infer_document_type(legacy), 'number': legacy, 'is_primary': True}]
    if not isinstance(docs, list):
        raise ValueError('documents must be a list')
    result = [validate_document(dict(doc)) for doc in docs]
    if result and not any(doc['is_primary'] for doc in result):
        result[0]['is_primary'] = 1
    return result


def companies_from_payload(payload: dict) -> list[dict]:
    companies = payload.get('companies')
    if companies is None:
        legal_name = str(payload.get('company_legal_name') or '').strip()
        trade_name = str(payload.get('company_trade_name') or '').strip() or None
        companies = [{'legal_name': legal_name, 'trade_name': trade_name, 'is_primary': True}] if legal_name else []
    if not isinstance(companies, list):
        raise ValueError('companies must be a list')
    result = []
    for company in companies:
        legal_name = str(company.get('legal_name') or '').strip()
        if not legal_name:
            raise ValueError('company legal_name required')
        result.append({
            'legal_name': legal_name,
            'trade_name': str(company.get('trade_name') or '').strip() or None,
            'document': str(company.get('document') or '').strip() or None,
            'normalized_document': normalize_document_number(company.get('document')) or None,
            'is_primary': 1 if company.get('is_primary') else 0,
        })
    if result and not any(company['is_primary'] for company in result):
        result[0]['is_primary'] = 1
    return result


def has_contact(payload: dict, *, existing_email: str | None = None, existing_phone: str | None = None) -> bool:
    email = str(payload.get('email', existing_email) or '').strip()
    phone = str(payload.get('phone', existing_phone) or '').strip()
    return bool(email or phone)
