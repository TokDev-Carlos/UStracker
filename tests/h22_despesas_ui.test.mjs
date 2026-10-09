// H-22 (2.8.0) — Despesas: período, destaque de vencimento, Ações e Abrir.
import test from 'node:test';
import assert from 'node:assert/strict';
import { dueFlag, filterExpenses, renderExpenseRows, renderExpenseOpen, renderDeleteChoice } from '../frontend/ui/expense-view.js';

const T = '2026-10-09';
const rows = [
  { id: 'a', description: 'Atrasada', competence: '2026-09', due_on: '2026-09-05', status: 'OPEN', repeat: 'MONTHLY', expected_amount_cents: 5000 },
  { id: 'b', description: 'Vence logo', competence: '2026-10', due_on: '2026-10-11', status: 'OPEN', repeat: 'ONCE', expected_amount_cents: 1000 },
  { id: 'c', description: 'Paga mês passado', competence: '2026-09', due_on: '2026-09-20', status: 'PAID', repeat: 'ANNUAL', expected_amount_cents: 9000 },
  { id: 'd', description: 'Futura', competence: '2026-11', due_on: '2026-11-02', status: 'OPEN', repeat: 'MONTHLY', expected_amount_cents: 5000 },
];
const ids = list => list.map(x => x.id).sort().join('');

test('período: padrão mês atual + atrasadas; próximos 30; mês passado; repetição', () => {
  assert.equal(ids(filterExpenses(rows, {}, T)), 'ab');
  assert.equal(ids(filterExpenses(rows, { period: 'next30' }, T)), 'bd');
  assert.equal(ids(filterExpenses(rows, { period: 'last' }, T)), 'ac');
  assert.equal(ids(filterExpenses(rows, { period: 'all', repeat: 'MONTHLY' }, T)), 'ad');
  assert.equal(ids(filterExpenses(rows, { period: 'custom', from: '2026-10-01', to: '2026-10-31' }, T)), 'b');
});

test('destaque: atrasada e vence em até 3 dias', () => {
  assert.deepEqual(rows.map(x => dueFlag(x, T)), ['late', 'soon', '', '']);
  const html = renderExpenseRows(rows, T);
  assert.match(html, /class="exp-late"/); assert.match(html, /Atrasada 34 dias/);
  assert.match(html, /class="exp-soon"/); assert.match(html, /Vence em 2 dias/);
});

test('Ações: Abrir | Editar | Excluir, nada mais na linha', () => {
  const html = renderExpenseRows([rows[0]], T);
  assert.deepEqual([...html.matchAll(/data-expense-(\w+)=/g)].map(m => m[1]), ['open', 'edit', 'delete']);
});

test('Abrir: meses da recorrente com marcação e pagamento em lote', () => {
  const series = { template_id: 't', repeat_active: 1, months: [
    { competence: '2026-09', due_on: '2026-09-05', amount_cents: 5000, status: 'OPEN', when: 'past' },
    { competence: '2026-10', due_on: '2026-10-05', amount_cents: 5000, status: 'PAID', paid_on: '2026-10-05', when: 'current' },
    { competence: '2026-11', due_on: '2026-11-05', amount_cents: 5000, status: 'FUTURE', when: 'future' }] };
  const html = renderExpenseOpen(rows[0], { series, today: T });
  assert.match(html, /Meses da repetição/); assert.match(html, /value="2026-10" disabled/);
  assert.match(html, /Pagar meses marcados/); assert.match(html, /Parar repetição/); assert.match(html, /Pagar hoje/);
  assert.match(html, /Vencimento de cada mês/);
});

test('Excluir recorrente oferece só esta / esta e as próximas', () => {
  const html = renderDeleteChoice(rows[0]);
  assert.match(html, /data-delete-scope="ONE"/); assert.match(html, /data-delete-scope="FORWARD"/);
});
