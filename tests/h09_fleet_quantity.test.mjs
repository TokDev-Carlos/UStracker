// H-09 (2.4.0): assinatura por frota — quantidade = total de veículos, prévia da conta e aviso de duplicidade.
import test from 'node:test';
import assert from 'node:assert/strict';
import { subscriptionPreview, renderSubscriptionWorkflow } from '../frontend/ui/subscription-workflow.js';

const model = {
  catalog: [{ id: 'p1', name: 'Plano 50', category: 'MENSAL', price_cents: 5000, active: 1 }],
  fleets: [{ id: 'f1', client_id: 'c1', name: 'Frota A' }],
  vehicles: [
    ...Array.from({ length: 10 }, (_, i) => ({ id: `fv${i}`, client_id: 'c1', fleet_id: 'f1', plate: `FRT0A${String(i).padStart(2, '0')}`, subscription_codes: i === 3 ? ['S0007'] : [] })),
    { id: 'a1', client_id: 'c1', fleet_id: null, plate: 'AVU1A11', subscription_codes: [] },
    { id: 'a2', client_id: 'c1', fleet_id: null, plate: 'AVU1A12', subscription_codes: ['S0002', 'S0005'] },
  ],
};

test('frota de 10 + 2 avulsos = 12 veículos, R$ 600,00/mês', () => {
  const p = subscriptionPreview(model, { catalogId: 'p1', vehicleIds: ['a1', 'a2'], fleetIds: ['f1'] });
  assert.equal(p.vehicles, 12);
  assert.equal(p.unitCents, 5000);
  assert.equal(p.totalCents, 60000);
  assert.match(p.text, /12 veículos × R\$\s?50,00 = R\$\s?600,00\/mês/);
});

test('veículo marcado direto e pela frota conta uma vez; quantidade manual muda o total', () => {
  const p = subscriptionPreview(model, { catalogId: 'p1', vehicleIds: ['fv0'], fleetIds: ['f1'], quantity: 3 });
  assert.equal(p.vehicles, 10);
  assert.equal(p.totalCents, 15000);
});

test('aviso de duplicidade lista placas já cobertas por outra assinatura ativa', () => {
  const p = subscriptionPreview(model, { catalogId: 'p1', vehicleIds: ['a2'], fleetIds: ['f1'] });
  assert.deepEqual(p.duplicates.map(d => d.plate), ['AVU1A12', 'FRT0A03']);
  assert.match(p.warning, /AVU1A12 \(S0002, S0005\)/);
  assert.equal(subscriptionPreview(model, { catalogId: 'p1', vehicleIds: ['a1'] }).warning, '');
});

test('formulário tem área de prévia', () => {
  assert.match(renderSubscriptionWorkflow({ ...model, clientId: 'c1', clients: [{ id: 'c1', legal_name: 'C' }] }), /data-subscription-preview/);
});
