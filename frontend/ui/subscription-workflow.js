import { bindEntityAutocomplete, renderEntityAutocomplete } from './entity-autocomplete.js';
import { vehicleCategory } from './logical-codes.js';
import { formatBRL } from './formatters.js';

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

// H-09 — veículos cobertos (marcados + os das frotas marcadas, sem repetir), prévia da conta e duplicidade.
export function subscriptionPreview(model = {}, { catalogId = '', vehicleIds = [], fleetIds = [], quantity = null } = {}) {
  const fleets = new Set(fleetIds.map(String));
  const picked = new Set(vehicleIds.map(String));
  const covered = (model.vehicles || []).filter(v => Number(v.archived || 0) === 0 && (picked.has(String(v.id)) || (v.fleet_id && fleets.has(String(v.fleet_id)))));
  const plan = (model.catalog || []).find(item => String(item.id) === String(catalogId));
  const unitCents = Number(plan?.price_cents || 0);
  const vehicles = covered.length;
  const qty = quantity == null || quantity === '' ? Math.max(1, vehicles) : Math.max(1, Number(quantity) || 1);
  const totalCents = unitCents * qty;
  const duplicates = covered.filter(v => (v.subscription_codes || []).length).map(v => ({ plate: v.plate || 'Sem placa', codes: v.subscription_codes }))
    .sort((a, b) => a.plate.localeCompare(b.plate, 'pt-BR'));
  const each = vehicles > 1 ? ` · ${vehicles} assinaturas (uma por veículo)` : '';
  const text = plan ? `${qty} veículo${qty === 1 ? '' : 's'} × ${formatBRL(unitCents)} = ${formatBRL(totalCents)}/mês${each}` : 'Escolha o plano para ver o valor.';
  const warning = duplicates.length
    ? `Atenção: já cobertos por outra assinatura ativa (cobraria 2×): ${duplicates.map(d => `${d.plate} (${d.codes.join(', ')})`).join('; ')}.`
    : '';
  return { vehicles, quantity: qty, unitCents, totalCents, duplicates, text, warning };
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
    <p class="muted sw-help">Assinatura é o plano mensal de cada veículo: todo mês gera uma cobrança no dia do vencimento. Marcando uma frota, cada veículo dela ganha a sua assinatura (a frota só agrupa e pode ser paga de uma vez). Quando a cobrança é paga, vira receita.</p>
    <div class="row">${clientField}<div class="field"><label>Plano mensal*</label><select name="catalog_id" required><option value="">Selecione o plano</option>${plans.map(item => `<option value="${escapeHtml(item.id)}" data-price="${Number(item.price_cents || 0)}">${escapeHtml(item.name || item.description || item.id)}</option>`).join('')}</select></div></div>
    <div class="row"><div class="field"><label>Início*</label><input type="date" name="start_on" value="${startOn}" required></div><div class="field"><label>Dia do vencimento*</label><input type="number" name="due_day" min="1" max="31" value="10" required></div><div class="field"><label>Quantidade*</label><input type="number" name="quantity" min="1" value="1" required><small class="muted">Automática: total de veículos marcados (frotas incluídas). Cada veículo vira uma assinatura.</small></div></div>
    <div data-subscription-targets>${targetChoices(model, selectedClientId)}</div>
    <div class="sw-preview" data-subscription-preview aria-live="polite"><strong data-preview-text>Escolha o plano para ver o valor.</strong><div class="sw-warning" data-preview-warning hidden></div></div>
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
  const quantityInput = form.querySelector('[name="quantity"]');
  let manualQuantity = false; // H-09: a quantidade segue os veículos até o usuário digitar outra
  const refresh = () => {
    const picked = type => [...form.querySelectorAll(`[data-subscription-target="${type}"]:checked`)].map(input => input.value);
    const preview = subscriptionPreview(model, { catalogId: form.querySelector('[name="catalog_id"]')?.value, vehicleIds: picked('vehicle'), fleetIds: picked('fleet'),
      quantity: manualQuantity ? quantityInput?.value : null });
    if (quantityInput && !manualQuantity) quantityInput.value = String(preview.quantity);
    const text = form.querySelector('[data-preview-text]'); if (text) text.textContent = preview.text;
    const warn = form.querySelector('[data-preview-warning]'); if (warn) { warn.hidden = !preview.warning; warn.textContent = preview.warning; }
    return preview;
  };
  form.addEventListener('change', event => { if (event.target?.matches?.('[data-subscription-target],[name="catalog_id"]')) refresh(); });
  if (quantityInput) quantityInput.addEventListener('input', () => { manualQuantity = quantityInput.value !== ''; refresh(); });
  if (typeof searchClients === 'function') bindEntityAutocomplete(form, {
    search: searchClients,
    onSelection: client => {
      if (targetHost) targetHost.innerHTML = targetChoices(model, client?.id || '');
      refresh();
    },
  });
  refresh();
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
