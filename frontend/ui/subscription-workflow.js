import { bindEntityAutocomplete, renderEntityAutocomplete } from './entity-autocomplete.js';
import { vehicleCategory } from './logical-codes.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]));

const activeMonthlyPlans = catalog => (catalog || []).filter(item =>
  Number(item.active ?? 1) === 1 && String(item.category || '').toUpperCase() === 'MENSAL'
);

export function searchSubscriptionClients(clients = [], query = '') {
  const needle = String(query || '').trim().toLocaleLowerCase('pt-BR');
  return needle ? clients.filter(client => String(client.legal_name || '').toLocaleLowerCase('pt-BR').includes(needle)) : [...clients];
}

export function subscriptionOptionsForClient(model = {}, clientId = '') {
  const belongs = row => row.client_id === clientId && Number(row.archived || 0) === 0;
  return {
    plans: activeMonthlyPlans(model.catalog),
    vehicles: clientId ? (model.vehicles || []).filter(belongs) : [],
    fleets: clientId ? (model.fleets || []).filter(belongs) : [],
  };
}

// V-07 — vehicles as aligned cards with the photo thumbnail (when there is one).
function vehicleThumb(model, vehicle) {
  const media = model.vehicleMedia?.[vehicle.id]?.[0] || (vehicle.media_id ? { id: vehicle.media_id } : null);
  return media
    ? `<img src="/api/v1/media/${escapeHtml(encodeURIComponent(media.id))}/thumb" alt="">`
    : `<span class="sw-thumb-empty" aria-hidden="true">${escapeHtml((vehicleCategory(vehicle.type, vehicle.category_label) || 'V').slice(0, 1))}</span>`;
}

function targetChoices(model, clientId) {
  const { vehicles, fleets } = subscriptionOptionsForClient(model, clientId);
  if (!clientId) return '<p class="muted">Selecione o cliente para carregar veículos e frotas.</p>';
  const vehicleCards = vehicles.length
    ? `<div class="sw-targets">${vehicles.map(row => `<label class="sw-target"><input type="checkbox" data-subscription-target="vehicle" value="${escapeHtml(row.id)}"><span class="sw-thumb">${vehicleThumb(model, row)}</span><span class="sw-text"><strong>${escapeHtml(row.plate || 'Sem placa')}</strong><small>${escapeHtml([[row.brand, row.model].filter(Boolean).join(' '), vehicleCategory(row.type, row.category_label)].filter(Boolean).join(' · '))}</small></span></label>`).join('')}</div>`
    : '<p class="muted">Nenhum veículo deste cliente.</p>';
  const fleetCards = fleets.length
    ? `<div class="sw-targets">${fleets.map(row => `<label class="sw-target"><input type="checkbox" data-subscription-target="fleet" value="${escapeHtml(row.id)}"><span class="sw-thumb"><span class="sw-thumb-empty" aria-hidden="true">F</span></span><span class="sw-text"><strong>${escapeHtml(row.name || 'Frota')}</strong><small>${escapeHtml([row.code, row.vehicle_group_label].filter(Boolean).join(' · '))}</small></span></label>`).join('')}</div>`
    : '<p class="muted">Nenhuma frota deste cliente.</p>';
  return `<fieldset class="field sw-fieldset"><legend>Veículos (o plano cobre os marcados)</legend>${vehicleCards}</fieldset>
    <fieldset class="field sw-fieldset"><legend>Frotas</legend>${fleetCards}</fieldset>`;
}

