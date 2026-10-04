import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { runDomAction } from '../frontend/ui/action-state.js';

const app = fs.readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');

test('R19: Administração é a aba inicial e diagnósticos ficam em Desenvolvimento', () => {
  assert.match(app, /class="active" data-system-tab="admin">Administração/);
  for (const title of ['Recuperação / transferência', 'Integrações planejadas', 'Laboratório de testes', 'Estações', 'Auditoria']) {
    assert.match(app.match(/const advanced=new Set\(\[(.*?)\]\)/)[1], new RegExp(title));
  }
});

test('R19: ações destrutivas pedem confirmação explícita', async () => {
  for (const key of ['sandbox-reset', 'admin-reset']) assert.match(app, new RegExp(`key:'${key}',confirm:'`));
  assert.match(app, /confirmDialog\('Restaurar este backup/);
  let called = false;
  const result = await runDomAction({ key: 'x', confirm: 'Apagar?', confirmFn: () => false, action: () => { called = true; } });
  assert.equal(called, false);
  assert.equal(result.cancelled, true);
});
