// AJ-07 — Ficha do Cliente enxuta: cabeçalho compacto, jornada fina, abas, leitura por padrão,
// edição sob demanda e "+ Adicionar" com formulários curtos. Regras de negócio ficam no backend.
import { formatBRL, formatDateBR } from './formatters.js';
import { codeTag, vehicleCategory, vehicleCell, vehicleDetail } from './logical-codes.js';
import { renderVehicleBreakdown } from './vehicle-breakdown.js';
import { subscriptionCountCell } from './subscription-popover.js';
import { fleetGroupOptions, renderMobilityHierarchy } from '../pages/mobility.js';

const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const STATUS = { ACTIVE: 'Ativo', INACTIVE: 'Inativo', CANCELLED: 'Cancelado', BLOCKED: 'Inativo' };
const SUB_STATUS = { ACTIVE: 'Ativa', PAUSED: 'Pausada', CANCELLED: 'Cancelada', ENDED: 'Encerrada' };
const SALE_STATUS = { OPEN: 'Em aberto', PAID: 'Paga', CANCELLED: 'Cancelada' };

export const CLIENT_PROFILE_TABS = [
  ['resumo', 'Resumo'], ['dados', 'Dados Básicos'], ['empresas', 'Empresas'], ['veiculos', 'Veículos e Frotas'],
  ['assinaturas', 'Assinaturas e Compras'], ['financeiro', 'Financeiro'], ['arquivos', 'Arquivos'],
];
const FOCUS_TAB = { mobility: 'veiculos', commercial: 'assinaturas' };

