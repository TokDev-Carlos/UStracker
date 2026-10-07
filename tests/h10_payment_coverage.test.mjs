// H-10 (2.4.0): pagamento mostra plano, frota(s), placas e valor por veículo; ficha do veículo/frota mostra o histórico.
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderPaymentDialog, coverageLine } from '../frontend/ui/payment-dialog.js';
import { renderSubscriptionDetail } from '../frontend/ui/subscription-popover.js';

const coverage = { fleets: [{ name: 'Frota A', code: 'F0001', plates: ['AAA1A11', 'AAA1A12'] }], vehicles: ['BBB2B22'], vehicle_count: 3, monthly_cents: 15000, per_vehicle_cents: 5000 };

test('linha de cobertura: frota com placas, avulsos e valor por veículo', () => {
  const text = coverageLine(coverage).replace(/<[^>]+>/g, '');
  assert.match(text, /Frota A \(2\): AAA1A11, AAA1A12/);
  assert.match(text, /Veículos: BBB2B22/);
  assert.match(text, /3 veículos · R\$\s?50,00 por veículo/);
  assert.equal(coverageLine({ fleets: [], vehicles: [], vehicle_count: 0 }), '');
});

test('diálogo de pagamento mostra a cobertura da assinatura', () => {
  const html = renderPaymentDialog({ client: { id: 'c', legal_name: 'C' }, options: { subscriptions: [{ subscription_id: 's1', code: 'S0001', plans: ['Plano'], monthly_cents: 15000, next_due: '2026-10', coverage }] } });
  assert.match(html, /AAA1A11, AAA1A12/);
});

test('ficha mostra histórico de cobranças e pagamentos', () => {
  const html = renderSubscriptionDetail({ target: { kind: 'VEHICLE', plate: 'AAA1A11' }, items: [], history: [
    { subscription_code: 'S0001', competence: '2026-10', amount_cents: 15000, paid_cents: 15000, status: 'PAID', paid_on: '2026-10-03', share_cents: 5000 },
    { subscription_code: 'S0001', competence: '2026-11', amount_cents: 15000, paid_cents: 0, status: 'OPEN', paid_on: null, share_cents: 5000 }] });
  assert.match(html, /Histórico de cobranças/);
  assert.match(html, /10\/2026/);
  assert.match(html, /03\/10\/2026/);
  assert.match(html, /Em aberto/);
  assert.match(html, /R\$\s?50,00/);
});
