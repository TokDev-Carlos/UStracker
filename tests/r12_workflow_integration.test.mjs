import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import { renderSubscriptionWorkflow } from '../frontend/ui/subscription-workflow.js';
import { renderCommercialPage } from '../frontend/pages/commercial.js';
import { renderFinancePage } from '../frontend/pages/finance.js';

const clients = Array.from({ length: 1005 }, (_, index) => ({
  id: `client-${index}`,
  legal_name: `Cliente ${index}`,
  archived: 0,
}));

function assertBoundedClientField(html) {
  assert.match(html, /data-entity-autocomplete/);
  assert.match(html, /type="hidden" name="client_id"/);
  assert.doesNotMatch(html, /<select name="client_id"/);
  assert.doesNotMatch(html, /Cliente 1000/);
}

test('assinatura comercial usa busca remota sem materializar clientes', () => {
  const html = renderSubscriptionWorkflow({ context: 'COMMERCIAL', clients, catalog: [] });
  assertBoundedClientField(html);
});

test('compra direta usa busca remota e preserva filtro de veículo por cliente', () => {
  const html = renderCommercialPage({
    clients,
    vehicles: [{ id: 'v1', client_id: 'client-1', plate: 'ABC1D23' }],
    catalog_avulsa: [], subscriptions: [], payments: [],
  }, 'purchases');
  assertBoundedClientField(html);
  assert.match(html, /data-client="client-1"/);
});

test('recebimento usa busca remota e preserva filtro de cobrança por cliente', () => {
  const html = renderFinancePage({
    clients,
    charges: [{ id: 'charge-1', client_id: 'client-2' }],
    payments: [], expenses: [], fiscal: [],
  });
  assertBoundedClientField(html);
  assert.match(html, /data-client="client-2"/);
});

test('aplicação consulta a rota limitada e vincula o autocomplete aos fluxos', async () => {
  const source = await readFile(new URL('../frontend/app.js', import.meta.url), 'utf8');
  assert.match(source, /bindEntityAutocomplete/);
  assert.match(source, /\/entities\/clients\?q=/);
  assert.match(source, /searchClients:\s*searchClientEntities/);
  assert.match(source, /#commercialPurchaseForm/);
  assert.match(source, /#financePaymentForm/);
});
