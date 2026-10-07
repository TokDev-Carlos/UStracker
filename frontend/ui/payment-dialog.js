// AJ-12 — one-click "Registrar pagamento": client → subscription → months → date → value.
import { formatBRL, parseBRLInput } from './formatters.js';
import { bindMoneyInputs, renderMoneyInput } from './money-input.js';
import { bindEntityAutocomplete, renderEntityAutocomplete } from './entity-autocomplete.js';
import { closeOverlay, openDrawer } from './overlay.js';
import { bindActionForm } from './action-state.js';

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
export const PAYMENT_METHODS = ['PIX', 'Dinheiro', 'Cartão de crédito', 'Cartão de débito', 'Boleto', 'Transferência', 'Outro'];

export function localToday(now = new Date()) {
  const p = n => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}
export function competenceLabel(comp) {
  const m = String(comp || '').match(/^(\d{4})-(\d{2})/);
  return m ? `${m[2]}/${m[1]}` : '—';
}
export function shiftCompetence(comp, months) {
  const [y, m] = String(comp).slice(0, 7).split('-').map(Number);
  const i = y * 12 + (m - 1) + Number(months || 0);
  return `${String(Math.floor(i / 12)).padStart(4, '0')}-${String(i % 12 + 1).padStart(2, '0')}`;
}
/** Range and suggested value for N months starting at the first unpaid competence. */
export function paymentSummary(sub, months = 1, discountCents = 0, today = localToday()) {
  const n = Math.max(1, Math.min(36, Number(months) || 1));
  const from = sub?.next_due || '';
  const to = from ? shiftCompetence(from, n - 1) : '';
  const total = Number(sub?.monthly_cents || 0) * n;
  return { months: n, from, to, totalCents: total, suggestedCents: Math.max(0, total - Number(discountCents || 0)),
    advance: from ? Array.from({ length: n }, (_, i) => shiftCompetence(from, i)).filter(c => c > String(today).slice(0, 7)).length : 0 };
}
/** H-10 — what the subscription covers: fleets (plates), loose vehicles and value per vehicle. */
export function coverageLine(cov) {
  if (!cov || !Number(cov.vehicle_count || 0)) return '';
  const parts = (cov.fleets || []).map(f => `<span class="pay-cover-name">${esc(f.name)} (${(f.plates || []).length})</span>: ${esc((f.plates || []).join(', ') || 'sem veículos')}`);
  if ((cov.vehicles || []).length) parts.push(`<span class="pay-cover-name">Veículos</span>: ${esc(cov.vehicles.join(', '))}`);
  const n = Number(cov.vehicle_count);
  const per = cov.per_vehicle_cents != null ? ` · ${formatBRL(Number(cov.per_vehicle_cents))} por veículo` : '';
  return `<span class="pay-cover">Cobre: ${parts.join(' · ')}<br><small>${n} ${n === 1 ? 'veículo' : 'veículos'}${per}</small></span>`;
}

function subscriptionLine(sub) {
  const paid = sub.paid_through ? `Pago até ${competenceLabel(sub.paid_through)}` : 'Nenhum mês pago';
  const late = sub.overdue_months ? ` · <strong class="pay-late">${sub.overdue_months} ${sub.overdue_months === 1 ? 'mês' : 'meses'} em atraso</strong>` : ' · Em dia';
  return `${paid}${late} · Mensal ${formatBRL(Number(sub.monthly_cents || 0))}`;
}

export function renderPaymentDialog({ client = null, options = null, subscriptionId = '' } = {}) {
  const subs = options?.subscriptions || [];
  const chosen = subs.find(s => s.subscription_id === subscriptionId) || subs[0] || null;
  const today = options?.today || localToday();
  const clientField = client
    ? `<div class="pay-client"><span class="muted">Cliente</span><strong>${esc(client.display_name || client.legal_name || '')}</strong><input type="hidden" name="client_id" value="${esc(client.id)}"></div>`
    : `<div class="row">${renderEntityAutocomplete({ name: 'client_id', label: 'Cliente', required: true })}</div>`;
  const subsField = !options ? '<p class="muted" data-pay-hint>Escolha o cliente para ver as assinaturas.</p>'
    : !subs.length ? '<p class="notice" data-pay-hint>Este cliente não tem assinatura ativa.</p>'
      : `<div class="pay-subs" role="radiogroup" aria-label="Assinatura">${subs.map(s => `<label class="pay-sub${s === chosen ? ' is-selected' : ''}"><input type="radio" name="subscription_id" value="${esc(s.subscription_id)}"${s === chosen ? ' checked' : ''}><span><b>${esc(s.code || 'Assinatura')}</b> ${esc((s.plans || []).join(', '))}<small>${subscriptionLine(s)}</small>${coverageLine(s.coverage)}</span></label>`).join('')}</div>`;
  const enabled = Boolean(chosen);
  return `<form id="paymentDialogForm" class="pay-form">${clientField}${subsField}
  <fieldset class="pay-main"${enabled ? '' : ' disabled'}>
   <div class="row"><div class="field"><label>Quantos meses?</label><div class="pay-months"><button type="button" class="ui-btn ui-btn-subtle" data-pay-step="-1" aria-label="Menos um mês">−</button><input type="number" name="months" min="1" max="36" value="1" required><button type="button" class="ui-btn ui-btn-subtle" data-pay-step="1" aria-label="Mais um mês">+</button></div></div>
   <div class="field"><label>Data do pagamento</label><input type="date" name="paid_on" value="${esc(today)}" max="${esc(today)}" required></div>
   <div class="field"><label>Forma</label><select name="method">${PAYMENT_METHODS.map(m => `<option>${esc(m)}</option>`).join('')}</select></div></div>
   <p class="pay-range" data-pay-range></p>
   <div class="row">${renderMoneyInput({ name: 'amount', label: 'Valor recebido', required: true })}${renderMoneyInput({ name: 'discount', label: 'Desconto (opcional)' })}</div>
  </fieldset>
  <div class="actions"><button class="ui-btn ui-btn-primary"${enabled ? '' : ' disabled'}>Confirmar pagamento</button></div></form>`;
}

