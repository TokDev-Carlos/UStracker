"""AJ-02 — vehicle category normalization (single semantic map for every screen).

The stored ``vehicles.type`` text is never rewritten: custom or unknown types are
classified as ``OTHER`` and keep their original text for display.
"""
from __future__ import annotations

import unicodedata

# key, plural label, singular label, icon registry key
CATEGORIES = (
    ('CAR', 'Carros', 'Carro', 'vehicle.car'),
    ('TRUCK', 'Caminhões', 'Caminhão', 'vehicle.truck'),
    ('BOAT', 'Embarcações', 'Embarcação', 'vehicle.boat'),
    ('AIRCRAFT', 'Aeronaves', 'Aeronave', 'vehicle.aircraft'),
    ('OTHER', 'Outros', 'Outro', 'vehicle.other'),
)
CATEGORY_KEYS = tuple(c[0] for c in CATEGORIES)
_BY_KEY = {c[0]: c for c in CATEGORIES}

_ALIASES = {
    'CAR': {'carro', 'carros', 'automovel', 'automoveis', 'auto', 'veiculo leve', 'utilitario', 'pickup', 'picape',
            'van', 'suv', 'sedan', 'hatch', 'car'},
    'TRUCK': {'caminhao', 'caminhoes', 'carreta', 'cavalo mecanico', 'cavalo', 'truck', 'bitrem', 'rodotrem',
              'caminhonete pesada', 'onibus', 'micro-onibus', 'microonibus'},
    'BOAT': {'embarcacao', 'embarcacoes', 'barco', 'lancha', 'navio', 'jet ski', 'jetski', 'jet-ski', 'veleiro',
             'iate', 'balsa', 'boat'},
    'AIRCRAFT': {'aeronave', 'aeronaves', 'aviao', 'avioes', 'helicoptero', 'helicopteros', 'drone', 'planador',
                 'aircraft'},
}


def _fold(value) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    return ' '.join(''.join(ch for ch in text if not unicodedata.combining(ch)).casefold().split())


def normalize_vehicle_category(vehicle_type) -> str:
    key = _fold(vehicle_type)
    if not key:
        return 'OTHER'
    for category, aliases in _ALIASES.items():
        if key in aliases:
            return category
    return 'OTHER'


def category_label(category: str, plural: bool = False) -> str:
    row = _BY_KEY.get(category, _BY_KEY['OTHER'])
    return row[1] if plural else row[2]


def annotate_vehicle(rec: dict, type_key: str = 'type', prefix: str = '') -> dict:
    """Adds ``category``/``category_label``/``category_icon`` (optionally prefixed) without touching ``type``."""
    category = normalize_vehicle_category(rec.get(type_key))
    rec[prefix + 'category'] = category
    rec[prefix + 'category_label'] = category_label(category)
    rec[prefix + 'category_icon'] = _BY_KEY[category][3]
    return rec


def empty_breakdown() -> dict:
    return {'total': 0, 'categories': [
        {'key': key, 'label': plural, 'singular': singular, 'icon': icon, 'count': 0, 'custom_types': []}
        for key, plural, singular, icon in CATEGORIES
    ]}


def breakdown_from_rows(rows) -> dict:
    """rows: iterable of (type, count)."""
    result = empty_breakdown()
    by_key = {item['key']: item for item in result['categories']}
    for vehicle_type, count in rows:
        count = int(count or 0)
        category = normalize_vehicle_category(vehicle_type)
        bucket = by_key[category]
        bucket['count'] += count
        if category == 'OTHER' and str(vehicle_type or '').strip() and vehicle_type not in bucket['custom_types']:
            bucket['custom_types'].append(str(vehicle_type).strip())
    result['total'] = sum(item['count'] for item in result['categories'])
    return result


def vehicle_breakdown(db, client_id: str | None = None) -> dict:
    sql = 'SELECT type,COUNT(*) AS n FROM vehicles WHERE archived=0'
    args: tuple = ()
    if client_id:
        sql += ' AND client_id=?'
        args = (client_id,)
    sql += ' GROUP BY type'
    return breakdown_from_rows((row['type'], row['n']) for row in db.query(sql, args))


# AJ-05 — fleet group (declared category of a fleet). MIXED accepts every category.
FLEET_GROUPS = CATEGORY_KEYS + ('MIXED',)


def fleet_group_label(group: str | None, plural: bool = True) -> str:
    if not group or group == 'MIXED':
        return 'Misto'
    return category_label(group, plural)


def validate_fleet_group(value) -> str:
    group = str(value or 'MIXED').strip().upper() or 'MIXED'
    if group not in FLEET_GROUPS:
        raise ValueError('invalid fleet group')
    return group


def ensure_vehicle_fits_fleet(fleet_group: str | None, vehicle_type) -> None:
    group = fleet_group or 'MIXED'
    if group != 'MIXED' and normalize_vehicle_category(vehicle_type) != group:
        raise ValueError('vehicle category does not match fleet group')
