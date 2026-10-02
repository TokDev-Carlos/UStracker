import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { renderMobilityPage, renderTransferCaseForm } from '../frontend/pages/mobility.js';

const clients = Array.from({ length: 1005 }, (_, index) => ({ id: `c${index}`, legal_name: `Cliente ${index}` }));
const fleets = Array.from({ length: 1005 }, (_, index) => ({ id: `f${index}`, client_id: `c${index}`, name: `Frota ${index}` }));

test('filtro, novo veículo e nova frota usam cliente incremental', () => {
  const html = renderMobilityPage({ particulars: [], fleets: [] }, { clients, fleets, filters: {} });
  assert.equal((html.match(/data-entity-autocomplete/g) || []).length, 3);
  assert.doesNotMatch(html, /<select name="client_id"/);
  assert.doesNotMatch(html, /Cliente 1000|Frota 1000/);
  assert.match(html, /id="mobilityFilter"/);
  assert.match(html, /id="vehicleForm"/);
  assert.match(html, /id="fleetForm"/);
});

test('transferência usa cliente incremental e frota dependente vazia', () => {
  const html = renderTransferCaseForm({ revision: 3 }, { clients, fleets, cases: [] });
  assert.match(html, /data-entity-autocomplete/);
  assert.match(html, /type="hidden" name="client_id"/);
  assert.doesNotMatch(html, /<select name="client_id"|Cliente 1000|Frota 1000/);
  assert.match(html, /name="fleet_id"[^>]*disabled/);
});

test('fluxo de mobilidade não carrega listas globais e busca dependências por cliente', async () => {
  const source = await readFile(new URL('../frontend/app.js', import.meta.url), 'utf8');
  const start = source.indexOf('async function mobilityPage');
  const end = source.indexOf('async function catalogPage', start);
  const mobility = source.slice(start, end);
  assert.doesNotMatch(mobility, /api\('\/clients'\)/);
  assert.match(mobility, /bindEntityAutocomplete/);
  assert.match(mobility, /\/fleets\?client_id=/);
  assert.match(mobility, /\/clients\/.*\/companies/);
});
