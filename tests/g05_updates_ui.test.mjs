// G-05 — aviso de versão: normal (faixa + "Atualizar agora" para quem pode) e crítica (tela bloqueada).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');

test('Checa /update/status e mostra faixa ou bloqueio', () => {
  assert.match(app, /'\/update\/status'/);
  assert.match(app, /update-banner/);
  assert.match(app, /Atualização obrigatória/);
  assert.match(app, /será instalada quando o sistema for fechado/);
  assert.match(app, /'\/update\/apply-now'/);
  assert.match(app, /waitNewVersion/);
});
