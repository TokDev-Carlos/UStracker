"""U-01..U-05 — pacotes de acesso (Operador, Gerente, Administrador e personalizados).

Uma permissão é um texto "modulo.acao". Administradores (posições 1..3) têm tudo. Usuários comuns
recebem as permissões do pacote. O servidor recusa qualquer rota sem a permissão necessária
(``required_permission``); a tela só esconde o que já seria recusado.
"""
from __future__ import annotations

import re

# (permissão, grupo, rótulo) — a ordem é a da tela de pacotes
PERMISSIONS: list[tuple[str, str, str]] = [
    ('dashboard.view', 'Visão geral', 'Ver indicadores (receita, previsão, clientes, assinaturas)'),
    ('dashboard.full', 'Visão geral', 'Ver despesas, resultado e detalhamento'),
    ('clients.view', 'Clientes', 'Ver'),
    ('clients.edit', 'Clientes', 'Criar e editar'),
    ('clients.delete', 'Clientes', 'Excluir'),
    ('mobility.view', 'Frotas/Veículos', 'Ver'),
    ('mobility.edit', 'Frotas/Veículos', 'Criar, editar e mover'),
    ('mobility.delete', 'Frotas/Veículos', 'Excluir'),
    ('catalog.view', 'Planos/Produtos', 'Ver'),
    ('catalog.edit', 'Planos/Produtos', 'Criar e editar'),
    ('catalog.delete', 'Planos/Produtos', 'Excluir ou arquivar'),
    ('catalog.costs', 'Planos/Produtos', 'Ver custo e margem'),
    ('commercial.view', 'Comercial', 'Ver assinaturas e compras'),
    ('commercial.edit', 'Comercial', 'Criar, ajustar, pausar e reativar'),
    ('commercial.delete', 'Comercial', 'Cancelar assinaturas e compras'),
    ('finance.view', 'Financeiro', 'Ver recebimentos'),
    ('finance.pay', 'Financeiro', 'Registrar pagamento'),
    ('finance.reverse', 'Financeiro', 'Estornar pagamento'),
    ('expenses.view', 'Despesas', 'Ver'),
    ('expenses.edit', 'Despesas', 'Lançar e pagar'),
    ('expenses.delete', 'Despesas', 'Excluir'),
    ('fiscal.view', 'Fiscal', 'Ver'),
    ('fiscal.edit', 'Fiscal', 'Lançar'),
    ('files.view', 'Fotos/Arquivos', 'Ver'),
    ('files.edit', 'Fotos/Arquivos', 'Enviar e trocar'),
    ('files.delete', 'Fotos/Arquivos', 'Remover'),
    ('reports.view', 'Relatórios', 'Baixar relatórios'),
    ('trash.view', 'Lixeira', 'Ver'),
    ('trash.restore', 'Lixeira', 'Restaurar'),
    ('system', 'Sistema', 'Administração (usuários, backup, nuvem, servidores)'),
]
ALL = frozenset(p for p, _, _ in PERMISSIONS)

OPERADOR = frozenset({
    'dashboard.view', 'clients.view', 'clients.edit', 'mobility.view', 'mobility.edit', 'catalog.view',
    'commercial.view', 'commercial.edit', 'finance.view', 'finance.pay', 'files.view', 'files.edit',
})
GERENTE = ALL - {'system'}

BUILTIN_PACKAGES = {
    'OPERADOR': ('Operador', 'Cria e atualiza dados. Não exclui, não estorna e não vê despesas nem custos.', OPERADOR),
    'GERENTE': ('Gerente', 'Tudo, inclusive excluir, estornar, despesas e relatórios. Sem o menu Sistema.', GERENTE),
}
ADMIN_TITLE = 'Administrador'

# menu → permissão para mostrar
NAV_PERMISSION = {
    'dashboard': 'dashboard.view', 'clients': 'clients.view', 'mobility': 'mobility.view', 'catalog': 'catalog.view',
    'commercial': 'commercial.view', 'finance': ('finance.view', 'expenses.view', 'fiscal.view'), 'files': 'files.view',
    'reports': 'reports.view', 'system': ('system', 'trash.view'),
}


def clean(perms) -> frozenset:
    return frozenset(p for p in (perms or []) if p in ALL)


def has(perms, need) -> bool:
    if need is None:
        return True
    if isinstance(need, (tuple, list, set, frozenset)):
        return any(p in perms for p in need)
    return need in perms


ANY = None  # any logged-in user
_EDIT_MEDIA = ('files.edit', 'clients.edit', 'mobility.edit')
_VIEW_MEDIA = ('files.view', 'clients.view', 'mobility.view', 'commercial.view')