export function renderSubscriptionWorkflow(model = {}) {
  const context = String(model.context || 'COMMERCIAL').toUpperCase();
  const locked = context === 'CLIENT_PROFILE';
  const selectedClientId = String(model.clientId || model.selectedClientId || '');
  const clients = (model.clients || []).filter(row => Number(row.archived || 0) === 0 && row.status !== 'INACTIVE' && row.status !== 'CANCELLED');
  const selectedClient = clients.find(row => row.id === selectedClientId) || {};
  const clientField = locked
    ? `<div class="field"><label>Cliente</label><select name="client_display" disabled><option>${escapeHtml(selectedClient.legal_name || selectedClientId)}</option></select><input type="hidden" name="client_id" value="${escapeHtml(selectedClientId)}"></div>`
    : `<div data-subscription-client-search>${renderEntityAutocomplete({
        name: 'client_id', label: 'Cliente', required: true,
        selected: selectedClientId ? { id: selectedClientId, display_name: selectedClient.legal_name || selectedClientId } : null,
      })}</div>`;
  const plans = activeMonthlyPlans(model.catalog);
  const today = new Date(); const pad = n => String(n).padStart(2, '0');
  const startOn = escapeHtml(model.startOn || `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`); // local date, not UTC
  return `<form id="subscriptionWorkflowForm" data-subscription-context="${escapeHtml(context)}">
    <p class="muted sw-help">Assinatura é o plano mensal do cliente: todo mês gera uma cobrança no dia do vencimento, para os veículos ou frotas marcados. Quando a cobrança é paga, vira receita.</p>
    <div class="row">${clientField}<div class="field"><label>Plano mensal*</label><select name="catalog_id" required><option value="">Selecione o plano</option>${plans.map(item => `<option value="${escapeHtml(item.id)}" data-price="${Number(item.price_cents || 0)}">${escapeHtml(item.name || item.description || item.id)}</option>`).join('')}</select></div></div>
    <div class="row"><div class="field"><label>Início*</label><input type="date" name="start_on" value="${startOn}" required></div><div class="field"><label>Dia do vencimento*</label><input type="number" name="due_day" min="1" max="31" value="10" required></div><div class="field"><label>Quantidade*</label><input type="number" name="quantity" min="1" value="1" required></div></div>
    <div data-subscription-targets>${targetChoices(model, selectedClientId)}</div>
    <div data-subscription-error class="error" hidden></div>
    <div class="actions"><button type="button" class="ui-btn ui-btn-secondary" data-close-overlay>Cancelar</button><button type="submit" class="ui-btn ui-btn-primary">Criar assinatura</button></div>
  </form>`;
}

const uniqueIds = (values, label) => {
  const normalized = (values || []).map(value => String(value || '').trim()).filter(Boolean);
  if (new Set(normalized).size !== normalized.length) throw new Error(`${label} duplicado`);
  return normalized;
};

export function buildSubscriptionPayload(form = {}, selections = {}, _options = {}) {
  const clientId = String(form.client_id || '').trim();
  const catalogId = String(form.catalog_id || '').trim();
  const startOn = String(form.start_on || '').trim();
  const dueDay = Number(form.due_day || 10);
  const quantity = Number(form.quantity || 1);
  if (!clientId || !catalogId || !startOn) throw new Error('Cliente, plano e início são obrigatórios.');
  if (!Number.isInteger(dueDay) || dueDay < 1 || dueDay > 31) throw new Error('Dia do vencimento inválido.');
  if (!Number.isInteger(quantity) || quantity < 1) throw new Error('Quantidade inválida.');
  return {
    client_id: clientId,
    start_on: startOn,
    due_day: dueDay,
    billing_cycle: 'MONTHLY',
    items: [{ catalog_id: catalogId, quantity }],
    target_vehicle_ids: uniqueIds(selections.targetVehicleIds, 'Veículo'),
    target_fleet_ids: uniqueIds(selections.targetFleetIds, 'Frota'),
  };
}

export function bindSubscriptionWorkflow(root, { model = {}, searchClients, onSubmit, onError } = {}) {
  const form = root?.querySelector?.('#subscriptionWorkflowForm');
  if (!form) return null;
  const targetHost = form.querySelector('[data-subscription-targets]');
  if (typeof searchClients === 'function') bindEntityAutocomplete(form, {
    search: searchClients,
    onSelection: client => {
      if (targetHost) targetHost.innerHTML = targetChoices(model, client?.id || '');
    },
  });
  form.onsubmit = async event => {
    event.preventDefault();
    const errorBox = form.querySelector('[data-subscription-error]');
    const submitButton = form.querySelector('[type=submit]');
    try {
      const flat = Object.fromEntries(new FormData(form).entries());
      const selections = {
        targetVehicleIds: [...form.querySelectorAll('[data-subscription-target="vehicle"]:checked')].map(input => input.value),
        targetFleetIds: [...form.querySelectorAll('[data-subscription-target="fleet"]:checked')].map(input => input.value),
      };
      const payload = buildSubscriptionPayload(flat, selections, { context: model.context });
      if (errorBox) { errorBox.hidden = true; errorBox.textContent = ''; }
      if (submitButton) submitButton.disabled = true;
      await onSubmit?.(payload, form);
    } catch (error) {
      if (errorBox) { errorBox.hidden = false; errorBox.textContent = error.message; }
      onError?.(error, form);
    } finally {
      if (submitButton?.isConnected) submitButton.disabled = false;
    }
  };
  return form;
}
