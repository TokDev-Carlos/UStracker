import test from 'node:test';
import assert from 'node:assert/strict';
import { datasetConfig } from '../frontend/ui/datasets.js';
import { helpFor } from '../frontend/ui/help-catalog.js';
import { setIconSet } from '../frontend/ui/icon-registry.js';

test('Compras Diretas usa o endpoint de vendas e tem ajuda contextual', () => {
  assert.equal(datasetConfig('purchases').endpoint, '/direct-sales');
  assert.match(helpFor('purchases').body, /compra/i);
});

test('Assinaturas expõem a periodicidade diária, mensal ou anual no dataset', () => {
  assert.ok(datasetConfig('subscriptions').columns.includes('billing_cycle'));
  assert.match(helpFor('subscriptions', 'billing_cycle').body, /diária|mensal|anual/i);
});

test('O seletor de assinatura apresenta os três ciclos em pt-BR', async () => {
  const { renderBillingCycleSelect } = await import('../frontend/ui/r2-ui.js');
  const html = renderBillingCycleSelect();
  assert.match(html, /name="billing_cycle"/);
  assert.match(html, /value="DAILY"[^>]*>Diário/);
  assert.match(html, /value="MONTHLY"[^>]*selected[^>]*>Mensal/);
  assert.match(html, /value="ANNUAL"[^>]*>Anual/);
});

test('A compra direta oferece cliente, itens, veículo opcional e pagamento', async () => {
  const { renderPurchasesForm } = await import('../frontend/ui/r2-ui.js');
  const html = renderPurchasesForm({
    clients: [{ id: 'c1', legal_name: '<Cliente>' }],
    catalog: [{ id: 'i1', name: 'Plano', price_cents: 5000 }],
    vehicles: [{ id: 'v1', plate: 'ABC1234' }],
  });
  assert.match(html, /name="client_id"/);
  assert.match(html, /id="purchaseCatalog"/);
  assert.match(html, /id="purchaseVehicle"/);
  assert.match(html, /name="quantity"/);
  assert.match(html, /name="unit_price"/);
  assert.match(html, /name="status"/);
  assert.match(html, /name="paid_on"/);
  assert.match(html, /&lt;Cliente&gt;/);
  assert.doesNotMatch(html, /<Cliente>/);
});

test('O Dashboard mostra exatamente oito indicadores principais na ordem definida', async () => {
  const { renderDashboardCards } = await import('../frontend/ui/r2-ui.js');
  const html = renderDashboardCards({
    clients_count: 2, products_count: 3, vehicles_count: 4,
    active_subscription_products: 5, accumulated_profit_cents: 10000,
    monthly_value_cents: 9000, monthly_spent_cents: 12000,
    real_profit_cents: -3000,
  });
  const labels = [...html.matchAll(/class="r2-kpi-label">([^<]+)/g)].map(match => match[1]);
  assert.deepEqual(labels, [
    'Quantidade de Clientes', 'Quantidade de Produtos', 'Quantidade de Veículos',
    'Assinaturas Ativas', 'Valor Acumulado', 'Valor Mensal', 'Valor Gasto', 'Lucro Real',
  ]);
  assert.match(html, /-R\$\s?30,00/);
});

test('Mensalidade apresenta somente os ciclos existentes sem conversão inventada', async () => {
  const { formatSubscriptionRates } = await import('../frontend/ui/r2-ui.js');
  assert.equal(formatSubscriptionRates({
    subscription_daily_cents: 1500,
    subscription_monthly_cents: 12000,
    subscription_annual_cents: 120000,
  }), 'R$ 15,00/dia · R$ 120,00/mês · R$ 1.200,00/ano');
  assert.equal(formatSubscriptionRates({}), '—');
});

test('A ficha do cliente mostra oito cards recolhíveis e reutiliza miniaturas', async () => {
  const { renderClientProfile } = await import('../frontend/ui/r2-ui.js');
  const html = renderClientProfile({
    client: { legal_name: '<Empresa>', trade_name: 'Marca', document: '123' },
    client_media: [{ id: 'm1' }], fleets: [{ name: 'Frota A' }],
    vehicles: [{ id: 'v1', plate: 'ABC1234' }],
    vehicle_media: { v1: [{ id: 'm2' }] },
    subscriptions: [{ billing_cycle: 'MONTHLY', subscription_items: [{ description: 'Plano', quantity: 1 }] }],
    direct_sales: [{ status: 'PAID', total_cents: 5000, direct_sale_items: [{ description: 'Item', quantity: 1 }] }],
    financial: { subscription_received_cents: 2000, direct_sales_paid_cents: 5000, client_expenses_paid_cents: 1000 },
  });
  const titles = [...html.matchAll(/<summary>([^<]+)/g)].map(match => match[1]);
  assert.deepEqual(titles, ['Cliente', 'Empresa / Identificação', 'Foto do Cliente', 'Frotas',
    'Veículos', 'Assinaturas', 'Compras Diretas', 'Resumo Financeiro']);
  assert.match(html, /\/api\/v1\/media\/m1\/thumb/);
  assert.match(html, /\/api\/v1\/media\/m2\/thumb/);
  assert.match(html, /&lt;Empresa&gt;/);
  assert.doesNotMatch(html, /<Empresa>/);
});

test('O Login tem logo, duas áreas e REAL selecionado em cada abertura', async () => {
  const { renderLoginScreen } = await import('../frontend/ui/r2-ui.js');
  setIconSet({ name: 'teste', icons: { 'brand.logo': '/assets/icons/default/brand/logo.png' } });
  const html = renderLoginScreen({ complete: true }, {
    brand: { assets: { logo: '/public-assets/logo.png' }, company_display_name: 'Empresa' },
    catalog: [{ name: '<Plano>', category: 'Serviço', price_cents: 5000 }],
  });
  assert.match(html, /class="r2-login-grid"/);
  assert.match(html, /src="\/public-assets\/logo.png"/);
  assert.match(html, /name="environment" value="production" checked/);
  assert.match(html, /name="environment" value="test"/);
  assert.match(html, /&lt;Plano&gt;/);
  assert.doesNotMatch(html, /<Plano>/);
  const fallback = renderLoginScreen({ complete: false }, { brand: {}, catalog: [] });
  assert.match(fallback, /src="\/assets\/icons\/default\/brand\/logo.png"/);
  assert.match(fallback, /name="environment" value="production" checked/);
});
