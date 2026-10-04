import { formatBRL, formatDateBR } from '../ui/formatters.js';
import { renderEntityAutocomplete } from '../ui/entity-autocomplete.js';
import { codeTag, vehicleCell } from '../ui/logical-codes.js';
import { VEHICLE_CATEGORIES, categoryIcon, renderVehicleBreakdown } from '../ui/vehicle-breakdown.js';
import { subscriptionCountCell } from '../ui/subscription-popover.js';

// AJ-05 — fleet group options (declared category of a fleet; MIXED accepts every category).
export const FLEET_GROUPS = [...VEHICLE_CATEGORIES.map(item => ({ key: item.key, label: item.label })), { key: 'MIXED', label: 'Misto (vários tipos)' }];
export const fleetGroupOptions = (selected = 'MIXED') => FLEET_GROUPS.map(item => `<option value="${item.key}" ${item.key === (selected || 'MIXED') ? 'selected' : ''}>${item.label}</option>`).join('');
const groupBadge = (key, label) => key && key !== 'MIXED' ? `<span class="fleet-group">${categoryIcon(key, '')}${esc(label || '')}</span>` : '<span class="fleet-group fleet-group-mixed">Misto</span>';

export const MOBILITY_TYPES = ['Carro', 'Caminhão', 'Embarcação', 'Aeronave'];

const esc = value => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const options = (items, valueKey = 'id', labelKey = 'legal_name', includeBlank = false, selected = '') => {
  const rows = includeBlank ? ['<option value="">—</option>'] : [];
  for (const item of items || []) {
    const value = item?.[valueKey] ?? '';
    const label = item?.[labelKey] ?? value;
    rows.push(`<option value="${esc(value)}" ${String(value) === String(selected) ? 'selected' : ''}>${esc(label)}</option>`);
  }
  return rows.join('');
};

export function buildVehiclePayload(flat = {}) {
  const payload = { ...flat };
  payload.type = flat.type === '__custom__' ? String(flat.custom_type || '').trim() : String(flat.type || '').trim();
  delete payload.custom_type;
  if (!payload.fleet_id) delete payload.fleet_id;
  if (!payload.review_on) delete payload.review_on;
  if (!payload.contracted_on) delete payload.contracted_on;
  if (!payload.renavam) delete payload.renavam;
  if (!payload.tracker_serial_imei) delete payload.tracker_serial_imei;
  if (!payload.installed_on) delete payload.installed_on;
  payload.year = Number(payload.year || 0);
  return payload;
}

export function buildMobilityQuery(filters = {}) {
  const params = new URLSearchParams();
  for (const key of ['client_id', 'company_id', 'fleet_id', 'group', 'plate']) {
    const value = String(filters[key] || '').trim();
    if (value) params.set(key, value);
  }
  const value = params.toString();
  return value ? `?${value}` : '';
}

