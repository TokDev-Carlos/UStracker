// AJ-06 — subscription count cell + anchored detail menu. Data always comes from /mobility/subscriptions.
import { formatBRL, formatDateBR } from './formatters.js';

const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const STATUS = { ACTIVE: 'Ativa', PAUSED: 'Pausada', CANCELLED: 'Cancelada', ENDED: 'Encerrada' };
const SCOPE = { DIRECT: 'Do veículo', FLEET: 'Via frota', DIRECT_AND_FLEET: 'Veículo e frota', FLEET_VEHICLE: 'Veículo da frota' };
const CHARGE = { OPEN: 'Em aberto', PARTIAL: 'Parcial', PAID: 'Paga', VOID: 'Anulada' };

/** Table cell: only the number of ACTIVE subscriptions. 0 is neutral (no button). */
export function subscriptionCountCell(count, { vehicleId = '', fleetId = '', label = '' } = {}) {
  const n = Number(count || 0);
  if (!n) return '<span class="subs-count subs-count-zero" aria-label="Nenhuma assinatura ativa">0</span>';
  const attr = vehicleId ? `data-subs-vehicle="${esc(vehicleId)}"` : `data-subs-fleet="${esc(fleetId)}"`;
  return `<button type="button" class="subs-count" ${attr} aria-haspopup="dialog" aria-expanded="false" title="Ver assinaturas${label ? ' de ' + esc(label) : ''}">${n}</button>`;
}

function itemHtml(item) {
  const plans = (item.plans || []).map(plan => `<tr><td>${esc(plan.name)}</td><td class="money">${plan.quantity}</td><td class="money">${formatBRL(plan.unit_price_cents || 0)}</td><td class="money">${formatBRL(plan.total_cents || 0)}</td></tr>`).join('');
  const charge = item.current_charge;
  return `<article class="subs-item subs-${esc(String(item.lifecycle_status || '').toLowerCase())}">
    <header><span class="ui-code">${esc(item.code || '')}</span><strong>${esc(item.plan_names || 'Plano')}</strong><span class="subs-status">${esc(STATUS[item.lifecycle_status] || item.lifecycle_status)}</span></header>
    <dl class="subs-facts"><dt>Valor mensal</dt><dd>${formatBRL(item.monthly_cents || 0)}</dd><dt>Início</dt><dd>${esc(formatDateBR(item.start_on, false) || '—')}</dd><dt>Vencimento</dt><dd>dia ${esc(item.due_day ?? '—')}</dd><dt>Origem</dt><dd>${esc(SCOPE[item.target_scope] || '—')}</dd>
      <dt>Cobrança ${esc(item.competence || '')}</dt><dd>${charge ? `${formatBRL(charge.amount_cents || 0)} · ${esc(CHARGE[charge.status] || charge.status)} · pago ${formatBRL(charge.paid_cents || 0)}` : 'Não gerada'}</dd>
      <dt>Recebido total</dt><dd>${formatBRL(item.received_cents || 0)}</dd></dl>
    ${plans ? `<table class="subs-plans"><thead><tr><th>Plano</th><th>Qtd</th><th>Unitário</th><th>Total</th></tr></thead><tbody>${plans}</tbody></table>` : ''}
    <div class="actions"><button type="button" class="ui-btn ui-btn-subtle" data-open-commercial="subscriptions" data-code="${esc(item.code || '')}">Abrir no Comercial</button></div>
  </article>`;
}

const competenceBR = comp => { const m = String(comp || '').match(/^(\d{4})-(\d{2})/); return m ? `${m[2]}/${m[1]}` : '—'; };

/** H-10 — charges and payments of the subscriptions that cover this vehicle/fleet. */
export function historyHtml(history = [], perVehicle = false) {
  if (!history.length) return '';
  const rows = history.map(h => `<tr><td>${esc(competenceBR(h.competence))}</td><td><span class="ui-code">${esc(h.subscription_code || '')}</span></td><td class="money">${formatBRL(h.amount_cents || 0)}</td>${perVehicle ? `<td class="money">${h.share_cents != null ? formatBRL(h.share_cents) : '—'}</td>` : ''}<td>${esc(CHARGE[h.status] || h.status)}</td><td>${h.paid_on ? esc(formatDateBR(h.paid_on, false)) : '—'}</td></tr>`).join('');
  return `<details class="subs-history" open><summary>Histórico de cobranças (${history.length})</summary><table class="subs-plans"><thead><tr><th>Mês</th><th>Assinatura</th><th>Cobrança</th>${perVehicle ? '<th>Por veículo</th>' : ''}<th>Situação</th><th>Pago em</th></tr></thead><tbody>${rows}</tbody></table></details>`;
}

