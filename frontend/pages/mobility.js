import { formatBRL, formatDateBR } from '../ui/formatters.js';
import { renderEntityAutocomplete } from '../ui/entity-autocomplete.js';
import { codeTag, vehicleCell } from '../ui/logical-codes.js';

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

const subscriptionSummaries = items => (items || []).length ? `<div class="mobility-subscriptions">${items.map(item =>
  `<div class="mobility-subscription"><strong>${esc(item.plan_names || 'Plano')}</strong>${codeTag(item.code)}<span>${esc(item.client_name || '—')} · ${esc(item.company_name || '—')}</span><span>${esc(formatDateBR(item.start_on, false))} · ${esc(formatBRL(Number(item.effective_total_cents || 0)))}</span></div>`
).join('')}</div>` : '<span class="muted">Sem assinatura ativa</span>';

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
  for (const key of ['client_id', 'fleet_id', 'plate']) {
    const value = String(filters[key] || '').trim();
    if (value) params.set(key, value);
  }
  const value = params.toString();
  return value ? `?${value}` : '';
}

function mobilityTable(rows = [], fleetMode = false) {
  const body = rows.length ? rows.map(row => `<tr>
    <td>${fleetMode ? `<span class="ui-vehicle"><strong>${esc(row.name || 'Frota')}</strong>${codeTag(row.code)}</span>` : vehicleCell(row)}</td>
    <td>${esc(row.client_name || '—')} ${codeTag(row.client_code)}</td>
    <td>${esc(fleetMode ? (row.name || row.fleet_name || '—') : (row.fleet_name || 'Particular'))}</td>
    <td>${esc(formatDateBR(row.contracted_on, false) || '—')}</td>
    <td>${esc(formatDateBR(row.review_on, false) || '—')}</td>
    <td>${esc(formatBRL(Number(row.total_value_cents || 0)))}</td>
    <td>${subscriptionSummaries(row.subscriptions)}</td>
    <td>${fleetMode ? `<button type="button" class="ui-btn ui-btn-secondary" data-open-fleet="${esc(row.id)}">Abrir Ficha</button>` : `<button type="button" class="ui-btn ui-btn-secondary" data-open-vehicle-transfer="${esc(row.id)}">Transferir</button>`}</td>
  </tr>`).join('') : '<tr><td colspan="8" class="muted">Nenhum registro encontrado.</td></tr>';
  return `<div class="table-wrap"><table class="ui-table mobility-table"><thead><tr>
    <th>${fleetMode ? 'Frota' : 'Veículo'}</th><th>Cliente</th><th>Frota(s)</th><th>Data Contratação</th><th>Data Revisão</th><th>Valor Total</th><th>Assinaturas</th><th>Ação</th>
  </tr></thead><tbody>${body}</tbody></table></div>`;
}

export function renderMobilityPage(data = {}, context = {}) {
  const fleets = (context.fleets || []).slice(0, 100);
  const filters = context.filters || {};
  const selectedClient = context.selectedClient || (filters.client_id ? { id: filters.client_id, display_name: filters.client_name || filters.client_id } : null);
  const typeOptions = MOBILITY_TYPES.map(type => `<option value="${esc(type)}">${esc(type)}</option>`).join('') + '<option value="__custom__">Novo tipo…</option>';
  return `<section class="mobility-page">
    <div class="page-header"><div><h2>Frotas/Veículos</h2><p class="muted">Gestão unificada de veículos particulares, frotas e transferências.</p></div></div>
    <div class="panel mobility-filters"><form id="mobilityFilter"><div class="row">
      ${renderEntityAutocomplete({name:'client_id',label:'Cliente',selected:selectedClient})}
      <div class="field"><label>Frota</label><select name="fleet_id">${options(fleets, 'id', 'name', true, filters.fleet_id)}</select></div>
      <div class="field"><label>Placa</label><input name="plate" value="${esc(filters.plate || '')}"></div>
    </div><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Pesquisar</button><button class="ui-btn ui-btn-secondary" type="button" id="mobilityClear">Limpar</button></div></form></div>
    <div class="panel"><div class="mobility-toolbar"><button type="button" class="ui-btn ui-btn-primary" id="newVehicle">Novo Veículo</button><button type="button" class="ui-btn ui-btn-secondary" id="newFleet">Nova Frota</button><span class="muted">Limite por frota: ${Number(data.fleet_limit || 100)} veículos ativos</span></div></div>
    <div class="mobility-tabs" role="tablist"><button type="button" class="mobility-tab active" data-mobility-tab="particulares">Particulares</button><button type="button" class="mobility-tab" data-mobility-tab="frotas">Frotas</button></div>
    <section data-mobility-panel="particulares">${mobilityTable(data.particulars || [], false)}</section>
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
      <div class="field"><label>Data Contratação</label><input name="contracted_on" type="date"></div>
      <div class="field"><label>Data Revisão</label><input name="review_on" type="date"></div>
      <div class="field"><label>RENAVAM</label><input name="renavam"></div>
      <div class="field"><label>Serial/IMEI</label><input name="tracker_serial_imei"></div>
    </div><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Salvar veículo</button></div></form></template>
    <template id="fleetFormTemplate"><form id="fleetForm"><div class="row">
      ${renderEntityAutocomplete({name:'client_id',label:'Cliente',required:true})}
      <div class="field"><label>Empresa*</label><select name="client_company_id" required><option value="">Selecione o cliente primeiro</option></select></div>
      <div class="field"><label>Nome da frota*</label><input name="name" required></div>
      <div class="field"><label>Setor/Unidade</label><input name="sector_or_unit"></div>
    </div><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Salvar frota</button></div></form></template>
  </section>`;
}

