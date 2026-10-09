// 2.8.0 — Despesas: filtro de período, destaque de vencimento, Ações (Abrir | Editar | Excluir) e a tela Abrir.
import { formatBRL, formatDateBR } from './formatters.js';
import { codeTag } from './logical-codes.js';

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const STATUS = { OPEN: 'A pagar', PARTIAL: 'Parcial', PAID: 'Paga', FUTURE: 'Futura' };
export const EXPENSE_PERIODS = [['current', 'Mês atual + atrasadas'], ['next30', 'Próximos 30 dias'], ['last', 'Mês passado'], ['year', 'Este ano'], ['all', 'Tudo'], ['custom', 'De / Até']];
export const EXPENSE_REPEAT_FILTER = [['', 'Todas'], ['MONTHLY', 'Mensal'], ['ANNUAL', 'Anual'], ['ONCE', 'Única']];

const DAY = 86400000;
const toDate = iso => new Date(`${String(iso).slice(0, 10)}T00:00:00`);
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export function daysUntil(due, today) { return Math.round((toDate(due) - toDate(today)) / DAY); }

/** 'late' (vencida e não paga), 'soon' (vence em até 3 dias) ou ''. */
export function dueFlag(x, today) {
  if (!x?.due_on || x.status === 'PAID') return '';
  const d = daysUntil(x.due_on, today);
  return d < 0 ? 'late' : d <= 3 ? 'soon' : '';
}
export function dueBadge(x, today) {
  const flag = dueFlag(x, today); if (!flag) return '';
  const d = daysUntil(x.due_on, today);
  const text = flag === 'late' ? `Atrasada ${-d} ${-d === 1 ? 'dia' : 'dias'}` : d === 0 ? 'Vence hoje' : `Vence em ${d} ${d === 1 ? 'dia' : 'dias'}`;
  return ` <span class="due-flag due-${flag}">${text}</span>`;
}

export function filterExpenses(items = [], { period = 'current', repeat = '', from = '', to = '' } = {}, today) {
  const t = String(today).slice(0, 10); const month = t.slice(0, 7);
  const prev = (() => { const d = toDate(t); d.setDate(1); d.setMonth(d.getMonth() - 1); return iso(d).slice(0, 7); })();
  const plus30 = iso(new Date(toDate(t).getTime() + 30 * DAY));
  const due = x => String(x.due_on || `${x.competence}-01`).slice(0, 10);
  const keep = x => {
    if (repeat && (x.repeat || 'ONCE') !== repeat) return false;
    switch (period) {
      case 'current': return String(x.competence).slice(0, 7) === month || (x.status !== 'PAID' && due(x) < t);
      case 'next30': return due(x) >= t && due(x) <= plus30;
      case 'last': return String(x.competence).slice(0, 7) === prev;
      case 'year': return due(x).slice(0, 4) === t.slice(0, 4);
      case 'custom': return (!from || due(x) >= from) && (!to || due(x) <= to);
      default: return true;
    }
  };
  return items.filter(keep);
}

export function renderExpenseFilters(state = {}) {
  const p = state.period || 'current';
  return `<div class="expense-filters" data-expense-filters><div class="field"><label>Período</label><select name="period">${EXPENSE_PERIODS.map(([v, l]) => `<option value="${v}"${v === p ? ' selected' : ''}>${l}</option>`).join('')}</select></div>
  <div class="field" data-expense-custom${p === 'custom' ? '' : ' hidden'}><label>De</label><input type="date" name="from" value="${esc(state.from || '')}"></div>
  <div class="field" data-expense-custom${p === 'custom' ? '' : ' hidden'}><label>Até</label><input type="date" name="to" value="${esc(state.to || '')}"></div>
  <div class="field"><label>Repetição</label><select name="repeat">${EXPENSE_REPEAT_FILTER.map(([v, l]) => `<option value="${v}"${v === (state.repeat || '') ? ' selected' : ''}>${l}</option>`).join('')}</select></div></div>`;
}

const actions = x => `<div class="row-actions"><button type="button" class="ui-btn ui-btn-primary ui-btn-sm" data-expense-open="${esc(x.id)}">Abrir</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-expense-edit="${esc(x.id)}">Editar</button>${x.converted_sale_id ? '' : `<button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-expense-delete="${esc(x.id)}">Excluir</button>`}</div>`;

export function renderExpenseRows(items = [], today) {
  return items.map(x => { const flag = dueFlag(x, today); return `<tr class="${flag ? `exp-${flag}` : ''}"><td><span class="cat-chip">${esc(x.category_label || x.category)}</span></td><td>${esc(x.description)}${x.sale_code ? ` <span class="muted">→ venda</span> ${codeTag(x.sale_code)}` : ''}</td><td><span class="badge ${x.repeat === 'ONCE' || !x.repeat ? 'badge-muted' : 'badge-info'}">${esc(x.repeat_label || 'Única')}</span></td><td>${formatDateBR(x.due_on || x.competence)}${dueBadge(x, today)}</td><td class="num">${formatBRL(x.expected_amount_cents)}</td><td><span class="badge ${x.status === 'PAID' ? 'badge-ok' : x.status === 'PARTIAL' ? 'badge-warn' : 'badge-alert'}">${esc(STATUS[x.status] || x.status)}</span></td><td>${actions(x)}</td></tr>`; }).join('')
    || '<tr><td colspan="7" class="muted">Nenhuma despesa neste período.</td></tr>';
}

