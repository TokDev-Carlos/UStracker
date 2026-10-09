// 2.8.0 — Financeiro › Cobrança: quem lembrar hoje (régua) e inadimplência.
import { formatBRL, formatDateBR } from './formatters.js';
import { codeTag } from './logical-codes.js';

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const STAGE_CLASS = { BEFORE: 'badge-info', TODAY: 'badge-warn', LATE3: 'badge-alert', LATE7: 'badge-alert' };

const buttons = (clientId, phone) => `<div class="row-actions">${phone ? `<button type="button" class="ui-btn ui-btn-primary ui-btn-sm" data-remind="${esc(clientId)}" data-channel="WHATSAPP">WhatsApp</button>` : ''}<button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-remind="${esc(clientId)}" data-channel="EMAIL">E-mail</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-bill="${esc(clientId)}">2ª via PDF</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-pay-client="${esc(clientId)}">Registrar pagamento</button></div>`;

export function renderCollections(data = {}) {
  const s = data.summary || {};
  const queue = data.queue || []; const items = data.items || [];
  const q = queue.map(r => `<tr><td>${codeTag(r.code)} ${esc(r.name)}</td><td><span class="badge ${STAGE_CLASS[r.stage] || ''}">${esc(r.stage_label)}</span></td><td>${formatDateBR(r.due_on)}</td><td class="num">${formatBRL(r.amount_cents)}</td><td>${buttons(r.client_id, r.phone)}</td></tr>`).join('')
    || '<tr><td colspan="5" class="muted">Ninguém para lembrar hoje.</td></tr>';
  const o = items.map(r => `<tr class="${r.days >= 7 ? 'exp-late' : ''}"><td>${codeTag(r.code)} ${esc(r.name)}</td><td>${formatDateBR(r.since)}</td><td class="num">${r.days}</td><td class="num">${r.months}${r.vehicles > 1 ? ` <small class="muted">(${r.vehicles} veículos)</small>` : ''}</td><td class="num"><b>${formatBRL(r.overdue_cents)}</b></td><td>${r.last_reminder ? `${esc({ WHATSAPP: 'WhatsApp', EMAIL: 'E-mail', OUTRO: 'Outro' }[r.last_reminder.channel] || r.last_reminder.channel)} · ${formatDateBR(r.last_reminder.sent_at)}` : '<span class="muted">—</span>'}</td><td>${buttons(r.client_id, r.phone)}</td></tr>`).join('')
    || '<tr><td colspan="7" class="muted">Nenhum cliente em atraso.</td></tr>';
  return `<div class="kpi-strip"><div class="kpi-unpaid"><span>Em atraso</span><b>${formatBRL(Number(s.overdue_cents || 0))}</b></div><div><span>Clientes inadimplentes</span><b>${Number(s.clients || 0)} de ${Number(s.active_clients || 0)}</b></div><div><span>Inadimplência</span><b>${String(s.clients_pct ?? 0).replace('.', ',')}%</b></div><div><span>Lembrar hoje</span><b>${queue.length}</b></div></div>
  <div class="panel"><h3>Lembrar hoje</h3><p class="muted">Régua: 3 dias antes, no dia, 3 e 7 dias depois do vencimento. O botão abre o WhatsApp ou o e-mail com a mensagem e o PIX prontos; o envio fica registrado.</p><div class="table-wrap"><table class="compact-table"><thead><tr><th>Cliente</th><th>Etapa</th><th>Vencimento</th><th class="num">Valor</th><th>Ações</th></tr></thead><tbody>${q}</tbody></table></div></div>
  <div class="panel"><h3>Inadimplência</h3><div class="table-wrap"><table class="compact-table"><thead><tr><th>Cliente</th><th>Em atraso desde</th><th class="num">Dias</th><th class="num">Meses</th><th class="num">Valor</th><th>Último lembrete</th><th>Ações</th></tr></thead><tbody>${o}</tbody></table></div></div>`;
}

/** Tela do lembrete: mostra a mensagem e os jeitos de enviar (app do WhatsApp, WhatsApp Web, copiar, e-mail). */
export function renderReminder(m = {}, channel = 'WHATSAPP') {
  const text = esc(m.text || '');
  const wa = m.whatsapp;
  const enc = encodeURIComponent(m.text || '');
  const links = channel === 'EMAIL'
    ? `<a class="ui-btn ui-btn-primary" href="${esc(m.email_url)}" data-sent="EMAIL">Abrir e-mail</a>`
    : wa ? `<a class="ui-btn ui-btn-primary" href="whatsapp://send?phone=${esc(wa)}&text=${enc}" data-sent="WHATSAPP">Abrir no WhatsApp</a><a class="ui-btn ui-btn-subtle" href="https://web.whatsapp.com/send?phone=${esc(wa)}&text=${enc}" target="_blank" rel="noopener" data-sent="WHATSAPP">WhatsApp Web</a>` : '<p class="notice">Cliente sem telefone válido.</p>';
  return `<div class="reminder"><p><span class="badge">${esc(m.stage_label || '')}</span> ${esc(m.name || '')} · ${formatBRL(Number(m.amount_cents || 0))}</p><textarea class="reminder-text" rows="9" readonly>${text}</textarea>
  <div class="actions">${links}<button type="button" class="ui-btn ui-btn-subtle" data-copy-reminder>Copiar mensagem</button></div>
  <p class="muted">Depois de enviar, confirme abaixo para registrar.</p><div class="actions"><button type="button" class="ui-btn ui-btn-primary" data-confirm-sent="${esc(channel)}">Enviado</button></div></div>`;
}
