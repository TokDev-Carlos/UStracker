// H-18 (2.6) — Diagnóstico e avisos (só administradores).
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderAlerts, renderDiagnostics } from '../frontend/pages/diagnostics.js';

test('avisos no topo: nada quando está tudo certo; erro em vermelho', () => {
  assert.equal(renderAlerts([]), '');
  const html = renderAlerts([{ code: 'backup_failed', level: 'error', message: 'A cópia falhou' }, { code: 'cloud_stale', level: 'warn', message: 'Sem nuvem' }]);
  assert.match(html, /admin-alert-error[^>]*data-alert="backup_failed"/);
  assert.match(html, /admin-alert-warn[^>]*data-alert="cloud_stale"/);
});

test('diagnóstico mostra versão, nuvem, cópia conferida, disco e botão de suporte', () => {
  const html = renderDiagnostics({ version: '2.6.0', schema_version: 16, cloud: { enabled: true }, backup: { last_at: '2026-10-08T10:00:00Z', verified: true, counts: { clients: 500 } },
    disk: { free_gb: 120, total_gb: 500 }, errors: [{ at: '2026-10-08T10:00', route: 'POST /api/v1/clients', error: 'ValueError' }], users_active: 3, stations: [{ name: 'UStracker Servidor 1' }] });
  for (const t of ['2.6.0', 'Conferida', 'clientes: 500', '120 GB', 'ValueError', 'UStracker Servidor 1', 'data-support-package']) assert.ok(html.includes(t), t);
  assert.ok(!html.includes('<input'), 'só leitura');
});