const compLabel = c => { const m = String(c || '').match(/^(\d{4})-(\d{2})/); return m ? `${m[2]}/${m[1]}` : '—'; };

/** Tela Abrir: dados, pagamentos, ações e (recorrente) os meses com pagamento retroativo/adiantado em lote. */
export function renderExpenseOpen(x = {}, { series = null, payments = [], today } = {}) {
  const open = Number(x.open_cents ?? (Number(x.expected_amount_cents || 0) - Number(x.paid_cents || 0)));
  const buttons = [];
  if (x.status !== 'PAID') buttons.push(`<button type="button" class="ui-btn ui-btn-primary" data-open-pay="${esc(x.id)}">Pagar hoje (${esc(formatBRL(open))})</button>`);
  if ((x.repeat || 'ONCE') === 'ONCE' && !x.converted_sale_id) buttons.push(`<button type="button" class="ui-btn ui-btn-subtle" data-open-sell="${esc(x.id)}">Vender ao cliente</button>`);
  if (series?.template_id && Number(series.repeat_active)) buttons.push(`<button type="button" class="ui-btn ui-btn-subtle" data-open-stop="${esc(series.template_id)}">Parar repetição</button>`);
  const info = `<dl class="expense-info"><dt>Categoria</dt><dd>${esc(x.category_label || x.category)}</dd><dt>Repetição</dt><dd>${esc(x.repeat_label || 'Única')}</dd><dt>Vencimento</dt><dd>${formatDateBR(x.due_on)}${dueBadge(x, today)}</dd><dt>Valor</dt><dd>${formatBRL(Number(x.expected_amount_cents || 0))}</dd><dt>Pago</dt><dd>${formatBRL(Number(x.paid_cents || 0))}</dd>${x.supplier ? `<dt>Fornecedor</dt><dd>${esc(x.supplier)}</dd>` : ''}</dl>`;
  const pays = payments.length ? `<h4>Pagamentos</h4><ul class="expense-pays">${payments.map(p => `<li>${formatDateBR(p.paid_on)} · ${formatBRL(Number(p.amount_cents || 0))}${p.reversed_at ? ' <span class="muted">(estornado)</span>' : ''}</li>`).join('')}</ul>` : '';
  let months = '';
  if (series?.months?.length) {
    const rows = series.months.map(m => {
      const paid = m.status === 'PAID';
      const flag = dueFlag(m, today);
      return `<tr class="${flag ? `exp-${flag}` : ''}${m.when === 'future' ? ' exp-future' : ''}"><td><input type="checkbox" name="competence" value="${esc(m.competence)}"${paid ? ' disabled' : ''} aria-label="Marcar ${esc(compLabel(m.competence))}"></td><td>${esc(compLabel(m.competence))}</td><td>${formatDateBR(m.due_on)}${dueBadge(m, today)}</td><td class="num">${formatBRL(m.amount_cents)}</td><td><span class="badge ${paid ? 'badge-ok' : m.status === 'FUTURE' ? 'badge-muted' : m.status === 'PARTIAL' ? 'badge-warn' : 'badge-alert'}">${esc(STATUS[m.status] || m.status)}</span>${m.paid_on ? ` <small class="muted">${formatDateBR(m.paid_on)}</small>` : ''}</td></tr>`;
    }).join('');
    months = `<h4>Meses da repetição</h4><p class="muted">Marque os meses e pague de uma vez: atrasados (com a data em que foram pagos de verdade), o atual e até 12 meses adiantados.</p>
    <form id="expenseMonthsForm"><div class="months-quick"><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-mark="late">Marcar atrasados</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-mark="none">Limpar</button></div>
    <div class="table-wrap"><table class="compact-table"><thead><tr><th></th><th>Mês</th><th>Vencimento</th><th class="num">Valor</th><th>Situação</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="row"><div class="field"><label>Data do pagamento</label><div class="segmented" role="radiogroup"><label><input type="radio" name="when" value="DUE" checked><span>Vencimento de cada mês</span></label><label><input type="radio" name="when" value="DATE"><span>Outra data</span></label></div></div><div class="field"><label>Data</label><input type="date" name="paid_on" value="${esc(today)}" max="${esc(today)}"></div></div>
    <p class="pay-range" data-months-total>Nenhum mês marcado.</p><div class="actions"><button class="ui-btn ui-btn-primary">Pagar meses marcados</button></div></form>`;
  }
  return `<div class="expense-open">${info}<div class="actions">${buttons.join('')}</div>${pays}${months}</div>`;
}

export function monthsPayload(form) {
  const competences = [...form.querySelectorAll('[name=competence]:checked')].map(i => i.value);
  const when = form.querySelector('[name=when]:checked')?.value || 'DUE';
  return { competences, paid_on: when === 'DUE' ? 'DUE' : form.querySelector('[name=paid_on]').value };
}

/** Excluir recorrente: escolha entre só esta e esta + as próximas. */
export function renderDeleteChoice(x = {}) {
  return `<div class="delete-choice"><p>Excluir <b>${esc(x.description)}</b> de ${esc(compLabel(x.competence))}?</p><p class="muted">Vai para a Lixeira (14 dias) e pode ser restaurada. Os meses anteriores ficam.</p>
  <div class="actions"><button type="button" class="ui-btn ui-btn-subtle" data-close-overlay>Cancelar</button><button type="button" class="ui-btn ui-btn-del" data-delete-scope="ONE">Só esta</button><button type="button" class="ui-btn ui-btn-del" data-delete-scope="FORWARD">Esta e as próximas (para a repetição)</button></div></div>`;
}
