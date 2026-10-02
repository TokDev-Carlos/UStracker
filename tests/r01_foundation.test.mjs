import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import {
  formatBRL,
  parseBRLInput,
  formatDateBR,
  normalizePlate,
  normalizeDocument,
} from '../frontend/ui/formatters.js';
import { renderMoneyInput, bindMoneyInput } from '../frontend/ui/money-input.js';
import { renderAppShellMarkup } from '../frontend/ui/shell.js';

test('formatBRL preserva centavos inteiros e formato pt-BR', () => {
  assert.equal(formatBRL(0), 'R$ 0,00');
  assert.equal(formatBRL(123456), 'R$ 1.234,56');
  assert.equal(formatBRL(-123456), '-R$ 1.234,56');
});

test('parseBRLInput converte texto brasileiro para centavos sem arredondar', () => {
  assert.equal(parseBRLInput('R$ 0,00'), 0);
  assert.equal(parseBRLInput('1.234,56'), 123456);
  assert.equal(parseBRLInput('-R$ 12,34'), -1234);
  assert.equal(parseBRLInput('1234'), 123400);
  assert.throws(() => parseBRLInput('1,234'), /duas casas|inválido/i);
});

test('formatDateBR exibe data e data-hora sem depender do timezone do navegador', () => {
  assert.equal(formatDateBR('2026-09-28', false), '28/09/2026');
  assert.equal(formatDateBR('2026-09-28T23:36:37Z', true), '28/09/2026 - 23:36:37');
  assert.equal(formatDateBR('', true), '—');
});

test('normalizadores retornam representações canônicas sem inventar dados', () => {
  assert.equal(normalizePlate('abc-1d23'), 'ABC1D23');
  assert.equal(normalizeDocument('CPF', '123.456.789-09'), '12345678909');
  assert.equal(normalizeDocument('CNH', ' 123 456 789 01 '), '12345678901');
  assert.equal(normalizeDocument('RG', '12.345.678-x'), '12345678X');
});

test('campo monetário é textual, decimal e não altera cursor durante digitação', () => {
  const html = renderMoneyInput({ name: 'amount', label: 'Valor', valueCents: 123456 });
  assert.match(html, /type="text"/);
  assert.match(html, /inputmode="decimal"/);
  assert.doesNotMatch(html, /type="number"/);
  assert.match(html, /value="R\$ 1\.234,56"/);

  const handlers = new Map();
  const input = {
    value: '1234,56',
    addEventListener(type, handler) { handlers.set(type, handler); },
  };
  bindMoneyInput(input);
  assert.equal(handlers.has('input'), false, 'não deve reformatar a cada tecla');
  assert.equal(handlers.has('blur'), true);
  handlers.get('blur')();
  assert.equal(input.value, 'R$ 1.234,56');
});

test('shell coloca marca e ações no cabeçalho fixo e remove PRODUÇÃO · ESCRITORA', () => {
  const html = renderAppShellMarkup({
    me: { name: 'Carlos', slot: 1, environment: 'production', station: { is_writer: 1 } },
    nav: [['dashboard', 'Visão geral'], ['system', 'Sistema']],
  });
  assert.match(html, /class="topbar shell-topbar"/);
  assert.match(html, /UStracker/);
  assert.match(html, />Carlos<\/button>/);
  assert.doesNotMatch(html, /Carlos · Administrador/);
  assert.match(html, /id="globalHelp"/);
  assert.match(html, /id="globalLogout"/);
  assert.match(html, /id="globalShutdown"/);
  assert.match(html, /id="globalSearch"/);
  assert.doesNotMatch(html, /PRODUÇÃO · ESCRITORA/);
  assert.doesNotMatch(html, /PRODUÇÃO · SOMENTE LEITURA/);
});

test('favicon padrão existe no HTML antes de branding personalizado', () => {
  const html = fs.readFileSync(new URL('../frontend/index.html', import.meta.url), 'utf8');
  assert.match(html, /id="dynamicFavicon"[^>]+href="\/assets\/icons\/default\/brand\/favicon\.png"/);
});

test('componentes existentes usam o formatador global de moeda', async () => {
  const { renderDashboardCards, formatSubscriptionRates } = await import('../frontend/ui/r2-ui.js');
  const html = renderDashboardCards({ accumulated_profit_cents: 123456 });
  assert.match(html, /R\$ 1\.234,56/);
  assert.equal(formatSubscriptionRates({ subscription_monthly_cents: 123456 }), 'R$ 1.234,56/mês');
});

test('CSS mantém cabeçalho superior sticky e menu lateral rolável abaixo dele', () => {
  const css = fs.readFileSync(new URL('../frontend/styles.css', import.meta.url), 'utf8');
  assert.match(css, /\.shell-topbar\s*\{[^}]*position:sticky[^}]*top:0/s);
  assert.match(css, /\.sidebar\s*\{[^}]*overflow:auto/s);
  assert.match(css, /height:calc\(100vh\s*-\s*var\(--shell-header-height\)\)/);
});

test('R01 preserva navegação responsiva em telas estreitas', () => {
  const css = fs.readFileSync(new URL('../frontend/styles.css', import.meta.url), 'utf8');
  const r01 = css.slice(css.indexOf('/* R01 — shell estável'));
  assert.match(r01, /@media\(max-width:800px\)\{[^}]*\.shell\{grid-template-columns:1fr;grid-template-rows:auto auto minmax\(0,1fr\)\}/s);
  assert.match(r01, /@media\(max-width:800px\)[\s\S]*\.sidebar\{[^}]*position:static[^}]*height:auto/s);
});

test('app usa helpers globais para moeda e liga inputs monetários', () => {
  const source = fs.readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');
  assert.match(source, /import \{ formatBRL, formatDateBR \} from '\.\/ui\/formatters\.js'/);
  assert.match(source, /bindMoneyInputs/);
  assert.doesNotMatch(source, /const money=c=>/);
  assert.match(source, /data-money-input/);
});