export function renderFleetProfile(profile = {}, context = {}) {
  const fleet = profile.fleet || {};
  const company = profile.company || {};
  const vehicles = profile.vehicles || [];
  const summary = profile.summary || {};
  const companies = context.companies || [];
  const vehicleRows = vehicles.length ? vehicles.map(vehicle => `<tr>
      <td>${vehicleCell(vehicle)}</td><td>${esc(vehicle.plate)}</td><td>${esc(vehicle.brand || '—')}</td><td>${esc(vehicle.model || '—')}</td><td>${esc(vehicle.year || '—')}</td><td>${esc(formatBRL(Number(vehicle.total_value_cents || 0)))}</td><td>${subscriptionSummaries(vehicle.subscriptions)}</td><td><button type="button" class="ui-btn ui-btn-secondary" data-open-vehicle-transfer="${esc(vehicle.id)}">Transferir</button></td>
    </tr>`).join('') : '<tr><td colspan="8">Nenhum veículo.</td></tr>';
  return `<div class="fleet-profile">
    <div class="fleet-profile-summary"><h3>${esc(fleet.name || 'Frota')}</h3><p class="muted">${esc(company.legal_name || 'Empresa não vinculada')}</p><dl><dt>Veículos ativos</dt><dd>${Number(summary.active_vehicles || 0)} / ${Number(summary.vehicle_limit || 100)}</dd><dt>Valor Total</dt><dd>${esc(formatBRL(Number(summary.total_value_cents || 0)))}</dd></dl></div>
    <section class="panel"><h4>Assinaturas ativas da frota</h4>${subscriptionSummaries(profile.subscriptions)}</section>
    <form id="fleetEditForm"><input type="hidden" name="expected_revision" value="${esc(fleet.revision || 0)}"><div class="row">
      <div class="field"><label>Empresa*</label><select name="client_company_id" required>${options(companies, 'id', 'legal_name', false, fleet.client_company_id)}</select></div>
      <div class="field"><label>Nome*</label><input name="name" value="${esc(fleet.name || '')}" required></div>
      <div class="field"><label>Setor/Unidade</label><input name="sector_or_unit" value="${esc(fleet.sector_or_unit || '')}"></div>
    </div><div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Salvar frota</button></div></form>
    <div class="actions"><button type="button" class="ui-btn ui-btn-secondary" data-add-vehicle-fleet="${esc(fleet.id)}">Adicionar veículo</button><button type="button" class="ui-btn ui-btn-secondary" data-upload-fleet-photo="${esc(fleet.id)}">Adicionar foto</button></div>
    <div class="table-wrap"><table class="ui-table"><thead><tr><th>Veículo</th><th>Placa</th><th>Marca</th><th>Modelo</th><th>Ano</th><th>Valor</th><th>Assinaturas</th><th>Ação</th></tr></thead><tbody>${vehicleRows}</tbody></table></div>
  </div>`;
}

export function renderTransferCaseForm(vehicle = {}, context = {}) {
  const cases = context.cases || [];
  const pending = cases.find(item => item.status === 'PENDING');
  if (pending) {
    return `<div class="notice mobility-transfer-pending"><strong>Transferência pendente.</strong><p>A propriedade vigente permanece inalterada até a conclusão.</p><div class="actions"><button type="button" class="ui-btn ui-btn-primary" data-complete-transfer="${esc(pending.id)}">Concluir</button><button type="button" class="ui-btn ui-btn-secondary" data-cancel-transfer="${esc(pending.id)}">Cancelar</button></div></div>`;
  }
  return `<form id="transferCaseForm"><input type="hidden" name="expected_revision" value="${esc(vehicle.revision || 0)}"><div class="row">
    ${renderEntityAutocomplete({name:'client_id',label:'Novo cliente',required:true})}
    <div class="field"><label>Nova frota</label><select name="fleet_id" disabled><option value="">Selecione o cliente primeiro</option></select></div>
    <div class="field"><label>Vigência</label><input type="date" name="effective_from"></div>
  </div><p class="muted">A criação deste caso não altera a propriedade atual. A mudança ocorre somente ao concluir.</p><div class="actions"><button class="ui-btn ui-btn-primary" type="submit">Criar transferência pendente</button></div></form>`;
}
