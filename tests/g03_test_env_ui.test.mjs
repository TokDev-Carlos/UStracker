// G-03 — login sem escolha de banco; Teste só pelo Sistema (Administrador), com faixa de aviso.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');

test('Login sem escolha de ambiente', async () => {
  const { renderLoginScreen } = await import('../frontend/ui/r2-ui.js');
  const html = renderLoginScreen({ complete: true }, { brand: {}, catalog: [] });
  assert.doesNotMatch(html, /name="environment"|TESTE/);
});

test('Sistema troca de banco e mostra a faixa de Teste', () => {
  assert.match(app, /id="enterTest"/);
  assert.match(app, /id="leaveTest"/);
  assert.match(app, /'\/session\/environment'/);
  assert.match(app, /test-banner/);
  assert.match(app, /nada aqui vai para a nuvem/);
});
