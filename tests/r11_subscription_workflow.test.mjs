import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import {
  bindSubscriptionWorkflow,
  buildSubscriptionPayload,
  renderSubscriptionWorkflow,
  searchSubscriptionClients,
  subscriptionOptionsForClient,
} from '../frontend/ui/subscription-workflow.js';


const model = {
  clients: [
    { id: 'c1', legal_name: 'Cliente <Um>', archived: 0, status: 'ACTIVE' },
    { id: 'c2', legal_name: 'Cliente Dois', archived: 0, status: 'ACTIVE' },
  ],
  catalog: [
    { id: 'p1', name: 'Plano Mensal', category: 'MENSAL', active: 1, price_cents: 12500 },
    { id: 'p2', name: 'Plano Inativo', category: 'MENSAL', active: 0, price_cents: 5000 },
    { id: 'a1', name: 'Produto Avulso', category: 'AVULSA', active: 1, price_cents: 3000 },
  ],
  vehicles: [
    { id: 'v1', client_id: 'c1', plate: 'AAA1A11', archived: 0 },
    { id: 'v2', client_id: 'c2', plate: 'BBB2B22', archived: 0 },
  ],
  fleets: [
    { id: 'f1', client_id: 'c1', name: 'Frota Um', archived: 0 },
    { id: 'f2', client_id: 'c2', name: 'Frota Dois', archived: 0 },
  ],
};

test('Ficha do Cliente bloqueia o cliente e filtra planos e alvos', () => {
  const html = renderSubscriptionWorkflow({ ...model, context: 'CLIENT_PROFILE', clientId: 'c1' });
  assert.match(html, /name="client_display"[^>]*disabled/);
  assert.match(html, /type="hidden" name="client_id" value="c1"/);
  assert.match(html, /Plano Mensal/);
  assert.doesNotMatch(html, /Plano Inativo|Produto Avulso/);
  assert.match(html, /AAA1A11/);
  assert.match(html, /Frota Um/);
  assert.doesNotMatch(html, /BBB2B22|Frota Dois/);
  assert.match(html, /Cliente &lt;Um&gt;/);
  assert.doesNotMatch(html, /Cliente <Um>/);
});

test('Comercial exige seleção de cliente antes de mostrar mobilidade', () => {
  const initial = renderSubscriptionWorkflow({ ...model, context: 'COMMERCIAL' });
  assert.match(initial, /data-subscription-client-search/);
  assert.match(initial, /name="client_id"/);
  assert.match(initial, /Selecione o cliente/);
  assert.doesNotMatch(initial, /AAA1A11|BBB2B22|Frota Um|Frota Dois/);

  const selected = renderSubscriptionWorkflow({ ...model, context: 'COMMERCIAL', selectedClientId: 'c2' });
  assert.match(selected, /BBB2B22/);
  assert.match(selected, /Frota Dois/);
  assert.doesNotMatch(selected, /AAA1A11|Frota Um/);
  assert.deepEqual(subscriptionOptionsForClient(model, 'c1').vehicles.map(row => row.id), ['v1']);
  assert.deepEqual(searchSubscriptionClients(model.clients, 'dois').map(row => row.id), ['c2']);
});

test('Os dois contextos produzem o mesmo payload e rejeitam duplicidades', () => {
  const flat = { client_id: 'c1', catalog_id: 'p1', start_on: '2026-10-02', due_day: '10', quantity: '2' };
  const selections = { targetVehicleIds: ['v1'], targetFleetIds: ['f1'] };
  const fromProfile = buildSubscriptionPayload(flat, selections, { context: 'CLIENT_PROFILE' });
  const fromCommercial = buildSubscriptionPayload(flat, selections, { context: 'COMMERCIAL' });
  assert.deepEqual(fromProfile, fromCommercial);
  assert.deepEqual(fromProfile, {
    client_id: 'c1', start_on: '2026-10-02', due_day: 10, billing_cycle: 'MONTHLY',
    items: [{ catalog_id: 'p1', quantity: 2 }],
    target_vehicle_ids: ['v1'], target_fleet_ids: ['f1'],
  });
  assert.throws(() => buildSubscriptionPayload(flat, { targetVehicleIds: ['v1', 'v1'] }), /duplicado/i);
  assert.throws(() => buildSubscriptionPayload(flat, { targetFleetIds: ['f1', 'f1'] }), /duplicado/i);
  assert.equal(typeof bindSubscriptionWorkflow, 'function');
});