function mobilityTable(rows = [], fleetMode = false) {
  const head = fleetMode
    ? '<th>Frota</th><th>Cliente</th><th>Empresa</th><th>Grupo</th><th>Veículos</th><th>Contratação</th><th>Revisão</th><th>Valor Total</th><th>Assinaturas</th><th>Ação</th>'
    : '<th>Veículo</th><th>Cliente</th><th>Empresa › Frota</th><th>Contratação</th><th>Revisão</th><th>Valor Total</th><th>Assinaturas</th><th>Ação</th>';
  const cols = fleetMode ? 10 : 8;
  const body = rows.length ? rows.map(row => fleetMode ? `<tr>
    <td><span class="ui-fleet-name"><strong>${esc(row.name || 'Frota')}</strong>${codeTag(row.code)}</span></td>
    <td>${esc(row.client_name || '—')} ${codeTag(row.client_code)}</td>
    <td>${esc(row.company_name || '—')}</td>
    <td>${groupBadge(row.vehicle_group, row.vehicle_group_label)}</td>
    <td class="money">${Number(row.vehicles_count || 0)}</td>
    <td>${esc(formatDateBR(row.contracted_on, false) || '—')}</td>
    <td>${esc(formatDateBR(row.review_on, false) || '—')}</td>
    <td class="money">${esc(formatBRL(Number(row.total_value_cents || 0)))}</td>
    <td class="subs-cell">${subscriptionCountCell(row.subscriptions_count, { fleetId: row.id, label: row.name })}</td>
    <td><div class="row-actions"><button type="button" class="ui-btn ui-btn-secondary ui-btn-sm" data-open-fleet="${esc(row.id)}">Abrir ficha</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-delete-fleet="${esc(row.id)}" data-label="${esc(row.name || 'Frota')}" data-vehicles="${Number(row.vehicles_count || 0)}">Excluir</button></div></td>
  </tr>` : `<tr>
    <td>${vehicleCell(row)}</td>
    <td>${esc(row.client_name || '—')} ${codeTag(row.client_code)}</td>
    <td>${row.fleet_id ? `${esc(row.company_name || '—')} › ${esc(row.fleet_name || 'Frota')}` : '<span class="muted">Particular</span>'}</td>
    <td>${esc(formatDateBR(row.contracted_on, false) || '—')}</td>
    <td>${esc(formatDateBR(row.review_on, false) || '—')}</td>
    <td class="money">${esc(formatBRL(Number(row.total_value_cents || 0)))}</td>
    <td class="subs-cell">${subscriptionCountCell(row.subscriptions_count, { vehicleId: row.id, label: row.plate })}</td>
    <td><div class="row-actions"><button type="button" class="ui-btn ui-btn-secondary ui-btn-sm" data-open-vehicle-transfer="${esc(row.id)}">Mover</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-delete-vehicle="${esc(row.id)}" data-label="${esc([row.plate, row.brand, row.model].filter(Boolean).join(' · '))}">Excluir</button></div></td>
  </tr>`).join('') : `<tr><td colspan="${cols}" class="muted">Nenhum registro encontrado.</td></tr>`;
  return `<div class="table-wrap"><table class="ui-table mobility-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

/** AJ-05 — Cliente › Empresa › Frota › Grupo, with totals at every level. */
export function renderMobilityHierarchy(hierarchy = []) {
  if (!hierarchy.length) return '<p class="muted">Nenhum veículo ou frota encontrado.</p>';
  return `<div class="mobility-tree">${hierarchy.map(client => `<section class="tree-client">
    <header><strong>${esc(client.client_name || 'Cliente')}</strong>${codeTag(client.client_code)}<span class="tree-total">${client.total} veículo(s)</span></header>
    ${client.companies.map(company => `<div class="tree-company"><header><span class="tree-label">Empresa</span><strong>${esc(company.company_name)}</strong><span class="tree-total">${company.total}</span></header>
      <ul class="tree-fleets">${company.fleets.map(fleet => `<li><button type="button" class="tree-fleet" data-open-fleet="${esc(fleet.fleet_id)}"><strong>${esc(fleet.fleet_name)}</strong>${codeTag(fleet.fleet_code)}${groupBadge(fleet.vehicle_group, fleet.vehicle_group_label)}<span class="tree-total">${fleet.total}</span></button>
        ${fleet.groups.length ? `<span class="tree-groups">${fleet.groups.map(group => `<span class="tree-group">${categoryIcon(group.key, '')}${esc(group.label)} <strong>${group.count}</strong></span>`).join('')}</span>` : '<span class="muted tree-groups">Sem veículos</span>'}</li>`).join('')}</ul></div>`).join('')}
    ${client.particulars ? `<div class="tree-company tree-particulars"><header><span class="tree-label">Particulares</span><strong>Sem frota</strong><span class="tree-total">${client.particulars}</span></header></div>` : ''}
  </section>`).join('')}</div>`;
}

export function renderMobilityPage(data = {}, context = {}) {
  const fleets = (context.fleets || []).slice(0, 100);
  const filters = context.filters || {};
  const selectedClient = context.selectedClient || (filters.client_id ? { id: filters.client_id, display_name: filters.client_name || filters.client_id } : null);
  const typeOptions = MOBILITY_TYPES.map(type => `<option value="${esc(type)}">${esc(type)}</option>`).join('') + '<option value="__custom__">Novo tipo…</option>';
  return `<section class="mobility-page">
    <div class="page-header"><div><h2>Frotas/Veículos</h2><p class="muted">Veículos particulares e frotas. Use “Mover” para trocar de frota ou de cliente e “Excluir” para mandar à Lixeira (14 dias).</p></div></div>
    <div class="panel mobility-filters"><form id="mobilityFilter"><div class="row">
      ${renderEntityAutocomplete({name:'client_id',label:'Cliente',selected:selectedClient})}
      <div class="field"><label>Empresa</label><select name="company_id">${options(context.companies || [], 'id', 'legal_name', true, filters.company_id)}</select></div>
      <div class="field"><label>Frota</label><select name="fleet_id">${options(fleets, 'id', 'name', true, filters.fleet_id)}</select></div>
      <div class="field"><label>Grupo</label><select name="group"><option value="">Todos</option>${VEHICLE_CATEGORIES.map(item => `<option value="${item.key}" ${filters.group === item.key ? 'selected' : ''}>${item.label}</option>`).join('')}</select></div>
      <div class="field"><label>Placa</label><input name="plate" value="${esc(filters.plate || '')}"></div>
    </div><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Pesquisar</button><button class="ui-btn ui-btn-secondary" type="button" id="mobilityClear">Limpar</button></div></form></div>
    <div class="panel"><div class="mobility-toolbar"><button type="button" class="ui-btn ui-btn-primary" id="newVehicle">Novo Veículo</button><button type="button" class="ui-btn ui-btn-secondary" id="newFleet">Nova Frota</button><span class="muted">Limite por frota: ${Number(data.fleet_limit || 100)} veículos ativos</span></div></div>
    ${data.vehicle_breakdown ? `<div class="panel">${renderVehicleBreakdown(data.vehicle_breakdown, { title: 'Veículos', compact: true })}</div>` : ''}
    <div class="mobility-tabs" role="tablist"><button type="button" class="mobility-tab active" data-mobility-tab="organizacao">Por Empresa</button><button type="button" class="mobility-tab" data-mobility-tab="particulares">Particulares</button><button type="button" class="mobility-tab" data-mobility-tab="frotas">Frotas</button></div>
    <section data-mobility-panel="organizacao">${renderMobilityHierarchy(data.hierarchy || [])}</section>
    <section data-mobility-panel="particulares" hidden>${mobilityTable(data.particulars || [], false)}</section>
    <section data-mobility-panel="frotas" hidden>${mobilityTable(data.fleets || [], true)}</section>
    <template id="vehicleFormTemplate"><form id="vehicleForm"><div class="row">
      ${renderEntityAutocomplete({name:'client_id',label:'Cliente',required:true})}
      <div class="field"><label>Frota</label><select name="fleet_id" disabled><option value="">Selecione o cliente primeiro</option></select></div>
      <div class="field"><label>Tipo*</label><select name="type" required>${typeOptions}</select></div>
      <div class="field custom-type-field" hidden><label>Novo tipo*</label><input name="custom_type"></div>
      <div class="field"><label>Marca*</label><input name="brand" required></div>
      <div class="field"><label>Série/Modelo*</label><input name="model" required></div>
      <div class="field"><label>Ano*</label><input name="year" inputmode="numeric" required></div>
      <div class="field"><label>Placa*</label><input name="plate" required></div>
    </div><details class="more-options"><summary>Mais opções</summary><div class="row">
      <div class="field"><label>Data Contratação</label><input name="contracted_on" type="date"></div>
      <div class="field"><label>Data Revisão</label><input name="review_on" type="date"></div>
      <div class="field"><label>RENAVAM</label><input name="renavam"></div>
      <div class="field"><label>Serial/IMEI</label><input name="tracker_serial_imei"></div>
    </div></details><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Salvar veículo</button></div></form></template>
    <template id="fleetFormTemplate"><form id="fleetForm"><div class="row">
      ${renderEntityAutocomplete({name:'client_id',label:'Cliente',required:true})}
      <div class="field"><label>Empresa*</label><select name="client_company_id" required><option value="">Selecione o cliente primeiro</option></select></div>
      <div class="field"><label>Nome da frota*</label><input name="name" required></div>
      <div class="field"><label>Grupo (tipo de veículo)*</label><select name="vehicle_group" required>${fleetGroupOptions('MIXED')}</select></div>
      <div class="field"><label>Setor/Unidade</label><input name="sector_or_unit"></div>
    </div><p class="muted">Uma frota com grupo definido aceita apenas veículos daquele tipo. "Misto" aceita todos.</p><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Salvar frota</button></div></form></template>
  </section>`;
}

export function renderFleetProfile(profile = {}, context = {}) {
  const fleet = profile.fleet || {};
  const company = profile.company || {};
  const vehicles = profile.vehicles || [];
  const summary = profile.summary || {};
  const companies = context.companies || [];
  const vehicleRows = vehicles.length ? vehicles.map(vehicle => `<tr>
      <td>${vehicleCell(vehicle)}</td><td>${esc(vehicle.plate)}</td><td>${esc(vehicle.brand || '—')}</td><td>${esc(vehicle.model || '—')}</td><td>${esc(vehicle.year || '—')}</td><td class="money">${esc(formatBRL(Number(vehicle.total_value_cents || 0)))}</td><td class="subs-cell">${subscriptionCountCell(vehicle.subscriptions_count, { vehicleId: vehicle.id, label: vehicle.plate })}</td><td><div class="row-actions"><button type="button" class="ui-btn ui-btn-secondary ui-btn-sm" data-open-vehicle-transfer="${esc(vehicle.id)}">Mover</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-delete-vehicle="${esc(vehicle.id)}" data-label="${esc([vehicle.plate, vehicle.brand, vehicle.model].filter(Boolean).join(' · '))}">Excluir</button></div></td>
    </tr>`).join('') : '<tr><td colspan="8">Nenhum veículo.</td></tr>';
  return `<div class="fleet-profile">
    <div class="fleet-profile-summary"><h3>${esc(fleet.name || 'Frota')} ${groupBadge(fleet.vehicle_group, fleet.vehicle_group_label)}</h3><p class="muted">${esc(company.legal_name || 'Empresa não vinculada')}</p><dl><dt>Veículos ativos</dt><dd>${Number(summary.active_vehicles || 0)} / ${Number(summary.vehicle_limit || 100)}</dd><dt>Valor Total</dt><dd>${esc(formatBRL(Number(summary.total_value_cents || 0)))}</dd></dl></div>
    ${summary.vehicle_breakdown ? renderVehicleBreakdown(summary.vehicle_breakdown, { title: 'Veículos da frota', compact: true }) : ''}
    <section class="panel fleet-subs"><h4>Assinaturas ativas da frota</h4>${subscriptionCountCell((profile.subscriptions || []).length, { fleetId: fleet.id, label: fleet.name })}<span class="muted"> Clique no número para ver valores e detalhes.</span></section>
    <form id="fleetEditForm"><input type="hidden" name="expected_revision" value="${esc(fleet.revision || 0)}"><div class="row">
      <div class="field"><label>Empresa*</label><select name="client_company_id" required>${options(companies, 'id', 'legal_name', false, fleet.client_company_id)}</select></div>
      <div class="field"><label>Nome*</label><input name="name" value="${esc(fleet.name || '')}" required></div>
      <div class="field"><label>Grupo (tipo de veículo)</label><select name="vehicle_group">${fleetGroupOptions(fleet.vehicle_group)}</select></div>
      <div class="field"><label>Setor/Unidade</label><input name="sector_or_unit" value="${esc(fleet.sector_or_unit || '')}"></div>
    </div><div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Salvar frota</button></div></form>
    <div class="actions"><button type="button" class="ui-btn ui-btn-secondary" data-add-vehicle-fleet="${esc(fleet.id)}">Adicionar veículo</button><label class="ui-btn ui-btn-secondary ui-file-action">Adicionar foto<input type="file" accept="image/jpeg,image/png,image/webp" data-fleet-photo="${esc(fleet.id)}"></label><button type="button" class="ui-btn ui-btn-subtle ui-btn-del" data-delete-fleet="${esc(fleet.id)}" data-label="${esc(fleet.name || 'Frota')}" data-vehicles="${vehicles.length}">Excluir frota</button></div>
    <div class="table-wrap"><table class="ui-table"><thead><tr><th>Veículo</th><th>Placa</th><th>Marca</th><th>Modelo</th><th>Ano</th><th>Valor</th><th>Assinaturas</th><th>Ação</th></tr></thead><tbody>${vehicleRows}</tbody></table></div>
  </div>`;
}

/** AJ-08 — "Mover veículo": one simple form, effective immediately (date today by default). */
export function renderMoveVehicleForm(vehicle = {}, context = {}) {
  const client = context.client || (vehicle.client_id ? { id: vehicle.client_id, display_name: vehicle.client_name || 'Cliente atual' } : null);
  const today = context.today || '';
  const where = vehicle.fleet_id ? `Frota ${esc(vehicle.fleet_name || '')}` : 'Particular';
  return `<form id="moveVehicleForm" class="move-form">
    <p class="move-from">Agora: <strong>${esc(vehicle.client_name || client?.display_name || '—')}</strong> · ${where}</p>
    <div class="row">${renderEntityAutocomplete({ name: 'client_id', label: 'Cliente de destino', required: true, selected: client })}
    <div class="field"><label>Destino</label><select name="fleet_id" ${client ? '' : 'disabled'}><option value="">Particular (sem frota)</option></select></div>
    <div class="field"><label>A partir de</label><input type="date" name="effective_from" value="${esc(today)}" ${today ? `max="${esc(today)}"` : ''}></div></div>
    <p class="notice" data-move-warning hidden>Ao mudar de cliente, o veículo sai das assinaturas do cliente atual e recebe um novo código.</p>
    <div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Mover agora</button></div></form>`;
}

/** Kept for compatibility with older callers: the pending-case flow was replaced by the simple move. */
export function renderTransferCaseForm(vehicle = {}, context = {}) {
  return renderMoveVehicleForm(vehicle, { ...context, client: null });
}
