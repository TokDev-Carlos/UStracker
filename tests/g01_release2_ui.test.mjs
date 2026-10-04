// G-01 — Release 2: sem "restaurar da nuvem" nas telas de entrada; só em Sistema › Nuvem (Administrador).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');

test('Login não oferece restaurar da nuvem e pede Usuário', async () => {
  const { renderLoginScreen } = await import('../frontend/ui/r2-ui.js');
  const html = renderLoginScreen({ complete: true }, { brand: {}, catalog: [] });
  assert.doesNotMatch(html, /data-cloud-restore-open|Restaurar da nuvem/);
  assert.match(html, /<label>Usuário<\/label>/);
});

test('Configuração inicial sem restaurar; nuvem sem resposta não cria Administrador às cegas', () => {
  const setup = app.slice(app.indexOf('function setupFirstScreen'), app.indexOf('function enrollmentScreen'));
  assert.doesNotMatch(setup, /restaurar da nuvem|data-cloud-restore-open/i);
  assert.match(app, /function cloudWaitScreen/);
  assert.match(app, /info\.available&&info\.reachable===false\)return cloudWaitScreen/);
});

test('Restaurar da nuvem existe só no painel do Administrador', async () => {
  assert.doesNotMatch(app, /bindCloudRestoreEntry\(\);document\.querySelector\('#(login|setup)'\)/);
  assert.match(app, /data-cloud-restore-admin/);
  const { renderRecoveryKit } = await import('../frontend/pages/cloud.js');
  assert.doesNotMatch(renderRecoveryKit({ url: 'https://x' }), /Restaurar da nuvem/);
});
