"""2.6 Etapa 1 — testes pesados (fora da bateria normal; rodar à mão).

Uso: python tools/dev/testes_pesados.py <pasta_de_saida> [clientes=500] [veiculos=1500]
Sobe uma nuvem simulada (Apps Script em Node) e dois computadores (A e B) com o servidor real (HTTP),
ativa com o Adm Global, gera a massa, mede tempos, confere backup/restauração, nuvem com 2 computadores
e usuários globais. Saída: <pasta>/relatorio.md + resultado.json. Nada toca dados reais.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import socket
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'

OUT = Path(sys.argv[1]).resolve()
N_CLIENTS = int(sys.argv[2]) if len(sys.argv) > 2 else 500
N_VEHICLES = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
os.environ['USTRACKER_BACKUPS'] = str(OUT / 'Documentos_Backups')

import uvicorn  # noqa: E402
from ustracker import adm_global as ag  # noqa: E402
from ustracker.placa import build_placa, new_master, save_bootstrap  # noqa: E402
from ustracker.server import create_app  # noqa: E402
from tests.test_h01_activation import RepoServer, gas  # noqa: E402

PIN = '48291735'


def _crash(t, e, tb):  # erro inesperado: mostra e encerra (servidores em threads não seguram o processo)
    import traceback; traceback.print_exception(t, e, tb); sys.stdout.flush(); os._exit(2)


sys.excepthook = _crash
random.seed(25)
RESULTS: list[dict] = []
TIMES: dict[str, list[float]] = {}


def check(ok: bool, what: str, detail: str = '') -> bool:
    RESULTS.append({'ok': bool(ok), 'what': what, 'detail': detail})
    print(('OK    ' if ok else 'FALHA ') + what + (f' — {detail}' if detail else ''), flush=True)
    return ok


def free_port() -> int:
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close(); return port


class Http:
    """Cliente HTTP com cookies (sessão + CSRF), como o navegador do sistema."""

    def __init__(self, base: str):
        self.base = base; self.cookies = {'us_csrf': 'csrf-' + uuid.uuid4().hex}

    def _hdr(self) -> dict:
        return {'Content-Type': 'application/json', 'X-CSRF-Token': self.cookies.get('us_csrf', ''),
                'X-Operation-ID': uuid.uuid4().hex, 'Cookie': '; '.join(f'{k}={v}' for k, v in self.cookies.items())}

    def req(self, method: str, path: str, body=None, *, label: str | None = None, raw: bool = False):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=self._hdr())
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(r, timeout=600) as resp:
                payload = resp.read(); status = resp.status; headers = resp.headers
        except urllib.error.HTTPError as exc:
            payload = exc.read(); status = exc.code; headers = exc.headers
        dt = time.perf_counter() - t0
        if label:
            TIMES.setdefault(label, []).append(dt)
        for h in headers.get_all('Set-Cookie') or []:
            k, _, v = h.split(';')[0].partition('=')
            if v:
                self.cookies[k.strip()] = v.strip()
        if raw:
            return status, payload
        try:
            return status, json.loads(payload or b'{}')
        except ValueError:
            return status, {'raw': payload[:200].decode('utf-8', 'replace')}

    def ok(self, method, path, body=None, **kw):
        st, out = self.req(method, path, body, **kw)
        if st >= 400:
            raise RuntimeError(f'{method} {path} -> {st} {str(out)[:300]}')
        return out


# ------------------------------------------------------------------ documentos válidos
def cpf(n: int) -> str:
    base = [int(c) for c in f'{100000000 + n * 7919 % 899999999:09d}']
    for _ in range(2):
        s = sum(d * w for d, w in zip(base, range(len(base) + 1, 1, -1)))
        base.append(0 if s % 11 < 2 else 11 - s % 11)
    return ''.join(map(str, base))


def cnpj(n: int) -> str:
    base = [int(c) for c in f'{10000000 + n * 7717 % 89999999:08d}0001']
    for w in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        s = sum(d * k for d, k in zip(base, w))
        base.append(0 if s % 11 < 2 else 11 - s % 11)
    return ''.join(map(str, base))


L = 'ABCDEFGHJKLMNPRSTUVWXYZ'


def plate(i: int) -> str:
    return f'{L[i // 2000 % 23]}{L[i // 80 % 23]}{L[i // 4 % 23]}{i % 10}{L[i % 23]}{(i // 10) % 10}{(i // 100) % 10}'


# ------------------------------------------------------------------ ambiente
def machine(name: str):
    root = OUT / name
    ag.save_trust(root, trust); save_bootstrap(root, url=repo.base + '/placa.json', master=master)
    shutil.copytree(ROOT / 'frontend', root / 'frontend')
    app = create_app(root)
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=2); break
        except Exception:
            time.sleep(.1)
    return root, app, Http(f'http://127.0.0.1:{port}')


def activate(h: Http) -> dict:
    h.req('POST', '/api/v1/auth/activate', {'name': 'crj', 'password': PIN})
    return h.ok('POST', '/api/v1/auth/activate', {'name': 'crj', 'password': PIN, 'answer': PIN}, label='ativação')


def login(base: str, name: str, pw: str) -> Http:
    h = Http(base); h.ok('POST', '/api/v1/auth/login', {'name': name, 'password': pw}, label='login'); return h


def table_counts(root: Path, key: bytes) -> dict:
    from ustracker.db import Database
    from ustracker.reconcile import STABLE_TABLES
    db = Database(root, 'production', key)
    out = {}
    for t in STABLE_TABLES:
        try:
            out[t] = db.one(f'SELECT COUNT(*) FROM {t}')[0]
        except Exception:
            pass
    out['payments_cents'] = db.one('SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE reversed_at IS NULL')[0]
    out['charges_cents'] = db.one('SELECT COALESCE(SUM(amount_cents),0) FROM charges')[0]
    return out


def session_key(app) -> bytes:
    return next(s for s in app.state.auth._sessions.values() if s.environment == 'production').db_key


# ================================================================== início
t_start = time.time()
repo = RepoServer()
trust, token, keys = ag.create('crj', PIN, url=repo.base + '/token-mestre.json', read_token=repo.read_token)
repo.files['token-mestre.json'] = token
master = new_master(); repo.files['company-key.json'] = ag.wrap_company_key(master['company_key'], trust)
proc, url, secret = gas(); repo.files['placa.json'] = build_placa([{'url': url, 'key': secret}], master, 1)

root_a, app_a, A = machine('A')
act = activate(A)
check(bool(act.get('new_company')) and bool(act.get('cloud_reset')), 'A: 1ª ativação cria a empresa e zera a nuvem uma vez')

# ------------------------------------------------------------------ 1. massa
print('== massa de teste', flush=True)
today = date.today()
start = (today.replace(day=1) - timedelta(days=330)).replace(day=1)
plan_car = A.ok('POST', '/api/v1/catalog', {'description': 'Plano Rastreamento Carro', 'category': 'Mensal', 'price': '59.90', 'cost': '18.00'})
plan_moto = A.ok('POST', '/api/v1/catalog', {'description': 'Plano Rastreamento Moto', 'category': 'Mensal', 'price': '39.90', 'cost': '12.00'})
item_inst = A.ok('POST', '/api/v1/catalog', {'description': 'Instalação', 'category': 'Avulsa', 'price': '120.00', 'cost': '40.00'})
n_pj = round(N_CLIENTS * .3); n_pf = N_CLIENTS - n_pj
pj_vehicles = round(N_VEHICLES * .7); pf_vehicles = N_VEHICLES - pj_vehicles
clients = []
t0 = time.time()
for i in range(N_CLIENTS):
    pj = i < n_pj
    doc = {'type': 'CNPJ', 'number': cnpj(i), 'is_primary': True} if pj else {'type': 'CPF', 'number': cpf(i), 'is_primary': True}
    name = f'Transportes Teste {i:04d} LTDA' if pj else f'Cliente Teste {i:04d}'
    c = A.ok('POST', '/api/v1/clients', {'legal_name': name, 'trade_name': name.split(' LTDA')[0], 'documents': [doc],
                                         'phone': f'119{i:08d}', 'email': f'cli{i}@exemplo.com'}, label='criar cliente')
    clients.append({'id': c['id'], 'pj': pj, 'name': name, 'vehicles': [], 'fleet': None})
check(len(clients) == N_CLIENTS, f'{N_CLIENTS} clientes criados ({n_pf} PF / {n_pj} PJ)', f'{time.time() - t0:.0f} s')

vi = 0
t0 = time.time()
pj_list = [c for c in clients if c['pj']]; pf_list = [c for c in clients if not c['pj']]
for k, c in enumerate(pj_list):
    prof = A.ok('GET', f"/api/v1/clients/{c['id']}/profile")
    fl = A.ok('POST', '/api/v1/fleets', {'client_id': c['id'], 'client_company_id': prof['companies'][0]['id'], 'name': f'Frota {k:03d}'}, label='criar frota')
    c['fleet'] = fl['id']
    size = pj_vehicles // n_pj + (1 if k < pj_vehicles % n_pj else 0)
    for _ in range(size):
        v = A.ok('POST', '/api/v1/vehicles', {'client_id': c['id'], 'fleet_id': fl['id'], 'plate': plate(vi), 'type': 'Caminhão' if vi % 5 == 0 else 'Carro',
                                              'brand': 'Marca', 'model': 'Modelo', 'year': 2018 + vi % 8}, label='criar veículo')
        c['vehicles'].append(v['id']); vi += 1
for k, c in enumerate(pf_list):
    size = pf_vehicles // n_pf + (1 if k < pf_vehicles % n_pf else 0)
    for _ in range(size):
        moto = vi % 3 == 0
        v = A.ok('POST', '/api/v1/vehicles', {'client_id': c['id'], 'plate': plate(vi), 'type': 'Moto' if moto else 'Carro',
                                              'brand': 'Honda' if moto else 'Fiat', 'model': 'Modelo', 'year': 2015 + vi % 10}, label='criar veículo')
        c['vehicles'].append(v['id']); c['moto'] = moto; vi += 1
check(vi == N_VEHICLES, f'{N_VEHICLES} veículos criados ({n_pj} frotas)', f'{time.time() - t0:.0f} s')

t0 = time.time(); subs = []
for c in clients:
    if not c['vehicles']:
        continue
    plan = plan_moto if c.get('moto') else plan_car
    body = {'client_id': c['id'], 'start_on': start.isoformat(), 'due_day': 10, 'items': [{'catalog_id': plan['id'], 'quantity': len(c['vehicles'])}]}
    if c['fleet']:
        body['target_fleet_ids'] = [c['fleet']]
    else:
        body['target_vehicle_ids'] = c['vehicles']
    s = A.ok('POST', '/api/v1/subscriptions', body, label='criar assinatura')
    subs.append(s['id'])
sales = 0
for c in random.sample(clients, min(100, len(clients))):
    A.ok('POST', '/api/v1/direct-sales', {'client_id': c['id'], 'sold_on': (start + timedelta(days=random.randint(0, 300))).isoformat(),
                                         'items': [{'catalog_id': item_inst['id'], 'quantity': 1}]}, label='criar venda direta')
    sales += 1
check(len(subs) >= N_CLIENTS * .99, f'{len(subs)} assinaturas + {sales} vendas diretas', f'{time.time() - t0:.0f} s')

t0 = time.time(); pays = 0
months_total = (today.year - start.year) * 12 + today.month - start.month + 1
for sid in subs:
    paid_months = months_total - random.choice([0, 0, 0, 1, 2])  # ~40% com atraso
    done = 0
    while done < paid_months:
        m = min(random.choice([1, 1, 2, 3]), paid_months - done)
        comp = start.replace(year=start.year + (start.month - 1 + done) // 12, month=(start.month - 1 + done) % 12 + 1)
        paid_on = min(today, comp.replace(day=8))
        A.ok('POST', '/api/v1/billing/payments', {'subscription_id': sid, 'months': m, 'paid_on': paid_on.isoformat(), 'method': 'PIX'}, label='registrar pagamento')
        done += m; pays += 1
for k, (cat, desc, amt) in enumerate([('Mensalidades e serviços', 'Plataforma GPS', '1890,00'), ('Pessoal', 'Técnico instalador', '3200,00'),
                                      ('Outros', 'Aluguel sala comercial', '1500,00'), ('Mensalidades e serviços', 'Chips M2M', '980,00')]):
    A.ok('POST', '/api/v1/expenses', {'category': cat, 'description': desc, 'amount': amt, 'repeat': 'MONTHLY', 'date': start.replace(day=5).isoformat()}, label='criar despesa')
A.ok('POST', '/api/v1/expenses/recurring/run')
key_a = session_key(app_a)
base_counts = table_counts(root_a, key_a)
check(pays > 0, f"{pays} pagamentos; {base_counts.get('charges')} cobranças; {base_counts.get('expenses')} despesas", f'{time.time() - t0:.0f} s')
print(base_counts, flush=True)

# ------------------------------------------------------------------ 2. tempos das telas (o que cada tela pede ao servidor)
print('== tempos', flush=True)
cli0 = clients[0]
SCREENS = [
    ('Visão geral', '/api/v1/dashboard'), ('Clientes (lista)', '/api/v1/clients'), ('Ficha do cliente', f"/api/v1/clients/{cli0['id']}/profile"),
    ('Frotas/Veículos', '/api/v1/mobility'), ('Veículos (lista)', '/api/v1/vehicles'), ('Frotas (lista)', '/api/v1/fleets'),
    ('Comercial (assinaturas)', '/api/v1/subscriptions'), ('Cobranças', '/api/v1/charges'), ('Financeiro', '/api/v1/finance'),
    ('Recebimentos', '/api/v1/payments'), ('Despesas', '/api/v1/expenses'), ('Busca global', '/api/v1/search?q=Teste%200042'),
    ('Busca de cliente (autocompletar)', '/api/v1/entities/clients?q=Transp&limit=20'), ('Lixeira', '/api/v1/trash'),
    ('Relatório cobranças (Excel)', '/api/v1/reports/charges.xlsx'), ('Relatório clientes (CSV)', '/api/v1/reports/clients.csv'),
]
slow = []
for label, path in SCREENS:
    for _ in range(3):
        st, _ = A.req('GET', path, label='tela: ' + label, raw=True)
    best = statistics.median(TIMES['tela: ' + label])
    if st != 200 or best > 2.0:
        slow.append(f'{label} {best:.2f}s (HTTP {st})')
check(not slow, 'todas as telas abrem em menos de 2 s (mediana de 3)', '; '.join(slow))
st, cl = A.req('GET', '/api/v1/clients')
listed = len(cl.get('items', [])) if isinstance(cl, dict) else 0
check(listed >= N_CLIENTS, f'lista de Clientes mostra todos ({listed} de {N_CLIENTS})')
st, vh = A.req('GET', '/api/v1/vehicles')
listed_v = len(vh.get('items', [])) if isinstance(vh, dict) else 0
check(listed_v >= N_VEHICLES, f'lista de Veículos mostra todos ({listed_v} de {N_VEHICLES})')
pay_t = statistics.median(TIMES['registrar pagamento'])
check(pay_t < 2.0, f'registrar pagamento (mediana) {pay_t:.2f} s')

# ------------------------------------------------------------------ 2b. telas no navegador (tempo até a tela pronta, com tabelas e filtros)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright:
    print('== navegador', flush=True)
    page_times, js_errors = {}, []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--no-sandbox'])
        ctx = browser.new_context(viewport={'width': 1366, 'height': 860})
        host = urllib.parse.urlsplit(A.base).hostname
        ctx.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in A.cookies.items()])
        pg = ctx.new_page(); pg.on('pageerror', lambda e: js_errors.append(str(e)[:200]))
        pg.goto(A.base + '/'); pg.wait_for_selector('[data-page]', timeout=60000); pg.wait_for_timeout(1500)
        for name, label in [('dashboard', 'Visão geral'), ('clients', 'Clientes'), ('mobility', 'Frotas/Veículos'), ('catalog', 'Planos/Produtos'),
                            ('commercial', 'Comercial'), ('finance', 'Financeiro'), ('reports', 'Relatórios'), ('system', 'Sistema')]:
            vals = []
            for _ in range(2):
                pg.evaluate("document.querySelector('[data-page=dashboard]')?.click()" if name != 'dashboard' else "document.querySelector('[data-page=clients]')?.click()")
                pg.wait_for_function("!document.body.classList.contains('is-navigating')", timeout=60000)
                t0 = time.perf_counter()
                pg.evaluate(f"document.querySelector('[data-page={name}]')?.click()")
                pg.wait_for_function("!document.body.classList.contains('is-navigating')", timeout=60000)
                pg.wait_for_timeout(50)
                vals.append(time.perf_counter() - t0 - .05)
            page_times[label] = min(vals); TIMES.setdefault('navegador: ' + label, []).extend(vals)
        pg.evaluate("document.querySelector('[data-page=clients]').click()")
        pg.wait_for_function("!document.body.classList.contains('is-navigating')", timeout=60000); pg.wait_for_timeout(800)
        t0 = time.perf_counter(); pg.click('th .tf-btn'); pg.wait_for_selector('.tf-pop'); TIMES.setdefault('navegador: abrir filtro (Clientes)', []).append(time.perf_counter() - t0)
        pg.screenshot(path=str(OUT / 'clientes_500.png'))
        pg.keyboard.press('Escape'); pg.mouse.click(5, 5)
        pg.evaluate("document.querySelector('[data-page=system]').click()")
        pg.wait_for_function("!document.body.classList.contains('is-navigating')", timeout=60000)
        pg.click('[data-system-tab=diagnostics]'); pg.wait_for_selector('[data-support-package]', timeout=30000)
        diag_txt = pg.inner_text('[data-system-panel=diagnostics]')
        pg.screenshot(path=str(OUT / 'diagnostico.png'), full_page=True)
        check('Conferida' in diag_txt and 'Espaço livre' in diag_txt, 'navegador: aba Sistema › Diagnóstico abre com a cópia conferida')
        browser.close()
    slow_ui = [f'{k} {v:.2f}s' for k, v in page_times.items() if v > 2.0]
    check(not slow_ui, 'navegador: todas as telas prontas em menos de 2 s', '; '.join(f'{k} {v:.2f}s' for k, v in page_times.items()))
    check(not js_errors, 'navegador: nenhuma falha de tela (erro JS)', '; '.join(js_errors[:3]))

# ------------------------------------------------------------------ 3. backup local: criar, conferir, restaurar em outra pasta
print('== backup local', flush=True)
from ustracker.backup import restore_backup, verify_backup  # noqa: E402
from ustracker.db import Database  # noqa: E402
bk = A.ok('POST', '/api/v1/backups', {}, label='criar backup')
sess_a = next(s for s in app_a.state.auth._sessions.values() if s.environment == 'production')
bk_path = next((root_a / 'UserData').rglob(bk['name']))
info = verify_backup(bk_path, sess_a.vrk)
check(bool(info), 'backup conferido (assinatura e conteúdo)', f"{bk['size'] / 1e6:.1f} MB")
probe = OUT / 'restaurado'; (probe / 'UserData').mkdir(parents=True)
db_probe = Database(probe, 'production', key_a)
restore_backup(probe, db_probe, sess_a.vrk, bk_path)
rest = table_counts(probe, key_a)
check(rest == base_counts, 'restauração em outra pasta: contagens e totais em R$ idênticos', '' if rest == base_counts else f'{rest} != {base_counts}')

# ------------------------------------------------------------------ 4. nuvem: envio, 2º computador, alternância, ponto de restauração
print('== nuvem', flush=True)
t0 = time.time(); A.ok('POST', '/api/v1/cloud/sync', {}, label='enviar à nuvem'); up = time.time() - t0
check(True, f'envio completo à nuvem: {up:.1f} s')
root_b, app_b, B = machine('B')
t0 = time.time(); act_b = activate(B)
check(bool(act_b.get('restored')) and not act_b.get('cloud_reset'), 'B: ativação traz a empresa da nuvem e NÃO zera de novo', f'{time.time() - t0:.1f} s')
key_b = session_key(app_b)
check(table_counts(root_b, key_b) == base_counts, 'B tem exatamente os mesmos dados de A (contagens e R$)')
# "Enviar agora" no 2º computador
st_b, out_b = B.req('POST', '/api/v1/cloud/sync', {}, label='enviar à nuvem (B)')
check(st_b == 200, 'B: botão "Enviar agora" funciona no 2º computador', '' if st_b == 200 else f'HTTP {st_b}: {str(out_b)[:160]}')
sess_b = next(s for s in app_b.state.auth._sessions.values() if s.environment == 'production')


def send(app, sess):  # o que o laço da nuvem faz sozinho: pega a vez, envia e solta
    app.state.cloud.acquire_turn(sess); app.state.cloud.sync_now(sess); app.state.cloud.release_turn(sess)


# alternância: cada computador cria 3 clientes, intercalados (duas pessoas trabalhando ao mesmo tempo)
ids = []; busy = []
ROUNDS = 3
for i in range(ROUNDS):
    for who, h in (('A', A), ('B', B)):
        st, c = h.req('POST', '/api/v1/clients', {'legal_name': f'Alternado {who} {i}', 'documents': [{'type': 'CPF', 'number': cpf(90000 + i * 2 + (who == 'B'))}], 'phone': '11900000000'},
                      label='criar cliente (2 computadores)')
        if st >= 400:
            other = app_b if who == 'A' else app_a
            busy.append(f"{who} rodada {i}: HTTP {st} {str(c)[:90]} | outro: status={other.state.cloud.status} lease_em={other.state.cloud.lease_until - time.time():.0f}s dirty={other.state.cloud.state.get('dirty_since')}")
            print('  ', busy[-1], flush=True)
        else:
            ids.append(c['id'])
send(app_a, sess_a); send(app_b, sess_b)
app_a.state.cloud.pull(sess_a); app_b.state.cloud.pull(sess_b)
ca, cb = table_counts(root_a, key_a), table_counts(root_b, key_b)
alt = TIMES['criar cliente (2 computadores)']
check(not busy, 'alternando A/B: nenhuma gravação recusada por "está salvando agora"', ' || '.join(busy)[:600])
check(ca['clients'] == cb['clients'] == base_counts['clients'] + len(ids), f"{len(ids)} clientes criados alternando A/B: nada perdido (A={ca['clients']}, B={cb['clients']})")
check(max(alt) < 10, f'alternando A/B, cada gravação espera a vez do outro: mediana {statistics.median(alt):.1f} s, máximo {max(alt):.1f} s (meta < 10 s)')
# simultâneo: os dois ao mesmo tempo
errs = []
def burst(h, who):
    for i in range(5):
        try:
            h.ok('POST', '/api/v1/clients', {'legal_name': f'Simultaneo {who} {i}', 'documents': [{'type': 'CPF', 'number': cpf(95000 + i + (50 if who == 'B' else 0))}], 'phone': '11900000000'})
        except Exception as exc:
            errs.append(f'{who}: {exc}'[:200])
ts = [threading.Thread(target=burst, args=(A, 'A')), threading.Thread(target=burst, args=(B, 'B'))]
[t.start() for t in ts]; [t.join() for t in ts]
send(app_a, sess_a); send(app_b, sess_b)
app_a.state.cloud.pull(sess_a); app_b.state.cloud.pull(sess_b)
ca, cb = table_counts(root_a, key_a), table_counts(root_b, key_b)
want = base_counts['clients'] + len(ids) + 10 - len(errs)
check(ca['clients'] == cb['clients'] == want, f"10 clientes ao mesmo tempo em A e B: os dois iguais e nada perdido (A={ca['clients']}, B={cb['clients']}, recusados={len(errs)})", '; '.join(errs[:3]))
# ponto de restauração
pts = A.ok('GET', '/api/v1/cloud/points').get('items', [])
check(len(pts) >= 2, f'pontos de restauração na nuvem: {len(pts)}')

# ------------------------------------------------------------------ 5. usuários globais pela tela (API)
print('== usuários', flush=True)
st, u = A.req('POST', '/api/v1/users', {'name': 'Gerente.Um', 'password': '1234', 'package_id': 'GERENTE', 'full_name': 'Gerente Um'})
check(st == 201, 'A: criar Gerente', str(u)[:120])
st, u2 = B.req('POST', '/api/v1/users', {'name': 'gerente.um', 'password': '1234', 'package_id': 'OPERADOR'})
check(st >= 400 and 'login already exists' in json.dumps(u2), 'B: mesmo login (outra grafia) é recusado', str(u2)[:120])
G = login(B.base, 'gerente.um', '1234')
check(G.req('GET', '/api/v1/auth/me')[1].get('must_change') is True, 'Gerente entra no B (criado no A) e a senha provisória pede troca')
st, op = G.req('POST', '/api/v1/users', {'name': 'operador.um', 'password': '1234', 'package_id': 'OPERADOR'})
check(st == 201, 'Gerente cria Operador', str(op)[:120])
O = login(A.base, 'operador.um', '1234')
check(O.req('POST', '/api/v1/users', {'name': 'x123', 'password': '1234'})[0] == 403, 'Operador não cria usuário')
check(O.req('GET', '/api/v1/clients')[0] == 200 and O.req('GET', '/api/v1/expenses')[0] == 403, 'Operador vê clientes e não vê despesas')

# ------------------------------------------------------------------ 6. diagnóstico (2.6 Etapa 2)
print('== diagnóstico', flush=True)
st, dgn = A.req('GET', '/api/v1/system/diagnostics', label='tela: Diagnóstico')
check(st == 200 and (dgn.get('backup') or {}).get('verified') is True, 'Diagnóstico: cópia de segurança diária conferida', str((dgn.get('backup') or {}).get('counts'))[:120])
check(O.req('GET', '/api/v1/system/diagnostics')[0] == 403 and G.req('GET', '/api/v1/system/diagnostics')[0] == 403, 'Diagnóstico só para administradores')
st, z = A.req('GET', '/api/v1/system/support-package', raw=True, label='pacote de suporte')
import io as _io, zipfile as _zip
names = _zip.ZipFile(_io.BytesIO(z)).namelist() if st == 200 else []
text = ''.join(_zip.ZipFile(_io.BytesIO(z)).read(n).decode('utf-8', 'replace') for n in names) if names else ''
check(st == 200 and 'diagnostico.json' in names and 'Cliente Teste 0001' not in text and cpf(1) not in text, 'pacote de suporte gerado sem dados de clientes', f'{len(z) / 1024:.0f} KB, {names}')

# ------------------------------------------------------------------ relatório
total = time.time() - t_start
for app in (app_a, app_b):
    try:
        app.state.cloud.stop(); app.state.updates.stop()
    except Exception:
        pass
proc.terminate(); repo.stop()
ok_n = sum(r['ok'] for r in RESULTS)
lines = [f'# Testes pesados — UStracker {json.loads((ROOT / "VERSION.json").read_text())["version"]}', '',
         f'Data: {date.today().isoformat()} · duração {total / 60:.1f} min · resultado **{ok_n}/{len(RESULTS)}**', '',
         f'Massa: {N_CLIENTS} clientes, {N_VEHICLES} veículos, {len(subs)} assinaturas, {base_counts.get("charges")} cobranças, '
         f'{base_counts.get("payments")} pagamentos, {base_counts.get("expenses")} despesas, {sales} vendas diretas.', '',
         '## Verificações', '', '| | Verificação | Detalhe |', '|---|---|---|']
lines += [f"| {'✅' if r['ok'] else '❌'} | {r['what']} | {r['detail']} |" for r in RESULTS]
lines += ['', '## Tempos (segundos)', '', '| Operação | Mediana | Máximo | Vezes |', '|---|---|---|---|']
for k, v in TIMES.items():
    lines.append(f'| {k} | {statistics.median(v):.3f} | {max(v):.3f} | {len(v)} |')
(OUT / 'relatorio.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
(OUT / 'resultado.json').write_text(json.dumps({'results': RESULTS, 'times': {k: [round(x, 4) for x in v] for k, v in TIMES.items()}, 'counts': base_counts}, ensure_ascii=False), encoding='utf-8')
print('RESUMO', ok_n, '/', len(RESULTS), f'{total / 60:.1f} min')
os._exit(0 if ok_n == len(RESULTS) else 1)
