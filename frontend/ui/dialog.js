// V-05 — small in-app dialog on top of any drawer, replacing the browser's confirm()/alert().
// openDialog resolves with the chosen action value (or null when closed with Esc/×/backdrop).
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

export function closeDialog(documentRef = globalThis.document) {
  documentRef.querySelector('#uiDialog')?.remove();
}

export function renderDialog({ title = '', body = '', actions = [] } = {}) {
  const buttons = actions.map((action, index) => `<button type="button" class="ui-btn ${action.kind === 'danger' ? 'ui-btn-danger' : action.kind === 'primary' ? 'ui-btn-primary' : 'ui-btn-secondary'}" data-dialog-action="${index}">${esc(action.label)}</button>`).join('');
  return `<div class="ui-dialog-backdrop" data-dialog-close></div><section class="ui-dialog" role="alertdialog" aria-modal="true" aria-labelledby="uiDialogTitle" tabindex="-1">
    <header class="ui-dialog-head"><h3 id="uiDialogTitle">${esc(title)}</h3><button type="button" class="ui-icon-btn" data-dialog-close aria-label="Fechar">×</button></header>
    <div class="ui-dialog-body">${body}</div>${buttons ? `<footer class="ui-dialog-actions">${buttons}</footer>` : ''}</section>`;
}

export function openDialog({ title, body = '', actions = [{ label: 'OK', kind: 'primary', value: true }], documentRef = globalThis.document, onOpen } = {}) {
  closeDialog(documentRef);
  return new Promise(resolve => {
    const host = documentRef.createElement('div');
    host.id = 'uiDialog';
    host.className = 'ui-dialog-host';
    host.innerHTML = renderDialog({ title, body, actions });
    const finish = value => { host.remove(); resolve(value); };
    host.querySelectorAll('[data-dialog-close]').forEach(element => { element.onclick = () => finish(null); });
    host.querySelectorAll('[data-dialog-action]').forEach(button => { button.onclick = () => finish(actions[Number(button.dataset.dialogAction)]?.value ?? null); });
    host.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); finish(null); } });
    documentRef.body.append(host);
    onOpen?.(host, finish);
    globalThis.setTimeout?.(() => (host.querySelector('.ui-dialog-actions .ui-btn-primary,.ui-dialog-actions .ui-btn-danger') || host.querySelector('.ui-dialog'))?.focus?.({ preventScroll: true }), 20);
  });
}

/** Yes/no question. Resolves true only when the main button is chosen. */
export async function confirmDialog(message, { title = 'Confirmar', okLabel = 'Confirmar', cancelLabel = 'Cancelar', danger = false, documentRef } = {}) {
  const value = await openDialog({ title, body: `<p>${esc(message)}</p>`, documentRef,
    actions: [{ label: cancelLabel, value: false }, { label: okLabel, kind: danger ? 'danger' : 'primary', value: true }] });
  return value === true;
}

// V-02 — "Placa já cadastrada": who owns it, with the vehicle photo when there is one.
export function renderPlateOwner(vehicle = {}) {
  const photo = vehicle.media_id
    ? `<img src="/api/v1/media/${esc(encodeURIComponent(vehicle.media_id))}/operational" alt="Foto do veículo">`
    : '<span class="plate-owner-noimg" aria-hidden="true">Sem foto</span>';
  const title = [vehicle.brand, vehicle.model, vehicle.year].filter(Boolean).join(' ');
  return `<div class="plate-owner"><div class="plate-owner-photo">${photo}</div><dl class="plate-owner-facts">
    <dt>Placa</dt><dd><strong class="plate-owner-plate">${esc(vehicle.plate || '')}</strong></dd>
    <dt>Veículo</dt><dd>${esc(title || vehicle.type || '—')}${vehicle.code ? ` <span class="ui-code">${esc(vehicle.code)}</span>` : ''}</dd>
    <dt>Cliente</dt><dd>${esc(vehicle.client_name || '—')}${vehicle.client_code ? ` <span class="ui-code">${esc(vehicle.client_code)}</span>` : ''}</dd>
    <dt>Frota</dt><dd>${esc(vehicle.fleet_name || 'Particular')}</dd></dl></div>`;
}

export function openPlateOwnerDialog(vehicle, { onOpenClient, documentRef } = {}) {
  return openDialog({
    title: 'Placa já cadastrada',
    body: `<p class="muted">Esta placa já está em outro cadastro. Cada placa só pode existir uma vez.</p>${renderPlateOwner(vehicle)}`,
    documentRef,
    actions: [{ label: 'Fechar', value: 'close' }, ...(onOpenClient && vehicle?.client_id ? [{ label: 'Abrir ficha do cliente', kind: 'primary', value: 'open' }] : [])],
  }).then(choice => { if (choice === 'open') onOpenClient(vehicle.client_id); return choice; });
}
