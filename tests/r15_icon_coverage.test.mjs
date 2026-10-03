import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const root = new URL('../frontend/', import.meta.url);
const app = fs.readFileSync(new URL('app.js', root), 'utf8');
const iconSet = JSON.parse(fs.readFileSync(new URL('icons/icon-set.json', root), 'utf8'));
const sources = ['app.js', ...fs.readdirSync(new URL('ui/', root)).map(f => 'ui/' + f), ...fs.readdirSync(new URL('pages/', root)).map(f => 'pages/' + f)]
  .filter(f => f.endsWith('.js')).map(f => fs.readFileSync(new URL(f, root), 'utf8')).join('\n');

test('R15: todo menu principal tem ícone registrado e o arquivo existe', () => {
  const nav = [...app.match(/const nav=\[(.*?)\];/)[1].matchAll(/\['([a-z]+)'/g)].map(m => m[1]);
  assert.ok(nav.length >= 9);
  for (const key of nav) {
    const path = iconSet.icons[`nav.${key}`];
    assert.ok(path, `nav.${key} sem ícone`);
    assert.ok(fs.existsSync(new URL('..' + path.replace('/assets', '/frontend'), root)), `${path} inexistente`);
  }
});

test('R15: todos os slots usados no código existem no registro', () => {
  const used = new Set([...sources.matchAll(/iconImg\(['`]((?:action|brand|vehicle)\.[a-z]+)['`]/g)].map(m => m[1]));
  for (const [, slot] of sources.matchAll(/icon: '([a-z]+\.[a-z]+)'/g)) used.add(slot);
  for (const slot of used) assert.ok(iconSet.icons[slot], `slot ${slot} sem asset`);
  for (const path of Object.values(iconSet.icons)) assert.ok(fs.existsSync(new URL('..' + path.replace('/assets', '/frontend'), root)), `${path} inexistente`);
});

test('R15: nenhum emoji como ícone de produção', () => {
  assert.doesNotMatch(sources, /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u);
});