export function renderSubscriptionDetail(detail = {}) {
  const target = detail.target || {};
  const title = target.kind === 'FLEET'
    ? `${target.name || 'Frota'} · ${target.vehicle_group_label || ''}`
    : [target.category_label, [target.brand, target.model].filter(Boolean).join(' '), target.plate].filter(Boolean).join(' · ');
  const items = detail.items || [];
  const active = items.filter(item => item.lifecycle_status === 'ACTIVE');
  const others = items.filter(item => item.lifecycle_status !== 'ACTIVE');
  return `<div class="subs-popover-head"><div><strong>${esc(title)}</strong> <span class="ui-code">${esc(target.code || '')}</span><span class="muted subs-client">${esc(target.client_name || '')} <span class="ui-code">${esc(target.client_code || '')}</span></span></div><button type="button" class="ui-icon-btn" data-subs-close aria-label="Fechar">×</button></div>
    <p class="subs-total">${active.length} ativa(s) · ${formatBRL(detail.active_monthly_cents || 0)}/mês</p>
    ${active.map(itemHtml).join('') || '<p class="muted">Nenhuma assinatura ativa.</p>'}
    ${others.length ? `<details class="subs-others"><summary>${others.length} pausada(s)/encerrada(s)</summary>${others.map(itemHtml).join('')}</details>` : ''}
    ${historyHtml(detail.history || [], target.kind === 'VEHICLE')}`;
}

export function closeSubscriptionPopover(documentRef = globalThis.document) {
  const current = documentRef.querySelector('#subsPopover');
  if (current) {
    const anchor = current._anchor;
    current.remove();
    if (anchor) { anchor.setAttribute('aria-expanded', 'false'); anchor.focus?.(); }
  }
}

/** Opens the menu next to the clicked count. ``load`` returns the detail JSON. */
export async function openSubscriptionPopover(anchor, load, { documentRef = globalThis.document, onCommercial } = {}) {
  closeSubscriptionPopover(documentRef);
  const pop = documentRef.createElement('div');
  pop.id = 'subsPopover'; pop.className = 'subs-popover'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'Assinaturas');
  pop._anchor = anchor; pop.innerHTML = '<p class="muted">Carregando…</p>';
  documentRef.body.append(pop);
  anchor.setAttribute('aria-expanded', 'true');
  const place = () => {
    const rect = anchor.getBoundingClientRect(); const width = Math.min(460, globalThis.innerWidth - 24);
    pop.style.width = width + 'px';
    pop.style.left = Math.max(12, Math.min(rect.left, globalThis.innerWidth - width - 12)) + 'px';
    const below = rect.bottom + 6; const maxH = Math.max(220, globalThis.innerHeight - below - 12);
    if (maxH < 260 && rect.top > 300) { pop.style.top = ''; pop.style.bottom = (globalThis.innerHeight - rect.top + 6) + 'px'; pop.style.maxHeight = (rect.top - 18) + 'px'; }
    else { pop.style.bottom = ''; pop.style.top = below + 'px'; pop.style.maxHeight = maxH + 'px'; }
  };
  place();
  try {
    pop.innerHTML = renderSubscriptionDetail(await load());
  } catch (error) {
    pop.innerHTML = `<p class="error">${esc(error.message)}</p>`;
  }
  place();
  pop.querySelector('[data-subs-close]')?.addEventListener('click', () => closeSubscriptionPopover(documentRef));
  pop.querySelectorAll('[data-open-commercial]').forEach(button => button.addEventListener('click', () => { closeSubscriptionPopover(documentRef); onCommercial?.(button.dataset.openCommercial, button.dataset.code); }));
  pop.querySelector('button')?.focus();
  return pop;
}
