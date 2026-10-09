// H-20 (2.7.0) — frota: uma assinatura por veículo; pagar a frota toda num recibo.
import test from 'node:test';
import assert from 'node:assert/strict';
import { subscriptionPreview } from '../frontend/ui/subscription-workflow.js';
import { renderPaymentDialog, paymentBody } from '../frontend/ui/payment-dialog.js';

const model = {
  catalog: [{ id: 'p', price_cents: 5000, category: 'Mensal', active: 1 }],
  vehicles: [1, 2, 3, 4].map(i => ({ id: 'v' + i, plate: 'FRT1A0' + i, fleet_id: 'f1', archived: 0 })),
};

test('prévia: 4 veículos da frota = 4 assinaturas individuais', () => {
  const p = subscriptionPreview(model, { catalogId: 'p', fleetIds: ['f1'] });
  assert.equal(p.quantity, 4);
  assert.match(p.text, /4 assinaturas \(uma por veículo\)/);
  assert.match(p.text, /4 veículos × R\$\s?50,00 = R\$\s?200,00\/mês/);
});

const options = {
  today: '2026-10-09',
  subscriptions: [1, 2, 3, 4].map(i => ({ subscription_id: 's' + i, code: 'A0' + i, monthly_cents: 5000, next_due: '2026-10', coverage: { vehicle_count: 1, vehicles: ['FRT1A0' + i], fleets: [] } })),
  fleets: [{ fleet_id: 'f1', name: 'Frota Azul', vehicle_count: 4, monthly_cents: 20000, next_due: '2026-10', plates: ['FRT1A01', 'FRT1A02', 'FRT1A03', 'FRT1A04'] }],
};

test('diálogo de pagamento oferece pagar a frota toda primeiro', () => {
  const html = renderPaymentDialog({ client: { id: 'c', legal_name: 'Transportes' }, options });
  assert.match(html, /value="fleet:f1" checked/);
  assert.match(html, /Frota Azul — pagar todos \(4 veículos\)/);
  assert.match(html, /value="s1"/);
});

test('corpo do envio: frota vai para fleet-payments, assinatura para payments', () => {
  assert.deepEqual(paymentBody('fleet:f1', { months: 2 }), { path: '/billing/fleet-payments', body: { fleet_id: 'f1', months: 2 } });
  assert.deepEqual(paymentBody('s1', { months: 1 }), { path: '/billing/payments', body: { subscription_id: 's1', months: 1 } });
});
