import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isZeroMoney, clearZeroOnFocus } from '../frontend/ui/money-input.js';

test('2.4.0: R$ 0,00 é só dica — some ao focar', () => {
  for (const v of ['R$ 0,00', '0,00', 'R$ 0', '0', ' R$  0,0 ']) assert.equal(isZeroMoney(v), true, v);
  for (const v of ['R$ 10,00', '0,50', 'R$ 0,01', '']) assert.equal(isZeroMoney(v) && v !== '', false, v);
  const el = { tagName: 'INPUT', value: 'R$ 0,00', placeholder: '', readOnly: false, disabled: false, hasAttribute: n => n === 'data-money-input', getAttribute: () => null };
  clearZeroOnFocus({ target: el });
  assert.equal(el.value, ''); assert.equal(el.placeholder, 'R$ 0,00');
  const keep = { ...el, value: 'R$ 12,00' }; clearZeroOnFocus({ target: keep }); assert.equal(keep.value, 'R$ 12,00');
});

test('2.4.0: nenhum formulário vem com R$ 0,00 escrito', () => {
  for (const f of ['frontend/pages/finance.js', 'frontend/pages/commercial.js', 'frontend/pages/catalog.js', 'frontend/app.js']) {
    assert.doesNotMatch(readFileSync(f, 'utf8'), /value="R\$ 0,00"/, f);
  }
});