/** Opens the dialog. `api(path, opt)` and `search(query)` come from app.js. */
export function openPaymentDialog({ api, search, client = null, subscriptionId = '', notify = () => {}, onSuccess = () => {} } = {}) {
  let options = null;
  let currentClient = client;
  const drawer = openDrawer({ title: 'Registrar pagamento', subtitle: 'Escolha a assinatura e quantos meses o cliente está pagando.', content: '<div data-pay-root></div>' });
  const root = drawer.querySelector('[data-pay-root]');
  const draw = () => {
    root.innerHTML = renderPaymentDialog({ client: currentClient, options, subscriptionId });
    const form = root.querySelector('#paymentDialogForm');
    bindMoneyInputs(form);
    if (!currentClient) bindEntityAutocomplete(form, { search, onSelection: item => { if (item) { currentClient = item; load(); } } });
    const amount = form.querySelector('[name=amount]');
    let amountTouched = false;
    amount?.addEventListener('input', () => { amountTouched = true; });
    const update = () => {
      const sub = (options?.subscriptions || []).find(s => s.subscription_id === form.querySelector('[name=subscription_id]:checked')?.value);
      form.querySelectorAll('.pay-sub').forEach(label => label.classList.toggle('is-selected', label.querySelector('input').checked));
      if (!sub) return;
      let discount = 0;
      try { discount = form.discount.value.trim() ? parseBRLInput(form.discount.value) : 0; } catch { discount = 0; }
      const s = paymentSummary(sub, form.months.value, discount, options?.today);
      const range = s.months === 1 ? competenceLabel(s.from) : `${competenceLabel(s.from)} a ${competenceLabel(s.to)}`;
      form.querySelector('[data-pay-range]').innerHTML = `Cobre <b>${esc(range)}</b> · ${s.months} × ${esc(formatBRL(Number(sub.monthly_cents || 0)))} = <b>${esc(formatBRL(s.totalCents))}</b>${s.advance ? ` · ${s.advance} ${s.advance === 1 ? 'mês adiantado' : 'meses adiantados'}` : ''}`;
      if (!amountTouched) amount.value = formatBRL(s.suggestedCents);
    };
    form.querySelectorAll('[data-pay-step]').forEach(button => button.onclick = () => {
      form.months.value = Math.max(1, Math.min(36, Number(form.months.value || 1) + Number(button.dataset.payStep))); update();
    });
    form.addEventListener('input', event => { if (event.target.name !== 'amount') update(); });
    form.addEventListener('change', event => { if (event.target.name === 'subscription_id') { subscriptionId = event.target.value; amountTouched = false; } update(); });
    form.discount?.addEventListener('blur', update);
    update();
    bindActionForm(form, {
      key: 'payment-dialog',
      action: async () => {
        const body = { subscription_id: form.querySelector('[name=subscription_id]:checked')?.value, months: Number(form.months.value || 1),
          paid_on: form.paid_on.value, method: form.method.value, amount: form.amount.value };
        if (form.discount.value.trim() && form.discount.value.trim() !== 'R$ 0,00') body.discount = form.discount.value;
        const rec = await api('/billing/payments', { method: 'POST', body: JSON.stringify(body) });
        closeOverlay();
        notify({ type: 'success', message: `Pagamento registrado. Pago até ${competenceLabel(rec.paid_through)}.` + (rec.credit_cents ? ` Crédito de ${formatBRL(rec.credit_cents)} gerado.` : '') });
        return rec;
      },
      refresh: onSuccess, notify,
    });
  };
  const load = async () => {
    root.setAttribute('aria-busy', 'true');
    try { options = await api('/billing/clients/' + encodeURIComponent(currentClient.id)); }
    catch (error) { notify({ type: 'error', message: error.message }); options = { subscriptions: [] }; }
    root.removeAttribute('aria-busy');
    if (!subscriptionId && options.subscriptions?.length) subscriptionId = options.subscriptions[0].subscription_id;
    draw();
  };
  draw();
  if (currentClient) load();
  return drawer;
}
