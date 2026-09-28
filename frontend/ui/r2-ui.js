import { getIconPath } from './icon-registry.js';
import { formatBRL, formatDateBR } from './formatters.js';
import { renderMoneyInput } from './money-input.js';

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

export function renderClientProfile(profile = {}) {
  const client = profile.client || {};
  const thumb = media => media ? `<img class="r2-profile-thumb" src="/api/v1/media/${escapeHtml(encodeURIComponent(media.id))}/thumb" alt="Foto">` : '<p class="muted">Nenhuma foto.</p>';
  const list = (items, render) => items?.length ? `<ul>${items.map(item => `<li>${render(item)}</li>`).join('')}</ul>` : '<p class="muted">Nenhum registro.</p>';
  const card = (title, body, open = false) => `<details class="r2-profile-card" ${open ? 'open' : ''}><summary>${title}</summary><div class="r2-profile-card-body">${body}</div></details>`;
  const vehicles = list(profile.vehicles, vehicle =>
    `<div class="r2-profile-vehicle">${thumb(profile.vehicle_media?.[vehicle.id]?.[0])}<span>${escapeHtml(vehicle.plate)} · ${escapeHtml(vehicle.type)}</span></div>`);
  const subscriptions = list(profile.subscriptions, subscription =>
    `<strong>${escapeHtml(({ DAILY: 'Diária', MONTHLY: 'Mensal', ANNUAL: 'Anual' })[subscription.billing_cycle] || subscription.billing_cycle)}</strong>
     ${list(subscription.subscription_items, item => `${escapeHtml(item.description)} · ${Number(item.quantity || 0)} unidade(s)`)}`);
  const sales = list(profile.direct_sales, sale =>
    `<strong>${escapeHtml(formatDateBR(sale.sold_on, false))} · ${escapeHtml(sale.status)} · ${escapeHtml(formatBRL(sale.total_cents))}</strong>
     ${list(sale.direct_sale_items, item => `${escapeHtml(item.description)} · ${Number(item.quantity || 0)} unidade(s)`)}`);
  const financial = profile.financial || {};
  return `<div class="r2-profile">
    ${card('Cliente', `<h3>${escapeHtml(client.legal_name)}</h3><p>${escapeHtml(client.public_name || client.trade_name || '')}</p>`, true)}
    ${card('Empresa / Identificação', `<dl><dt>Nome comercial</dt><dd>${escapeHtml(client.trade_name || '—')}</dd><dt>Documento</dt><dd>${escapeHtml(client.document || '—')}</dd><dt>E-mail</dt><dd>${escapeHtml(client.email || '—')}</dd><dt>Telefone</dt><dd>${escapeHtml(client.phone || '—')}</dd></dl>`)}
    ${card('Foto do Cliente', thumb(profile.client_media?.[0]))}
    ${card('Frotas', list(profile.fleets, fleet => escapeHtml(fleet.name)))}
    ${card('Veículos', vehicles)}
    ${card('Assinaturas', subscriptions)}
    ${card('Compras Diretas', sales)}
    ${card('Resumo Financeiro', `<dl><dt>Assinaturas recebidas</dt><dd>${escapeHtml(formatBRL(financial.subscription_received_cents))}</dd><dt>Compras pagas</dt><dd>${escapeHtml(formatBRL(financial.direct_sales_paid_cents))}</dd><dt>Despesas pagas do cliente</dt><dd>${escapeHtml(formatBRL(financial.client_expenses_paid_cents))}</dd></dl>`)}
  </div>`;
}

export function renderLoginScreen(setup = {}, publicData = {}) {
  const brand = publicData.brand || {};
  const storedLogo = brand.assets?.logo;
  const logo = storedLogo?.startsWith('/public-assets/') ? storedLogo : getIconPath('brand.logo');
  const catalog = publicData.catalog || [];
  return `<section class="auth r2-auth">
    <header class="r2-login-header">${logo ? `<img class="r2-login-logo" src="${escapeHtml(logo)}" alt="UStracker">` : '<h1>UStracker</h1>'}</header>
    <div class="r2-login-grid">
      <section class="r2-login-access"><h2>Acesso</h2><p>${setup.complete ? 'Acesso administrativo' : 'Configuração ainda incompleta.'}</p>
        <form id="login"><div class="field"><label>Administrador</label><input name="name" autocomplete="username" required></div>
          <div class="field"><label>Senha ou PIN (mínimo 4 caracteres)</label><input name="password" type="password" autocomplete="current-password" required></div>
          <fieldset class="r2-env-choice"><legend>Ambiente</legend><label><input type="radio" name="environment" value="production" checked> REAL</label><label><input type="radio" name="environment" value="test"> TESTE</label></fieldset>
          <div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Entrar</button></div></form><div id="loginOut"></div>
      </section>
      <section class="r2-login-marketing"><h2>Planos e Serviços</h2><p class="muted">${escapeHtml(brand.company_display_name || 'UStracker')}</p>
        ${catalog.length ? `<div class="r2-login-catalog">${catalog.map(item => `<article class="card"><strong>${escapeHtml(item.name)}</strong><p>${escapeHtml(item.category)}</p><span>${escapeHtml(formatBRL(item.price_cents))}</span></article>`).join('')}</div>` : '<p class="muted">Nenhum item público.</p>'}
      </section>
    </div></section>`;
}
