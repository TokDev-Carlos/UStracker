// H-19 (2.6) — LGPD: botão "Exportar dados" na ficha do cliente, só para administradores.
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderClientProfile } from '../frontend/ui/client-profile.js';
import { ELEMENT_PERMISSION } from '../frontend/ui/permissions.js';

test('ficha do cliente tem Exportar dados e a regra é só administração', () => {
  const html = renderClientProfile({ client: { id: 'c1', legal_name: 'Ana' } });
  assert.match(html, /data-cp-export="c1"/);
  const rule = ELEMENT_PERMISSION.find(([sel]) => sel.includes('[data-cp-export]'));
  assert.deepEqual(rule?.[1], ['system']);
});
