import { getIconPath } from './icon-registry.js';
import { formatBRL, formatDateBR } from './formatters.js';
import { renderMoneyInput } from './money-input.js';
import { codeTag, vehicleCategory, vehicleDetail } from './logical-codes.js';
import { VEHICLE_CATEGORIES, categoryIcon, renderVehicleBreakdown } from './vehicle-breakdown.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[character]));

export function renderBillingCycleSelect(selected = 'MONTHLY') {
  const cycles = [['DAILY', 'Diário'], ['MONTHLY', 'Mensal'], ['ANNUAL', 'Anual']];
  return `<div class="field"><label>Periodicidade</label><select name="billing_cycle">${cycles.map(([value, label]) =>
    `<option value="${value}" ${selected === value ? 'selected' : ''}>${label}</option>`
  ).join('')}</select></div>`;
}

export function renderPurchasesForm({ clients = [], catalog = [], vehicles = [] } = {}) {
  const clientOptions = clients.map(row => `<option value="${escapeHtml(row.id)}">${escapeHtml(row.legal_name)}</option>`).join('');
  const catalogOptions = catalog.filter(row => row.active !== 0).map(row =>
    `<option value="${escapeHtml(row.id)}" data-price="${Number(row.price_cents || 0)}">${escapeHtml(row.name)}</option>`
  ).join('');
  const vehicleOptions = vehicles.map(row => `<option value="${escapeHtml(row.id)}" data-client="${escapeHtml(row.client_id)}">${escapeHtml(row.plate)}</option>`).join('');
  return `<div class="panel"><h3>Nova Compra Direta</h3><form id="purchaseForm">
    <div class="row"><div class="field"><label>Cliente*</label><select name="client_id" required>${clientOptions}</select></div>
    <div class="field"><label>Data da compra*</label><input name="sold_on" type="date" required></div>
    <div class="field"><label>Status</label><select name="status"><option value="OPEN">Em aberto</option><option value="PAID">Paga</option></select></div>
    <div class="field"><label>Data do pagamento</label><input name="paid_on" type="date"></div></div>
    <div class="row"><div class="field"><label>Item do catálogo</label><select id="purchaseCatalog">${catalogOptions}</select></div>
    <div class="field"><label>Veículo (opcional)</label><select id="purchaseVehicle"><option value="">—</option>${vehicleOptions}</select></div>
    <div class="field"><label>Quantidade</label><input name="quantity" type="number" min="1" value="1"></div>
    ${renderMoneyInput({ name: 'unit_price', label: 'Preço unitário', placeholder: 'Preço do catálogo' })}</div>
    <div class="actions"><button type="button" id="addPurchaseItem" class="ui-btn ui-btn-secondary">Adicionar item</button></div>
    <div id="purchaseItems" class="notice">Nenhum item.</div>
    <div class="field"><label>Observações</label><textarea name="notes"></textarea></div>
    <div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Salvar compra</button></div></form></div>`;
}

export function renderDashboardCards(data = {}) {
  const metrics = [
    ['Quantidade de Clientes', 'clients_count', false],
    ['Quantidade de Produtos', 'products_count', false],
    ['Quantidade de Veículos', 'vehicles_count', false],
    ['Assinaturas Ativas', 'active_subscription_products', false],
    ['Valor Acumulado', 'accumulated_profit_cents', true],
    ['Valor Mensal', 'monthly_value_cents', true],
    ['Valor Gasto', 'monthly_spent_cents', true],
    ['Lucro Real', 'real_profit_cents', true],
  ];
  return `<div class="r2-kpis">${metrics.map(([label, key, currency]) => {
    const value = Number(data[key] || 0);
    const tone = key === 'monthly_spent_cents' || value < 0 ? 'attention' : currency && value > 0 ? 'positive' : 'info';
    return `<div class="card r2-kpi r2-kpi-${tone}"><div class="r2-kpi-value">${escapeHtml(currency ? formatBRL(value) : value)}</div><div class="r2-kpi-label">${label}</div></div>`;
  }).join('')}</div>`;
}

export function formatSubscriptionRates(row = {}) {
  const rates = [
    ['subscription_daily_cents', '/dia'],
    ['subscription_monthly_cents', '/mês'],
    ['subscription_annual_cents', '/ano'],
  ].filter(([key]) => Number(row[key] || 0) !== 0);
  return rates.length ? rates.map(([key, suffix]) => formatBRL(row[key]) + suffix).join(' · ') : '—';
}

// AJ-07: the client profile lives in client-profile.js; re-exported for existing imports.
export { renderClientProfile } from './client-profile.js';

export function renderLoginScreen(setup = {}, publicData = {}) {
  const brand = publicData.brand || {};
  const storedLogo = brand.assets?.logo;
  const logo = storedLogo?.startsWith('/public-assets/') ? storedLogo : getIconPath('brand.logo');
  const catalog = publicData.catalog || [];
  return `<section class="auth r2-auth">
    <header class="r2-login-header">${logo ? `<img class="r2-login-logo" src="${escapeHtml(logo)}" alt="UStracker">` : '<h1>UStracker</h1>'}</header>
    <div class="r2-login-grid">
      <section class="r2-login-access"><h2>Acesso</h2><p>${setup.complete ? 'Entre com seu usuário e senha.' : (setup.activated ? 'Ainda sem Administrador local: entre com o Adm Global e crie-o em Sistema.' : 'Configuração ainda incompleta.')}</p>
        <form id="login"><div class="field"><label>Usuário</label><input name="name" autocomplete="username" required></div>
          <div class="field"><label>Senha ou PIN (mínimo 4 caracteres)</label><input name="password" type="password" autocomplete="current-password" required></div>
          <div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Entrar</button><button type="button" class="ui-btn ui-btn-subtle" data-recover-open>Esqueci a senha</button></div></form><div id="loginOut"></div>
      </section>
      <section class="r2-login-marketing"><h2>Planos e Serviços</h2><p class="muted">${escapeHtml(brand.company_display_name || 'UStracker')}</p>
        ${catalog.length ? `<div class="r2-login-catalog">${catalog.map(item => `<article class="card"><strong>${escapeHtml(item.name)}</strong><p>${escapeHtml(item.category)}</p><span>${escapeHtml(formatBRL(item.price_cents))}</span></article>`).join('')}</div>` : '<p class="muted">Nenhum item público.</p>'}
      </section>
    </div></section>`;
}
