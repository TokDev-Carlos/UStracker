// H-17 (2.6) — envio à nuvem é automático e invisível: a tela não mostra botão "Enviar agora".
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderCloudPanel } from '../frontend/pages/cloud.js';

test('painel da nuvem conectada não tem botão de envio manual', () => {
  const html = renderCloudPanel({ enabled: true, generation: 3, last_upload_at: '2026-10-08T10:00:00Z' });
  assert.ok(!html.includes('data-cloud-sync'), 'sem botão Enviar agora');
  assert.ok(!html.includes('Enviar agora'));
  assert.match(html, /Envio automático/);
});

test('alterações aguardando aparecem só como situação, sem pedir ação', () => {
  const html = renderCloudPanel({ enabled: true, pending_changes: true });
  assert.match(html, /Salvando na nuvem/);
  assert.ok(!html.includes('data-cloud-sync'));
});
