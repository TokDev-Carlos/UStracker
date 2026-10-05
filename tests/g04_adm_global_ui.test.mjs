// G-04 — telas: pergunta de segurança com pistas, Chave de Recuperação, painéis só do Adm Global.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../frontend/app.js', import.meta.url), 'utf8');

test('Login: segunda etapa com pergunta e pistas; bloqueio de 30 minutos', () => {
  assert.match(app, /if\(r\.challenge\)return challengeScreen/);
  assert.match(app, /question_id:challenge\.id/);
  assert.match(app, /err\?\.data\?\.hint/);
  assert.match(app, /retry_minutes\|\|30/);
});

test('Chave de Recuperação: mostrada ao configurar e usada no "Esqueci a senha"', async () => {
  assert.match(app, /showRecoveryKey\(r\.recovery_key\);boot\(\)/);
  assert.match(app, /'\/auth\/recover'/);
  const { renderLoginScreen } = await import('../frontend/ui/r2-ui.js');
  assert.match(renderLoginScreen({ complete: true }, { brand: {}, catalog: [] }), /data-recover-open/);
  assert.doesNotMatch(app, /Resetar slot/);
});

test('Recursos do Adm Global escondidos do Adm Local', () => {
  for (const id of ['restoreForm', 'recoveryForm', 'claimForm', 'emergencyForm', 'verifyAudit']) {
    assert.match(app, new RegExp(`isGlobal\\(\\)\\?\`[^\`]*id="${id}"`), id);
  }
  assert.match(app, /if\(isGlobal\(\)&&me\?\.environment==='production'\)loadPlacaPanel/);
  assert.match(app, /id="globalSetupForm"/);
  assert.match(app, /'\/global\/pass'/);
});
