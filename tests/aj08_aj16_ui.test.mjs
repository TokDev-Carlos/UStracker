import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { competenceLabel, paymentSummary, renderPaymentDialog, shiftCompetence } from '../frontend/ui/payment-dialog.js';
import { EXPENSE_CATEGORIES, renderExpenseForm, renderFinancePage } from '../frontend/pages/finance.js';
import { renderCatalogPage } from '../frontend/pages/catalog.js';
import { renderActionMenu } from '../frontend/ui/action-menu.js';
import { renderCommercialPage, renderSubscriptionAmendForm, subscriptionMenuItems } from '../frontend/pages/commercial.js';

test('AJ-12: resumo do pagamento cobre atrasados e adiantados', () => {
  assert.equal(shiftCompetence('2026-11', 3), '2027-02');
  assert.equal(competenceLabel('2026-08'), '08/2026');
  const s = paymentSummary({ next_due: '2026-08', monthly_cents: 10000, overdue_months: 2 }, 5, 3000, '2026-10-03');
  assert.deepEqual([s.from, s.to, s.totalCents, s.suggestedCents, s.advance], ['2026-08', '2026-12', 50000, 47000, 2]);
  const html = renderPaymentDialog({ client: { id: 'c1', display_name: 'Alfa' }, options: { today: '2026-10-03', subscriptions: [{ subscription_id: 's1', code: 'CLI-0001-A01', monthly_cents: 10000, next_due: '2026-10', overdue_months: 0, plans: ['Plano'] }] } });
  assert.match(html, /name="paid_on" value="2026-10-03" max="2026-10-03"/);
  assert.match(html, /name="subscription_id" value="s1" checked/);
  assert.match(html, /data-pay-step="1"/);
});

test('AJ-13: despesa simples tem Repetição e categorias fixas, sem Competência', () => {
  const form = renderExpenseForm();
  for (const label of ['Mensal', 'Anual', 'Única']) assert.match(form, new RegExp(`<span>${label}</span>`));
  for (const category of EXPENSE_CATEGORIES) assert.ok(form.includes(`<option>${category}</option>`), category);
  assert.doesNotMatch(form, /Competência/);
  const page = renderFinancePage({ expenses: [{ id: 'e1', category: 'Equipamentos', description: 'Rastreador', repeat: 'ONCE', repeat_label: 'Única', status: 'OPEN', expected_amount_cents: 100, paid_cents: 0 }] }, 'expenses');
  assert.match(page, /data-expense-pay="e1"/);
  assert.match(page, /data-expense-sell="e1"/);
  assert.match(page, /data-expense-delete="e1"/);
  assert.match(renderFinancePage({}), /data-open-payment/);
});

test('AJ-11: produto usado é arquivado, não excluído; custos removíveis', () => {
  const html = renderCatalogPage({ items: [{ id: 'p1', code: 'PRD001', name: 'A', category: 'MENSAL', price_cents: 100, cost_cents: 30, active: 1, usage_count: 2 }, { id: 'p2', code: 'PRD002', name: 'B', category: 'AVULSA', price_cents: 50, cost_cents: 0, active: 1, usage_count: 0 }] });
  assert.match(html, /data-catalog-delete="p1" data-used="2">Arquivar/);
  assert.match(html, /data-catalog-delete="p2" data-used="0">Excluir/);
  assert.match(html, /data-cost-remove/);
  assert.match(html, /data-cost-add/);
});

test('AJ-10: menu Ações por assinatura conforme a situação', () => {
  const active = subscriptionMenuItems({ lifecycle_status: 'ACTIVE' }).filter(x => !x.hidden).map(x => x.key).filter(Boolean);
  assert.deepEqual(active, ['pay', 'amend', 'purchase', 'profile', 'pause', 'cancel']);
  const paused = subscriptionMenuItems({ lifecycle_status: 'PAUSED' }).filter(x => !x.hidden).map(x => x.key).filter(Boolean);
  assert.deepEqual(paused, ['amend', 'purchase', 'profile', 'resume', 'cancel']);
  const page = renderCommercialPage({ subscriptions: [{ id: 's1', code: 'CLI-0001-A01', client_name: 'Alfa', lifecycle_status: 'ACTIVE', total_cents: 100, paid_through: '2026-10', overdue_months: 0 }] });
  assert.match(page, /data-sub-actions="s1"/);
  assert.match(page, /10\/2026/);
  assert.match(renderActionMenu([{ label: 'X', danger: true }]), /is-danger/);
  const form = renderSubscriptionAmendForm({ client_id: 'c1', due_day: 7, items: [{ catalog_id: 'p1', quantity: 2, unit_price_cents: 500 }], targets: [{ vehicle_id: 'v1' }] }, { catalog: [{ id: 'p1', name: 'Plano', price_cents: 500, active: 1 }], vehicles: [{ id: 'v1', client_id: 'c1', plate: 'AAA' }, { id: 'v2', client_id: 'x' }] });
  assert.match(form, /value="v1" checked/);
  assert.doesNotMatch(form, /value="v2"/);
});

test('AJ-14/15: tema carregado por último e movimento respeita redução de movimento', () => {
  const html = fs.readFileSync(new URL('../frontend/index.html', import.meta.url), 'utf8');
  assert.ok(html.indexOf('ui/theme.css') > html.indexOf('styles.css'));
  const css = fs.readFileSync(new URL('../frontend/ui/theme.css', import.meta.url), 'utf8');
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.match(css, /--us-signal-500/);
});
