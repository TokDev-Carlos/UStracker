import test from 'node:test';
import assert from 'node:assert/strict';
import { vehicleCategory, vehicleCell, vehicleRef } from '../frontend/ui/logical-codes.js';
import { renderCommercialPage } from '../frontend/pages/commercial.js';
import { renderMobilityPage } from '../frontend/pages/mobility.js';
import { renderFilesPage } from '../frontend/pages/files.js';

const UUID = '3f2b6c1e-8a4d-4c2e-9b7f-0d1e2f3a4b5c';
const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
const visibleText = html => html.replace(/<[^>]*>/g, ' ');
const vehicle = { id: UUID, code: 'CLI-0001-V02', type: 'Caminhão', brand: 'Volvo', model: 'FH', plate: 'ABC1D23', client_id: UUID };

test('categoria do veículo é o valor principal e o código fica secundário', () => {
  assert.equal(vehicleCategory('caminhao'), 'Caminhão');
  assert.equal(vehicleCategory('Trator'), 'Outro');
  const cell = vehicleCell(vehicle);
  assert.match(cell, /<strong>Caminhão<\/strong><span class="ui-code">CLI-0001-V02<\/span>/);
  assert.match(cell, /title="CLI-0001-V02 · Volvo FH · ABC1D23"/);
  assert.equal(vehicleRef(vehicle), 'CLI-0001-V02 · Volvo FH · ABC1D23');
});

test('tabelas operacionais não exibem UUID técnico', () => {
  const commercial = renderCommercialPage({
    subscriptions: [{ id: UUID, code: 'CLI-0001-A01', client_id: UUID, client_name: 'Alfa', vehicles: [vehicle], plans: [], total_cents: 100, lifecycle_status: 'ACTIVE' }],
    direct_sales: [{ id: UUID, code: 'CLI-0001-C01', client_name: 'Alfa', sold_on: '2026-10-01', status: 'OPEN', total_cents: 100 }],
    credits: [{ id: UUID, client_id: UUID, client_name: 'Alfa', client_code: 'CLI-0001', amount_cents: 1, balance_cents: 1, status: 'OPEN' }],
    vehicles: [vehicle], payments: [{ id: UUID, code: 'CLI-0001-R01' }],
  });
  const mobility = renderMobilityPage({ particulars: [{ ...vehicle, client_name: 'Alfa', client_code: 'CLI-0001' }], fleets: [] });
  const files = renderFilesPage({ media: [{ id: UUID, entity_type: 'vehicle', entity_id: UUID, entity_code: 'CLI-0001-V02', mime: 'image/png' }] });
  for (const html of [commercial, mobility, files]) {
    assert.deepEqual(visibleText(html).match(UUID_RE), null);
    assert.match(html, /CLI-0001/);
  }
});
