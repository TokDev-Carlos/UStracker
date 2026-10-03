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

export function renderClientProfile(profile = {}, options = {}) {
  const client = profile.client || {};
  const documents = profile.documents || [];
  const companies = profile.companies || [];
  const summary = profile.summary || {};
  const financial = profile.financial || {};
  const subscriptions = profile.subscriptions || [];
  const attachments = profile.attachments || [];
  const thumb = media => media ? `<img class="r2-profile-thumb" src="/api/v1/media/${escapeHtml(encodeURIComponent(media.id))}/thumb" alt="Foto do Cliente">` : '<p class="muted">Nenhuma foto.</p>';
  const list = (items, render, empty = 'Nenhum registro.') => items?.length ? `<ul>${items.map(item => `<li>${render(item)}</li>`).join('')}</ul>` : `<p class="muted">${escapeHtml(empty)}</p>`;
  const card = (title, body, open = false) => `<details class="r2-profile-card" ${open ? 'open' : ''}><summary>${title}</summary><div class="r2-profile-card-body">${body}</div></details>`;

  const document = documents[0] || { type: 'RG', number: client.document || '' };
  const documentTypeOptions = ['CPF', 'RG', 'CNH'].map(type => `<option value="${type}" ${document.type === type ? 'selected' : ''}>${type}</option>`).join('');
  const statusValue = client.status === 'BLOCKED' ? 'INACTIVE' : (client.status || 'ACTIVE');
  const statusOptions = [['ACTIVE', 'ATIVO'], ['INACTIVE', 'INATIVO'], ['CANCELLED', 'CANCELADO']]
    .map(([value, label]) => `<option value="${value}" ${statusValue === value ? 'selected' : ''}>${label}</option>`).join('');
  const photo = `${thumb(profile.client_media?.[0])}<form id="clientPhotoForm" data-auto-upload><div class="actions"><label class="ui-btn ui-btn-secondary ui-file-action">Escolher e atualizar foto<input name="file" type="file" accept="image/jpeg,image/png,image/webp" required></label></div></form>`;

  const companyList = list(companies, company => {
    const name = company.trade_name || company.legal_name || 'Empresa';
    const cnpj = company.document ? ` · CNPJ ${escapeHtml(company.document)}` : '';
    return `${escapeHtml(name)}${cnpj}${company.is_primary ? ' · Principal' : ''}`;
  });

  const vehicles = profile.vehicles || [];
  const fleets = profile.fleets || [];
  const directSales = profile.direct_sales || [];
  const vehicleGroups = VEHICLE_CATEGORIES.map(category => {
    const rows = vehicles.filter(vehicle => (vehicle.category || 'OTHER') === category.key);
    if (!rows.length) return '';
    return `<section class="r2-profile-vehicle-group"><h4>${categoryIcon(category.key, '')} ${escapeHtml(category.label)} <span class="muted">(${rows.length})</span></h4>${list(rows, vehicle => {
      const media = profile.vehicle_media?.[vehicle.id]?.[0];
      const custom = vehicle.category === 'OTHER' && vehicle.type ? ` · ${escapeHtml(vehicle.type)}` : '';
      const description = vehicleDetail(vehicle) || vehicleCategory(vehicle.type, vehicle.category_label);
      return `<div class="r2-profile-vehicle">${media ? thumb(media) : ''}<span>${escapeHtml(description)}${custom} ${codeTag(vehicle.code)}</span></div>`;
    })}</section>`;
  }).join('') || '<p class="muted">Nenhum veículo.</p>';
  const typeOptions = ['Carro', 'Caminhão', 'Embarcação', 'Aeronave'].map(type => `<option value="${type}">${type}</option>`).join('') + '<option value="__custom__">Outro tipo…</option>';
  const fleetOptions = '<option value="">Particular (sem frota)</option>' + fleets.map(fleet => `<option value="${escapeHtml(fleet.id)}">${escapeHtml([fleet.name, fleet.code].filter(Boolean).join(' · '))}</option>`).join('');
  const companyOptions = companies.map(company => `<option value="${escapeHtml(company.id)}" ${company.is_primary ? 'selected' : ''}>${escapeHtml(company.trade_name || company.legal_name)}</option>`).join('');
  const vehicleForm = `<form id="clientVehicleForm" class="r2-profile-inline-form"><h4>Adicionar veículo</h4><div class="row">
      <div class="field"><label>Tipo*</label><select name="type" required>${typeOptions}</select></div>
      <div class="field custom-type-field" hidden><label>Qual tipo?*</label><input name="custom_type"></div>
      <div class="field"><label>Marca*</label><input name="brand" required></div>
      <div class="field"><label>Série/Modelo*</label><input name="model" required></div>
      <div class="field"><label>Ano*</label><input name="year" inputmode="numeric" required></div>
      <div class="field"><label>Placa/Registro*</label><input name="plate" required></div>
      <div class="field"><label>Frota</label><select name="fleet_id">${fleetOptions}</select></div>
    </div><div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Salvar veículo</button></div></form>`;
  const fleetForm = companies.length ? `<form id="clientFleetForm" class="r2-profile-inline-form"><h4>Adicionar frota</h4><div class="row">
      <div class="field"><label>Empresa*</label><select name="client_company_id" required>${companyOptions}</select></div>
      <div class="field"><label>Nome da frota*</label><input name="name" required></div>
      <div class="field"><label>Setor/Unidade</label><input name="sector_or_unit"></div>
    </div><div class="actions"><button type="submit" class="ui-btn ui-btn-secondary">Salvar frota</button></div></form>` : '<p class="muted r2-profile-inline-form">Para criar uma frota, adicione antes uma empresa ao cliente.</p>';

  const signatureAttachments = attachments.filter(attachment => attachment.entity_type === 'subscription');
  const signatureList = list(signatureAttachments, attachment => attachment.origin === 'LINK'
    ? `<a href="${escapeHtml(attachment.url)}" target="_blank" rel="noopener">${escapeHtml(attachment.filename || 'Abrir assinatura')}</a>`
    : `<a href="/api/v1/attachments/${escapeHtml(encodeURIComponent(attachment.id))}">${escapeHtml(attachment.filename || 'Baixar assinatura')}</a>`, 'Nenhuma assinatura eletrônica anexada.');
  const signatureUpload = subscriptions.length ? `<form id="clientSignatureForm" data-auto-upload><div class="row"><div class="field"><label>Assinatura</label><select name="subscription_id" required><option value="">Selecione</option>${subscriptions.map(subscription => `<option value="${escapeHtml(subscription.id)}">${escapeHtml(subscription.code || 'Assinatura')}</option>`).join('')}</select></div></div><div class="actions"><label class="ui-btn ui-btn-secondary ui-file-action">Escolher e anexar arquivo<input type="file" name="file" accept=".jpg,.jpeg,.png,.webp,.pdf" required></label></div></form>` : '<p class="muted">Cadastre uma assinatura comercial antes de anexar o documento eletrônico.</p>';
  const subscriptionList = list(subscriptions, subscription => {
    const plans = (subscription.items || subscription.subscription_items || []).map(item => item.plan_name || item.description).filter(Boolean).join(', ') || 'Plano';
    return `<strong>${escapeHtml(plans)}</strong> ${codeTag(subscription.code)} · ${escapeHtml(formatDateBR(subscription.start_on, false))} · ${escapeHtml(formatBRL(subscription.effective_total_cents || 0))} · ${escapeHtml(subscription.lifecycle_status || '')} <button type="button" class="ui-btn ui-btn-subtle" data-open-commercial="subscriptions" data-code="${escapeHtml(subscription.code || '')}">Abrir no Comercial</button>`;
  }, 'Nenhuma assinatura comercial.');
  const saleStatus = { OPEN: 'Em aberto', PAID: 'Paga', CANCELLED: 'Cancelada' };
  const directSaleList = list(directSales, sale => {
    const items = (sale.direct_sale_items || []).map(item => item.description).filter(Boolean).join(', ') || 'Compra direta';
    return `<strong>${escapeHtml(items)}</strong> ${codeTag(sale.code)} · ${escapeHtml(formatDateBR(sale.sold_on, false))} · ${escapeHtml(formatBRL(sale.total_cents || 0))} · ${escapeHtml(saleStatus[sale.status] || sale.status || '')} <button type="button" class="ui-btn ui-btn-subtle" data-open-commercial="purchases" data-code="${escapeHtml(sale.code || '')}">Abrir no Comercial</button>`;
  }, 'Nenhuma compra direta.');
  const vehicleOptions = '<option value="">— sem veículo —</option>' + vehicles.map(vehicle => `<option value="${escapeHtml(vehicle.id)}">${escapeHtml([vehicleCategory(vehicle.type, vehicle.category_label), vehicle.code, vehicleDetail(vehicle)].filter(Boolean).join(' · '))}</option>`).join('');
  const purchaseForm = `<form id="clientPurchaseForm" class="r2-profile-inline-form"><h4>Nova compra direta</h4><div class="row">
      <div class="field"><label>Produto avulso*</label><select name="catalog_id" required data-avulsa-catalog><option value="">Carregando…</option></select></div>
      <div class="field"><label>Veículo</label><select name="vehicle_id">${vehicleOptions}</select></div>
      <div class="field"><label>Quantidade</label><input type="number" min="1" name="quantity" value="1"></div>
      <div class="field"><label>Data</label><input type="date" name="sold_on"></div>
    </div><div class="actions"><button type="submit" class="ui-btn ui-btn-secondary">Registrar compra</button></div></form>`;
  const hasMobility = vehicles.length + fleets.length > 0;
  const hasCommercial = subscriptions.length + directSales.length > 0;
  const stepClass = (done, isCurrent) => done ? 'done' : (isCurrent ? 'current' : '');
  const journey = `<ol class="client-journey" aria-label="Jornada do cliente">
    <li class="done"><span class="step">1 · Cliente</span><strong>${escapeHtml(client.legal_name || 'Cliente')} ${codeTag(client.code)}</strong><span class="muted">Cadastro concluído</span></li>
    <li class="${stepClass(hasMobility, !hasMobility)}"><span class="step">2 · Mobilidade</span><strong>${vehicles.length} veículo(s) · ${fleets.length} frota(s)</strong><button type="button" class="ui-btn ui-btn-subtle" data-journey="mobility">${hasMobility ? 'Adicionar mais' : 'Adicionar veículo ou frota'}</button></li>
    <li class="${stepClass(hasCommercial, hasMobility && !hasCommercial)}"><span class="step">3 · Plano ou compra</span><strong>${subscriptions.length} assinatura(s) · ${directSales.length} compra(s)</strong><span class="actions"><button type="button" class="ui-btn ui-btn-subtle" data-journey-subscription>Assinar plano</button><button type="button" class="ui-btn ui-btn-subtle" data-journey="purchase">Compra direta</button></span></li>
  </ol>`;

  return `<div class="r2-profile">
    ${journey}
    ${card('Dados Básicos', `<div class="r2-profile-basic-media">${photo}</div><form id="clientBasicsForm"><div class="row">
      <div class="field"><label>Nome*</label><input name="legal_name" value="${escapeHtml(client.legal_name || '')}" required></div>
      <div class="field"><label>E-mail</label><input name="email" type="email" value="${escapeHtml(client.email || '')}"></div>
      <div class="field"><label>Telefone</label><input name="phone" value="${escapeHtml(client.phone || '')}"></div>
      <div class="field"><label>Situação</label><select name="status">${statusOptions}</select></div>
      <div class="field"><label>Documento</label><select name="document_type">${documentTypeOptions}</select></div>
      <div class="field"><label>Número do documento*</label><input name="document" value="${escapeHtml(document.number || '')}" required><span class="muted">Ao salvar, substitui o documento atual; não cria acúmulo.</span></div>
    </div><div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Salvar dados</button></div></form>`, true)}
    ${card('Empresas', `${companyList}<form id="clientCompanyForm"><div class="row"><div class="field"><label>Nome Fantasia ou Razão Social*</label><input name="legal_name" required></div><div class="field"><label>CNPJ <span class="muted">(não obrigatório)</span></label><input name="document"></div><label><input type="checkbox" name="is_primary" value="true"> Principal</label></div><div class="actions"><button type="submit" class="ui-btn ui-btn-secondary">Adicionar</button></div></form>`)}
    ${card('Veículos', `${renderVehicleBreakdown(summary.vehicle_breakdown || {}, { title: 'Veículos', compact: true })}${vehicleGroups}${vehicleForm}${fleetForm}`, options.focus === 'mobility')}
    ${card('Financeiro', `<dl><dt>Valor contratado ativo</dt><dd>${escapeHtml(formatBRL(summary.contracted_active_cents || 0))}</dd><dt>Receita realizada</dt><dd>${escapeHtml(formatBRL(summary.realized_revenue_cents || 0))}</dd><dt>Compras em aberto</dt><dd>${escapeHtml(formatBRL(summary.open_purchases_cents || 0))}</dd><dt>Compras Pagas</dt><dd>${escapeHtml(formatBRL(financial.direct_sales_paid_cents))}</dd><dt>Despesas Geradas</dt><dd>${escapeHtml(formatBRL(financial.client_expenses_generated_cents))}</dd><dt>Resultado do cliente</dt><dd>${escapeHtml(formatBRL(summary.generated_value_cents))}</dd></dl>`)}
    ${card('Assinaturas', `<div class="actions"><button type="button" class="ui-btn ui-btn-primary" data-client-new-subscription>Nova Assinatura</button></div><h4>Assinaturas</h4>${subscriptionList}<h4>Compras diretas</h4>${directSaleList}${purchaseForm}${signatureList}${signatureUpload}`, options.focus === 'commercial')}
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