const initials = name => String(name || '?').trim().split(/\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase() || '?';
const table = (head, rows, empty) => rows.length
  ? `<div class="table-wrap cp-table"><table><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`
  : `<p class="muted cp-empty">${esc(empty)}</p>`;
const addButton = (target, label) => `<button type="button" class="ui-btn ui-btn-secondary cp-add" data-cp-toggle="${target}" aria-expanded="false">+ ${esc(label)}</button>`;
const panel = (id, title, actions, body) => `<section class="cp-panel" data-cp-panel="${id}" role="tabpanel" hidden><div class="cp-panel-head"><h3>${esc(title)}</h3><div class="cp-panel-actions">${actions}</div></div>${body}</section>`;

export function renderClientProfile(profile = {}, options = {}) {
  const client = profile.client || {};
  const documents = profile.documents || [];
  const companies = profile.companies || [];
  const summary = profile.summary || {};
  const financial = profile.financial || {};
  const subscriptions = profile.subscriptions || [];
  const attachments = profile.attachments || [];
  const vehicles = profile.vehicles || [];
  const fleets = profile.fleets || [];
  const directSales = profile.direct_sales || [];
  const document = documents[0] || { type: 'RG', number: client.document || '' };
  const primaryCompany = companies.find(company => company.is_primary) || companies[0];
  const media = profile.client_media?.[0];
  const activeSubs = subscriptions.filter(item => (item.lifecycle_status || 'ACTIVE') === 'ACTIVE').length;
  const hasMobility = vehicles.length + fleets.length > 0;
  const hasCommercial = subscriptions.length + directSales.length > 0;
  const activeTab = FOCUS_TAB[options.focus] || options.tab || 'resumo';

  // Cabeçalho compacto
  const avatar = `<form id="clientPhotoForm" class="cp-avatar" data-auto-upload><label title="Trocar foto" aria-label="Trocar foto do cliente">${media
    ? `<img src="/api/v1/media/${esc(encodeURIComponent(media.id))}/operational" alt="Foto do Cliente">`
    : `<span class="cp-initials">${esc(initials(client.legal_name))}</span>`}<span class="cp-avatar-edit">${media ? 'Trocar' : 'Adicionar'}</span><input name="file" type="file" accept="image/jpeg,image/png,image/webp" required></label>${media ? `<button type="button" class="cp-photo-remove cp-avatar-remove" data-remove-photo="${esc(media.id)}" aria-label="Remover foto do cliente" title="Remover foto">×</button>` : ''}</form>`;
  const contact = [client.phone, client.email].filter(Boolean).join(' · ');
  const chips = [
    ['Veículos', vehicles.length], ['Frotas', fleets.length], ['Assinaturas ativas', activeSubs],
    ['Contratado/mês', formatBRL(summary.contracted_active_cents || 0)], ['Receita realizada', formatBRL(summary.realized_revenue_cents || 0)],
  ].map(([label, value]) => `<div class="cp-chip"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join('');
  const head = `<header class="cp-head"><div class="cp-id"><h3>${esc(client.legal_name || 'Cliente')} ${codeTag(client.code)} <span class="cp-status cp-status-${esc(String(client.status || 'ACTIVE').toLowerCase())}">${esc(STATUS[client.status] || 'Ativo')}</span></h3>
    <p class="muted">${esc(contact || 'Sem contato')}${primaryCompany ? ` · ${esc(primaryCompany.trade_name || primaryCompany.legal_name)}` : ''}${document.number ? ` · ${esc(document.type || '')} ${esc(document.number)}` : ''}</p></div>
    <div class="cp-chips">${chips}</div></header>`;

  // Jornada fina (some quando completa)
  const step = (n, label, done, current, action) => `<li class="${done ? 'done' : current ? 'current' : ''}"><span class="cp-step-n">${done ? '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>' : n}</span><span>${esc(label)}</span>${!done && current ? action : ''}</li>`;
  const journey = hasMobility && hasCommercial ? '' : `<ol class="cp-steps" aria-label="Próximos passos do cadastro">
    ${step(1, 'Cliente', true, false, '')}
    ${step(2, 'Veículo ou frota', hasMobility, !hasMobility, '<button type="button" class="ui-btn ui-btn-primary ui-btn-sm" data-journey="mobility">Adicionar</button>')}
    ${step(3, 'Plano ou compra', hasCommercial, hasMobility && !hasCommercial, '<button type="button" class="ui-btn ui-btn-primary ui-btn-sm" data-journey-subscription>Assinar plano</button><button type="button" class="ui-btn ui-btn-secondary ui-btn-sm" data-journey="purchase">Compra direta</button>')}
  </ol>`;

  const tabs = `<nav class="cp-tabs" role="tablist">${CLIENT_PROFILE_TABS.map(([id, label]) => `<button type="button" role="tab" data-cp-tab="${id}" aria-selected="${id === activeTab}">${esc(label)}</button>`).join('')}</nav>`;

  // Resumo
  const resumo = panel('resumo', 'Resumo', '', `<div class="cp-grid">
      <div class="cp-box"><h4>Veículos</h4>${renderVehicleBreakdown(summary.vehicle_breakdown || {}, { title: 'Veículos', compact: true })}</div>
      <div class="cp-box"><h4>Organização</h4>${renderMobilityHierarchy(profile.mobility?.hierarchy || [])}</div>
      <div class="cp-box"><h4>Assinaturas e compras</h4><dl class="cp-dl"><dt>Assinaturas ativas</dt><dd>${activeSubs}</dd><dt>Valor contratado/mês</dt><dd>${formatBRL(summary.contracted_active_cents || 0)}</dd><dt>Compras em aberto</dt><dd>${formatBRL(summary.open_purchases_cents || 0)}</dd><dt>Receita realizada</dt><dd>${formatBRL(summary.realized_revenue_cents || 0)}</dd></dl></div>
    </div>`);

  // Dados básicos: leitura + edição sob demanda
  const statusValue = client.status === 'BLOCKED' ? 'INACTIVE' : (client.status || 'ACTIVE');
  const statusOptions = [['ACTIVE', 'ATIVO'], ['INACTIVE', 'INATIVO'], ['CANCELLED', 'CANCELADO']].map(([v, l]) => `<option value="${v}" ${statusValue === v ? 'selected' : ''}>${l}</option>`).join('');
  const documentTypeOptions = ['CPF', 'RG', 'CNH'].map(type => `<option value="${type}" ${document.type === type ? 'selected' : ''}>${type}</option>`).join('');
  const readView = `<dl class="cp-dl cp-dl-wide" data-cp-read="dados"><dt>Nome</dt><dd>${esc(client.legal_name || '—')}</dd><dt>E-mail</dt><dd>${esc(client.email || '—')}</dd><dt>Telefone</dt><dd>${esc(client.phone || '—')}</dd><dt>Situação</dt><dd>${esc(STATUS[client.status] || 'Ativo')}</dd><dt>Documento</dt><dd>${esc(document.type || '')} ${esc(document.number || '—')}</dd></dl>`;
  const editForm = `<form id="clientBasicsForm" class="cp-form" hidden><div class="cp-form-grid">
      <div class="field"><label>Nome*</label><input name="legal_name" value="${esc(client.legal_name || '')}" required></div>
      <div class="field"><label>E-mail</label><input name="email" type="email" value="${esc(client.email || '')}"></div>
      <div class="field"><label>Telefone</label><input name="phone" value="${esc(client.phone || '')}"></div>
      <div class="field"><label>Situação</label><select name="status">${statusOptions}</select></div>
      <div class="field"><label>Documento</label><select name="document_type">${documentTypeOptions}</select></div>
      <div class="field"><label>Número do documento*</label><input name="document" value="${esc(document.number || '')}" required></div>
    </div><p class="muted">Trocar o documento substitui o atual; não cria acúmulo.</p>
    <div class="cp-form-actions"><button type="button" class="ui-btn ui-btn-secondary" data-cp-cancel="clientBasicsForm">Cancelar</button><button type="submit" class="ui-btn ui-btn-primary">Salvar</button></div></form>`;
  const dados = panel('dados', 'Dados Básicos', '<button type="button" class="ui-btn ui-btn-secondary" data-cp-edit="clientBasicsForm">Editar</button>', readView + editForm);

  // Empresas
  const companyRows = companies.map(company => `<tr><td>${esc(company.trade_name || company.legal_name)}</td><td>${esc(company.legal_name || '')}</td><td>${esc(company.document || '—')}</td><td>${company.is_primary ? '<span class="cp-tag">Principal</span>' : ''}</td><td class="money">${fleets.filter(f => f.client_company_id === company.id).length}</td></tr>`);
  const companyForm = `<form id="clientCompanyForm" class="cp-form" hidden><div class="cp-form-grid">
      <div class="field"><label>Nome Fantasia ou Razão Social*</label><input name="legal_name" required></div>
      <div class="field"><label>CNPJ <span class="muted">(opcional)</span></label><input name="document"></div>
      <label class="cp-check"><input type="checkbox" name="is_primary" value="true"> Empresa principal</label>
    </div><div class="cp-form-actions"><button type="button" class="ui-btn ui-btn-secondary" data-cp-cancel="clientCompanyForm">Cancelar</button><button type="submit" class="ui-btn ui-btn-primary">Adicionar empresa</button></div></form>`;
  const empresas = panel('empresas', 'Empresas', addButton('clientCompanyForm', 'Empresa'), companyForm + table(['Nome', 'Razão social', 'CNPJ', '', 'Frotas'], companyRows, 'Nenhuma empresa cadastrada.'));

  // Veículos e frotas
  const typeOptions = ['Carro', 'Caminhão', 'Embarcação', 'Aeronave'].map(type => `<option value="${type}">${type}</option>`).join('') + '<option value="__custom__">Outro tipo…</option>';
  const fleetOptions = '<option value="">Particular (sem frota)</option>' + fleets.map(fleet => `<option value="${esc(fleet.id)}">${esc([fleet.name, fleet.vehicle_group_label || 'Misto'].join(' · '))}</option>`).join('');
  const companyOptions = companies.map(company => `<option value="${esc(company.id)}" ${company.is_primary ? 'selected' : ''}>${esc(company.trade_name || company.legal_name)}</option>`).join('');
  const vehicleForm = `<form id="clientVehicleForm" class="cp-form" hidden><h4>Novo veículo</h4><div class="cp-form-grid">
      <div class="field"><label>Tipo*</label><select name="type" required>${typeOptions}</select></div>
      <div class="field custom-type-field" hidden><label>Qual tipo?*</label><input name="custom_type"></div>
      <div class="field"><label>Marca*</label><input name="brand" required></div>
      <div class="field"><label>Série/Modelo*</label><input name="model" required></div>
      <div class="field"><label>Ano*</label><input name="year" inputmode="numeric" required></div>
      <div class="field"><label>Placa/Registro*</label><input name="plate" required></div>
      <div class="field"><label>Frota</label><select name="fleet_id">${fleetOptions}</select></div>
    </div><div class="cp-form-actions"><button type="button" class="ui-btn ui-btn-secondary" data-cp-cancel="clientVehicleForm">Cancelar</button><button type="submit" class="ui-btn ui-btn-primary">Salvar veículo</button></div></form>`;
  const fleetForm = companies.length ? `<form id="clientFleetForm" class="cp-form" hidden><h4>Nova frota</h4><div class="cp-form-grid">
      <div class="field"><label>Empresa*</label><select name="client_company_id" required>${companyOptions}</select></div>
      <div class="field"><label>Nome da frota*</label><input name="name" required></div>
      <div class="field"><label>Grupo (tipo de veículo)*</label><select name="vehicle_group" required>${fleetGroupOptions('MIXED')}</select></div>
      <div class="field"><label>Setor/Unidade</label><input name="sector_or_unit"></div>
    </div><div class="cp-form-actions"><button type="button" class="ui-btn ui-btn-secondary" data-cp-cancel="clientFleetForm">Cancelar</button><button type="submit" class="ui-btn ui-btn-primary">Salvar frota</button></div></form>`
    : '<p class="muted cp-form" id="clientFleetForm" hidden>Para criar uma frota, adicione antes uma empresa na aba Empresas.</p>';
  const fleetById = new Map(fleets.map(fleet => [fleet.id, fleet]));
  const companyById = new Map(companies.map(company => [company.id, company]));
  // V-04 — clean, aligned columns; the photo lives only in the side card (with "×" to remove).
  const vehicleRows = vehicles.map(vehicle => {
    const fleet = fleetById.get(vehicle.fleet_id);
    const company = fleet ? companyById.get(fleet.client_company_id) : null;
    const place = fleet ? `${esc(company?.trade_name || company?.legal_name || '—')} › ${esc(fleet.name)}` : '<span class="muted">Particular</span>';
    const name = [vehicle.brand, vehicle.model].filter(Boolean).join(' ');
    const label = [vehicle.plate, name].filter(Boolean).join(' · ');
    return `<tr data-cp-select-vehicle="${esc(vehicle.id)}" class="cp-vehicle-row" tabindex="0" title="Clique para ver a foto">
      <td class="cp-plate"><strong>${esc(vehicle.plate || '—')}</strong>${codeTag(vehicle.code)}</td>
      <td>${esc(name || '—')}${vehicle.year ? ` <span class="muted">${esc(vehicle.year)}</span>` : ''}</td>
      <td>${esc(vehicleCategory(vehicle.type, vehicle.category_label))}</td>
      <td>${place}</td>
      <td class="subs-cell">${subscriptionCountCell(vehicle.subscriptions_count, { vehicleId: vehicle.id, label: vehicle.plate })}</td>
      <td><div class="row-actions"><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-open-vehicle-transfer="${esc(vehicle.id)}">Mover</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-delete-vehicle="${esc(vehicle.id)}" data-label="${esc(label)}">Excluir</button></div></td></tr>`;
  });
  const fleetRows = fleets.map(fleet => {
    const company = companyById.get(fleet.client_company_id);
    return `<tr><td><strong>${esc(fleet.name)}</strong> ${codeTag(fleet.code)}</td><td>${esc(company?.trade_name || company?.legal_name || '—')}</td><td>${esc(fleet.vehicle_group_label || 'Misto')}</td><td class="money">${Number(fleet.vehicles_count || 0)}</td><td class="subs-cell">${subscriptionCountCell(fleet.subscriptions_count, { fleetId: fleet.id, label: fleet.name })}</td><td><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-delete-fleet="${esc(fleet.id)}" data-label="${esc(fleet.name)}" data-vehicles="${Number(fleet.vehicles_count || 0)}">Excluir</button></td></tr>`;
  });
  const veiculos = panel('veiculos', 'Veículos e Frotas', addButton('clientVehicleForm', 'Veículo') + addButton('clientFleetForm', 'Frota'),
    `${vehicleForm}${fleetForm}${renderVehicleBreakdown(summary.vehicle_breakdown || {}, { title: 'Veículos', compact: true })}
     <h4 class="cp-sub">Veículos</h4>${table(['Placa', 'Marca/Modelo', 'Tipo', 'Empresa › Frota', 'Assinaturas', ''], vehicleRows, 'Nenhum veículo cadastrado.')}
     <h4 class="cp-sub">Frotas</h4>${table(['Frota', 'Empresa', 'Grupo', 'Veículos', 'Assinaturas', ''], fleetRows, 'Nenhuma frota cadastrada.')}`);

  // Assinaturas e compras
  const subRows = subscriptions.map(sub => {
    const plans = (sub.items || sub.subscription_items || []).map(item => item.plan_name || item.description).filter(Boolean).join(', ') || 'Plano';
    return `<tr><td>${codeTag(sub.code) || '—'}</td><td>${esc(plans)}</td><td class="money">${formatBRL(sub.effective_total_cents || 0)}</td><td>${esc(formatDateBR(sub.start_on, false) || '—')}</td><td>${esc(SUB_STATUS[sub.lifecycle_status] || sub.lifecycle_status || '')}</td><td><div class="row-actions">${sub.lifecycle_status === 'ACTIVE' ? `<button type="button" class="ui-btn ui-btn-primary ui-btn-sm" data-client-payment data-subscription-id="${esc(sub.id)}">Pagar</button>` : ''}<button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-open-commercial="subscriptions" data-code="${esc(sub.code || '')}">Abrir no Comercial</button></div></td></tr>`;
  });
  const saleRows = directSales.map(sale => {
    const items = (sale.direct_sale_items || []).map(item => item.description).filter(Boolean).join(', ') || 'Compra direta';
    return `<tr><td>${codeTag(sale.code) || '—'}</td><td>${esc(items)}</td><td class="money">${formatBRL(sale.total_cents || 0)}</td><td>${esc(formatDateBR(sale.sold_on, false) || '—')}</td><td>${esc(SALE_STATUS[sale.status] || sale.status || '')}</td><td><button type="button" class="ui-btn ui-btn-subtle" data-open-commercial="purchases" data-code="${esc(sale.code || '')}">Abrir no Comercial</button></td></tr>`;
  });
  const vehicleOptions = '<option value="">— sem veículo —</option>' + vehicles.map(vehicle => `<option value="${esc(vehicle.id)}">${esc([vehicleCategory(vehicle.type, vehicle.category_label), vehicle.code, vehicleDetail(vehicle)].filter(Boolean).join(' · '))}</option>`).join('');
  const purchaseForm = `<form id="clientPurchaseForm" class="cp-form" hidden><h4>Nova compra direta</h4><div class="cp-form-grid">
      <div class="field"><label>Produto avulso*</label><select name="catalog_id" required data-avulsa-catalog><option value="">Carregando…</option></select></div>
      <div class="field"><label>Veículo</label><select name="vehicle_id">${vehicleOptions}</select></div>
      <div class="field"><label>Quantidade</label><input type="number" min="1" name="quantity" value="1"></div>
      <div class="field"><label>Data</label><input type="date" name="sold_on"></div>
    </div><div class="cp-form-actions"><button type="button" class="ui-btn ui-btn-secondary" data-cp-cancel="clientPurchaseForm">Cancelar</button><button type="submit" class="ui-btn ui-btn-primary">Registrar compra</button></div></form>`;
  const assinaturas = panel('assinaturas', 'Assinaturas e Compras',
    '<button type="button" class="ui-btn ui-btn-primary" data-client-new-subscription>+ Assinatura</button>' + addButton('clientPurchaseForm', 'Compra direta'),
    `${purchaseForm}<h4 class="cp-sub">Assinaturas</h4>${table(['Código', 'Plano', 'Valor', 'Início', 'Situação', ''], subRows, 'Nenhuma assinatura comercial.')}
     <h4 class="cp-sub">Compras diretas</h4>${table(['Código', 'Itens', 'Total', 'Data', 'Situação', ''], saleRows, 'Nenhuma compra direta.')}`);

  // Financeiro
  const financeiro = panel('financeiro', 'Financeiro', subscriptions.length ? '<button type="button" class="ui-btn ui-btn-primary" data-client-payment>Registrar pagamento</button>' : '', `<dl class="cp-dl cp-dl-wide"><dt>Valor contratado ativo (mês)</dt><dd>${formatBRL(summary.contracted_active_cents || 0)}</dd><dt>Receita realizada</dt><dd>${formatBRL(summary.realized_revenue_cents || 0)}</dd><dt>Compras em aberto</dt><dd>${formatBRL(summary.open_purchases_cents || 0)}</dd><dt>Compras pagas</dt><dd>${formatBRL(financial.direct_sales_paid_cents || 0)}</dd><dt>Despesas geradas</dt><dd>${formatBRL(financial.client_expenses_generated_cents || 0)}</dd><dt>Resultado do cliente</dt><dd>${formatBRL(summary.generated_value_cents || 0)}</dd></dl>`);

  // Arquivos
  const fileRows = attachments.map(attachment => `<tr><td>${attachment.origin === 'LINK'
      ? `<a href="${esc(attachment.url)}" target="_blank" rel="noopener">${esc(attachment.filename || 'Abrir link')}</a>`
      : `<a href="/api/v1/attachments/${esc(encodeURIComponent(attachment.id))}">${esc(attachment.filename || 'Baixar')}</a>`}</td><td>${esc({ client: 'Cliente', subscription: 'Assinatura', vehicle: 'Veículo', fleet: 'Frota' }[attachment.entity_type] || attachment.entity_type)}</td><td>${esc(formatDateBR(attachment.created_at, true) || '')}</td></tr>`);
  const signatureForm = subscriptions.length ? `<form id="clientSignatureForm" class="cp-inline" data-auto-upload><div class="field"><label>Anexar contrato assinado do plano</label><select name="subscription_id" required><option value="">Selecione o plano (assinatura)</option>${subscriptions.map(sub => `<option value="${esc(sub.id)}">${esc(sub.code || 'Assinatura')}</option>`).join('')}</select></div><label class="ui-btn ui-btn-secondary ui-file-action">Escolher e anexar arquivo<input type="file" name="file" accept=".jpg,.jpeg,.png,.webp,.pdf" required></label></form>` : '<p class="muted">Cadastre um plano (assinatura) antes de anexar o contrato assinado.</p>';
  const arquivos = panel('arquivos', 'Arquivos', '', signatureForm + table(['Arquivo', 'Vinculado a', 'Data'], fileRows, 'Nenhum arquivo anexado.'));

  // AJ-09 — photos live in their own column: client on top, selected vehicle at the bottom.
  const withPhoto = vehicles.find(vehicle => profile.vehicle_media?.[vehicle.id]?.[0]);
  const selectedVehicle = (withPhoto || vehicles[0] || {}).id || '';
  const vehicleCards = vehicles.map(vehicle => {
    const media = profile.vehicle_media?.[vehicle.id]?.[0];
    return `<figure class="cp-vehicle-card" data-cp-vehicle-card="${esc(vehicle.id)}"${vehicle.id === selectedVehicle ? '' : ' hidden'}>
      <div class="cp-vehicle-frame"><label class="cp-vehicle-photo" title="${media ? 'Trocar foto do veículo' : 'Adicionar foto do veículo'}">${media ? `<img src="/api/v1/media/${esc(encodeURIComponent(media.id))}/operational" alt="Foto do veículo">` : `<span class="cp-vehicle-empty">${vehicleCell(vehicle)}</span>`}<span class="cp-avatar-edit">${media ? 'Trocar foto' : '+ Adicionar foto'}</span><input type="file" accept="image/jpeg,image/png,image/webp" data-vehicle-photo="${esc(vehicle.id)}" aria-label="Foto do veículo"></label>${media ? `<button type="button" class="cp-photo-remove cp-vehicle-remove" data-remove-photo="${esc(media.id)}" aria-label="Remover foto do veículo" title="Remover foto">×</button>` : ''}</div>
      <figcaption><strong>${esc([vehicle.brand, vehicle.model].filter(Boolean).join(' ') || vehicleCategory(vehicle.type, vehicle.category_label))}</strong><span>${esc(vehicle.plate || '')} ${codeTag(vehicle.code)}</span></figcaption></figure>`;
  }).join('');
  const side = `<aside class="cp-side"><div class="cp-photo-card">${avatar}</div><div class="cp-side-fill"></div>${vehicles.length ? `<div class="cp-vehicle-slot"><span class="cp-side-label">Veículo selecionado</span>${vehicleCards}${vehicles.length > 1 ? '<p class="muted cp-side-hint">Clique em um veículo da lista para ver a foto dele.</p>' : ''}</div>` : ''}</aside>`;
  const html = `<div class="cp" data-cp-active="${esc(activeTab)}" data-client-id="${esc(client.id || '')}">${side}<div class="cp-main">${head}${journey}${tabs}${resumo}${dados}${empresas}${veiculos}${assinaturas}${financeiro}${arquivos}</div></div>`;
  return html.replace(`data-cp-panel="${activeTab}" role="tabpanel" hidden`, `data-cp-panel="${activeTab}" role="tabpanel"`);
}

/** Tab switching, "+ Adicionar" toggles and Editar/Cancelar. Pure DOM, no network. */
export function bindClientProfileUi(root) {
  if (!root) return;
  const selectTab = id => {
    root.querySelectorAll('[data-cp-tab]').forEach(tab => tab.setAttribute('aria-selected', String(tab.dataset.cpTab === id)));
    root.querySelectorAll('[data-cp-panel]').forEach(section => { section.hidden = section.dataset.cpPanel !== id; });
    root.querySelector('.cp')?.setAttribute('data-cp-active', id);
  };
  const reveal = (formId, show = true) => {
    const form = root.querySelector('#' + formId);
    if (!form) return;
    const section = form.closest('[data-cp-panel]');
    if (show && section) selectTab(section.dataset.cpPanel);
    form.hidden = !show;
    root.querySelectorAll(`[data-cp-toggle="${formId}"]`).forEach(button => button.setAttribute('aria-expanded', String(show)));
    const read = section?.querySelector('[data-cp-read]');
    if (read && formId === 'clientBasicsForm') read.hidden = show;
    if (show) { form.scrollIntoView?.({ block: 'nearest' }); form.querySelector('input:not([type=hidden]),select')?.focus?.(); }
  };
  root.querySelectorAll('[data-cp-tab]').forEach(tab => { tab.onclick = () => selectTab(tab.dataset.cpTab); });
  root.querySelectorAll('[data-cp-toggle]').forEach(button => { button.onclick = () => { const form = root.querySelector('#' + button.dataset.cpToggle); reveal(button.dataset.cpToggle, !!form?.hidden); }; });
  root.querySelectorAll('[data-cp-edit]').forEach(button => { button.onclick = () => reveal(button.dataset.cpEdit, true); });
  root.querySelectorAll('[data-cp-cancel]').forEach(button => { button.onclick = () => { const form = root.querySelector('#' + button.dataset.cpCancel); form?.reset?.(); reveal(button.dataset.cpCancel, false); }; });
  root.querySelectorAll('[data-journey="mobility"]').forEach(button => { button.onclick = () => reveal('clientVehicleForm', true); });
  root.querySelectorAll('[data-journey="purchase"]').forEach(button => { button.onclick = () => reveal('clientPurchaseForm', true); });
  const selectVehicle = id => {
    root.querySelectorAll('[data-cp-vehicle-card]').forEach(card => { card.hidden = card.dataset.cpVehicleCard !== id; });
    root.querySelectorAll('[data-cp-select-vehicle]').forEach(row => row.classList.toggle('is-selected', row.dataset.cpSelectVehicle === id));
  };
  root.querySelectorAll('[data-cp-select-vehicle]').forEach(row => {
    row.addEventListener('click', event => { if (!event.target.closest('input,label,a,button')) selectVehicle(row.dataset.cpSelectVehicle); });
    row.addEventListener('keydown', event => { if (event.key === 'Enter' && event.target === row) selectVehicle(row.dataset.cpSelectVehicle); });
  });
  const first = root.querySelector('[data-cp-vehicle-card]:not([hidden])');
  if (first) selectVehicle(first.dataset.cpVehicleCard);
  return { selectTab, reveal, selectVehicle };
}