test('Ficha e Comercial acionam o mesmo workflow e a mesma rota', () => {
  const app = fs.readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');
  const profile = fs.readFileSync(new URL('../frontend/ui/r2-ui.js', import.meta.url), 'utf8');
  const commercial = fs.readFileSync(new URL('../frontend/pages/commercial.js', import.meta.url), 'utf8');
  const help = fs.readFileSync(new URL('../frontend/ui/help-catalog.js', import.meta.url), 'utf8');
  assert.match(app, /renderSubscriptionWorkflow/);
  assert.match(app, /bindSubscriptionWorkflow/);
  assert.match(app, /api\('\/subscriptions'/);
  assert.doesNotMatch(app, /id="subForm"/);
  assert.match(profile, /data-client-new-subscription/);
  assert.match(commercial, /data-new-subscription/);
  assert.match(help, /alvos|veículo|frota/i);
});

test('Mobilidade e ficha exibem assinaturas como contagem e o detalhe vem do servidor (AJ-06)', async () => {
  const { renderFleetProfile, renderMobilityPage } = await import('../frontend/pages/mobility.js');
  const { renderSubscriptionDetail, subscriptionCountCell } = await import('../frontend/ui/subscription-popover.js');
  const subscription = {
    id: 's1', code: 'CLI-0001-A01', client_name: 'Cliente Um', company_name: 'Empresa Um', plan_names: 'Plano Mensal',
    effective_total_cents: 12500, monthly_cents: 12500, start_on: '2026-10-01', lifecycle_status: 'ACTIVE', due_day: 10,
    target_scope: 'FLEET', plans: [{ name: 'Plano Mensal', quantity: 1, unit_price_cents: 12500, total_cents: 12500 }],
  };
  const page = renderMobilityPage({ particulars: [], fleets: [{
    id: 'f1', client_name: 'Cliente Um', company_name: 'Empresa Um', name: 'Frota Um', subscriptions_count: 1, vehicle_group: 'TRUCK', vehicle_group_label: 'Caminhões',
  }] });
  const fleet = renderFleetProfile({
    fleet: { id: 'f1', name: 'Frota Um' }, company: { legal_name: 'Empresa Um' }, subscriptions: [subscription],
    vehicles: [{ id: 'v1', plate: 'AAA1A11', subscriptions_count: 1 }], summary: {},
  });
  assert.match(page, /data-subs-fleet="f1"[^>]*>1<\/button>/);
  assert.match(fleet, /data-subs-vehicle="v1"[^>]*>1<\/button>/);
  assert.match(page, /Cliente Um/);
  assert.match(page, /Empresa Um/);
  assert.doesNotMatch(page, /Plano Mensal/);
  assert.match(subscriptionCountCell(0, { vehicleId: 'v9' }), /subs-count-zero/);
  const detail = renderSubscriptionDetail({ target: { kind: 'FLEET', name: 'Frota Um', vehicle_group_label: 'Caminhões', client_name: 'Cliente Um' }, items: [subscription], active_monthly_cents: 12500 });
  assert.match(detail, /Plano Mensal/);
  assert.match(detail, /R\$ 125,00/);
  assert.match(detail, /01\/10\/2026/);
  assert.match(detail, /data-open-commercial="subscriptions" data-code="CLI-0001-A01"/);
});
