// H-24 (2.8.0) — Financeiro › Cobrança e Recibo PDF.
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderCollections, renderReminder } from '../frontend/ui/collections-view.js';
import { renderFinancePage } from '../frontend/pages/finance.js';

test('Cobrança: KPIs, lembrar hoje e inadimplência com ações', () => {
  const html = renderCollections({
    queue: [{ client_id: 'c1', code: 'CLI-0001', name: 'Joana', phone: '11988887777', stage: 'TODAY', stage_label: 'No dia', due_on: '2026-10-10', amount_cents: 5000 }],
    items: [{ client_id: 'c2', code: 'CLI-0002', name: 'Beto', phone: '', since: '2026-09-01', days: 39, months: 2, vehicles: 1, overdue_cents: 10000, last_reminder: null }],
    summary: { clients: 1, active_clients: 2, overdue_cents: 10000, clients_pct: 50 } });
  assert.match(html, /Lembrar hoje/); assert.match(html, /Inadimplência/); assert.match(html, /50%/);
  assert.match(html, /data-remind="c1" data-channel="WHATSAPP"/);
  assert.doesNotMatch(html, /data-remind="c2" data-channel="WHATSAPP"/, 'sem telefone, sem WhatsApp');
  assert.match(html, /data-bill="c2"/); assert.match(html, /data-pay-client="c2"/);
});

test('lembrete: app do WhatsApp, WhatsApp Web, copiar e confirmar envio', () => {
  const html = renderReminder({ name: 'Joana', stage_label: 'No dia', amount_cents: 5000, text: 'Olá, Joana!', whatsapp: '5511988887777', email_url: 'mailto:j@x.com' }, 'WHATSAPP');
  assert.match(html, /whatsapp:\/\/send\?phone=5511988887777&text=Ol%C3%A1%2C%20Joana!/);
  assert.match(html, /web\.whatsapp\.com\/send\?phone=5511988887777/);
  assert.match(html, /data-copy-reminder/); assert.match(html, /data-confirm-sent="WHATSAPP"/);
});

test('Financeiro tem a aba Cobrança e o Recibo PDF em cada recebimento', () => {
  const html = renderFinancePage({ payments: [{ id: 'p1', code: 'CLI-0001-R01', client_name: 'Joana', paid_on: '2026-10-09', amount_cents: 5000 }] }, 'payments');
  assert.match(html, /data-finance-tab="collections"/); assert.match(html, /data-receipt="p1"/);
});
