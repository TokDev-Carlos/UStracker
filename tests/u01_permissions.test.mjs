import test from 'node:test';
import assert from 'node:assert/strict';
import { allowedPages, can, filterMenu, setAccess } from '../frontend/ui/permissions.js';
import { renderPermissionGrid, renderUsersTab } from '../frontend/pages/users.js';

test('U-05: menus e ações seguem o pacote', () => {
  setAccess({ kind: 'user', permissions: ['clients.view', 'clients.edit', 'commercial.view', 'commercial.edit', 'finance.pay'] });
  assert.deepEqual(allowedPages(['dashboard', 'clients', 'commercial', 'system']), ['clients', 'commercial']);
  assert.equal(can('clients.delete'), false);
  const menu = filterMenu([{ key: 'pay' }, { key: 'cancel' }, { key: 'profile' }]);
  assert.deepEqual(menu.map(i => !!i.hidden), [false, true, false]);
  setAccess({ kind: 'admin' });
  assert.equal(can('system'), true);
});

test('U-02: tela de usuários e grade de permissões', () => {
  const html = renderUsersTab({ items: [{ id: 1, name: 'ana', package_id: 'OPERADOR', package_title: 'Operador', active: true }], packages: [{ id: 'OPERADOR', title: 'Operador', builtin: true, permissions: ['a'] }] });
  assert.match(html, /ana/); assert.match(html, /Padrão/); assert.match(html, /data-user-new/);
  const grid = renderPermissionGrid([{ key: 'clients.view', group: 'Clientes', label: 'Ver' }], ['clients.view']);
  assert.match(grid, /<legend>Clientes<\/legend>/); assert.match(grid, /value="clients.view" checked/);
});
