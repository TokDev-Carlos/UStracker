import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../frontend/app.js', import.meta.url), 'utf8');

test('menus comerciais, financeiros e arquivos declaram ações sincronizadas', () => {
  for (const key of [
    'catalog-create', 'catalog-edit', 'purchase-create', 'coverage-create',
    'payment-create', 'expense-create', 'fiscal-create',
    'media-upload', 'attachment-upload', 'attachment-link',
  ]) assert.match(source, new RegExp(key));
  assert.ok((source.match(/bindActionForm/g) || []).length >= 20);
});

test('administração usa ciclo compartilhado nas mutações operacionais', () => {
  for (const key of [
    'settings-save', 'branding-upload', 'backup-create', 'backup-restore',
    'recovery-export', 'station-claim', 'station-emergency', 'admin-reset', 'password-change',
  ]) assert.match(source, new RegExp(key));
});

test('navegação entrega conteúdo somente para a requisição mais recente', () => {
  assert.match(source, /navigationSequence/);
  assert.match(source, /content\([^)]*,\s*lease\)/);
  assert.match(source, /lease\s*!==\s*navigationSequence/);
});