# (métodos, regex do caminho depois de /api/v1, permissão). A primeira que casar vale.
_RULES: list[tuple[str, str, object]] = [
    ('*', r'/(health|public|auth/(csrf|login|logout|me|setup-status|bootstrap|enroll|change-password))$', ANY),
    ('*', r'/(system/shutdown|shell/detach)$', ANY),
    ('GET', r'/(search|entities/clients)$', ANY),
    ('GET', r'/cloud/status$', ANY),
    ('GET', r'/dashboard$', 'dashboard.view'),
    ('GET', r'/dashboard/drilldown$', 'dashboard.full'),
    ('POST', r'/clients/archive$', 'clients.delete'),
    ('GET', r'/clients(/.*)?$', 'clients.view'),
    ('POST|PATCH|PUT', r'/clients(/.*)?$', 'clients.edit'),
    ('GET', r'/(fleets|vehicles|mobility|vehicle-transfer-cases)(/.*)?$', 'mobility.view'),
    ('DELETE', r'/(fleets|vehicles)/[^/]+$', 'mobility.delete'),
    ('POST|PATCH|PUT', r'/(fleets|vehicles|vehicle-transfer-cases)(/.*)?$', 'mobility.edit'),
    ('GET', r'/catalog(/.*)?$', ('catalog.view', 'commercial.view')),
    ('DELETE', r'/catalog/[^/]+$', 'catalog.delete'),
    ('POST|PATCH|PUT', r'/catalog(/.*)?$', 'catalog.edit'),
    ('POST', r'/(billing/payments|payments)$', 'finance.pay'),
    ('POST', r'/payments/[^/]+/reverse$', 'finance.reverse'),
    ('POST', r'/disbursements/[^/]+/reverse$', 'expenses.delete'),
    ('GET', r'/finance$', ('finance.view', 'expenses.view', 'fiscal.view')),
    ('GET', r'/payments(/.*)?$', 'finance.view'),
    ('GET', r'/billing(/.*)?$', ('finance.view', 'commercial.view')),
    ('GET', r'/(subscriptions|commercial|direct-sales|credits|charges)(/.*)?$', 'commercial.view'),
    ('POST|PATCH|PUT', r'/(subscriptions|commercial|direct-sales|credits|charges)(/.*)?$', 'commercial.edit'),
    ('DELETE', r'/expenses/[^/]+$', 'expenses.delete'),
    ('GET', r'/expenses(/.*)?$', 'expenses.view'),
    ('POST|PATCH|PUT', r'/expenses(/.*)?$', 'expenses.edit'),
    ('GET', r'/fiscal(/.*)?$', 'fiscal.view'),
    ('POST|PATCH|PUT', r'/fiscal(/.*)?$', 'fiscal.edit'),
    ('GET', r'/(media|attachments)(/.*)?$', _VIEW_MEDIA),
    ('DELETE', r'/media/[^/]+$', ('files.delete',) + _EDIT_MEDIA),
    ('POST', r'/(media|attachments)(/.*)?$', _EDIT_MEDIA),
    ('GET', r'/reports/.*$', 'reports.view'),
    ('GET', r'/trash$', 'trash.view'),
    ('POST', r'/trash/[^/]+/restore$', 'trash.restore'),
    ('GET', r'/settings$', ANY),
]
_COMPILED = [(set(m.split('|')) if m != '*' else None, re.compile(rx), perm) for m, rx, perm in _RULES]
SYSTEM_ONLY = 'system'


def required_permission(method: str, path: str):
    """Permission needed for an /api/v1 route. Unlisted routes are Administration only."""
    sub = path[len('/api/v1'):] if path.startswith('/api/v1') else path
    method = method.upper()
    for methods, rx, perm in _COMPILED:
        if (methods is None or method in methods) and rx.match(sub):
            return perm
    return SYSTEM_ONLY


def _strip(obj, words: tuple[str, ...]):
    if isinstance(obj, dict):
        return {k: _strip(v, words) for k, v in obj.items() if not any(w in str(k).lower() for w in words)}
    if isinstance(obj, list):
        return [_strip(v, words) for v in obj]
    return obj


def strip_costs(obj):
    """Remove cost/margin fields (packages without catalog.costs)."""
    return _strip(obj, ('cost', 'margin'))


def restrict_dashboard(obj):
    """Visão geral sem despesas, resultado, custos e acumulados (packages without dashboard.full)."""
    out = _strip(obj, ('expense', 'spent', 'result', 'cost', 'margin', 'accumulated', 'disburse', 'profit'))
    if isinstance(out, dict):
        out['restricted'] = True
    return out


def describe() -> dict:
    return {
        'permissions': [{'key': k, 'group': g, 'label': label} for k, g, label in PERMISSIONS],
        'nav': {k: (list(v) if isinstance(v, tuple) else [v]) for k, v in NAV_PERMISSION.items()},
    }
