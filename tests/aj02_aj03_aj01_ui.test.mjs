import test from 'node:test';
import assert from 'node:assert/strict';
import { setIconSet } from '../frontend/ui/icon-registry.js';
import { renderOverviewPage } from '../frontend/pages/dashboard.js';
import { renderVehicleBreakdown } from '../frontend/ui/vehicle-breakdown.js';
import { renderClientProfile } from '../frontend/ui/r2-ui.js';

setIconSet({ name: 'teste', icons: {
  'vehicle.car': '/assets/icons/default/vehicles/car.svg', 'vehicle.truck': '/assets/icons/default/vehicles/truck.svg',
  'vehicle.boat': '/assets/icons/default/vehicles/boat.svg', 'vehicle.aircraft': '/assets/icons/default/vehicles/aircraft.svg',
  'vehicle.other': '/assets/icons/default/vehicles/other.svg',
} });

test('AJ-02: total geral e cinco categorias com ícone, nome e quantidade', () => {
  const html = renderVehicleBreakdown({ categories: [{ key: 'CAR', count: 2 }, { key: 'TRUCK', count: 1 }, { key: 'OTHER', count: 1, custom_types: ['Trator'] }] });
  assert.match(html, /<strong>4<\/strong><span class="muted">Total Geral/);
  const labels = [...html.matchAll(/vehicle-breakdown-label">([^<]+)/g)].map(m => m[1]);
  assert.deepEqual(labels, ['Carros', 'Caminhões', 'Embarcações', 'Aeronaves', 'Outros']);
  assert.equal((html.match(/vehicles\/[a-z]+\.svg/g) || []).length, 5);
  assert.match(html, /title="Tipos: Trator"/);
});

test('AJ-01: Receita Geral e Previsão do Mês lado a lado; previsão fora do Resultado', () => {
  const html = renderOverviewPage({
    period: { label: 'Geral', revenue_cents: 10000, expenses_cents: 4000, result_cents: 6000 },
    month_forecast: { competence: '2026-10', forecast_cents: 25000, received_in_month_cents: 10000 },
    vehicle_breakdown: { categories: [] },
    client_activity: [{ client_id: 'x', client_code: 'CLI-0001', client_name: 'Alfa', vehicles_count: 1, active_subscriptions: 1, purchases_count: 0, contracted_active_cents: 10000, realized_revenue_cents: 0, status: 'ACTIVE' }],
  });
  assert.match(html, /revenue-split[\s\S]*Receita Geral[\s\S]*Previsão do Mês out\/2026[\s\S]*fora do Resultado/);
  assert.match(html, /R\$ 60,00<\/div><div class="label">Resultado/);
  assert.match(html, /Valor contratado ativo<\/th><th>Receita realizada/);
  assert.match(html, /R\$ 100,00<\/td><td class="money">R\$ 0,00/);
});

test('AJ-03: ficha mostra jornada Cliente → Mobilidade → Plano e atalhos para o Comercial', () => {
  const html = renderClientProfile({
    client: { legal_name: 'Alfa', code: 'CLI-0001' }, companies: [{ id: 'co', legal_name: 'Empresa', is_primary: 1 }],
    vehicles: [{ id: 'v', code: 'CLI-0001-V01', type: 'Lancha', category: 'BOAT', category_label: 'Embarcação', brand: 'X', model: 'Y', plate: 'B1' }],
    subscriptions: [{ id: 's', code: 'CLI-0001-A01', items: [{ plan_name: 'Plano' }] }],
    direct_sales: [{ id: 'd', code: 'CLI-0001-C01', status: 'OPEN', total_cents: 5000, direct_sale_items: [{ description: 'Instalação' }] }],
    summary: { vehicle_breakdown: { categories: [{ key: 'BOAT', count: 1 }] }, contracted_active_cents: 10000, realized_revenue_cents: 0 },
  });
  assert.match(html, /client-journey[\s\S]*1 · Cliente[\s\S]*2 · Mobilidade[\s\S]*3 · Plano ou compra/);
  assert.match(html, /id="clientVehicleForm"/);
  assert.match(html, /id="clientFleetForm"/);
  assert.match(html, /id="clientPurchaseForm"/);
  assert.match(html, /data-open-commercial="subscriptions" data-code="CLI-0001-A01"/);
  assert.match(html, /data-open-commercial="purchases" data-code="CLI-0001-C01"/);
  assert.match(html, /Embarcações <span class="muted">\(1\)/);
  assert.match(html, /Valor contratado ativo<\/dt><dd>R\$ 100,00/);
});
