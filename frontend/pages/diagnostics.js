// 2.6 — Sistema › Diagnóstico e avisos no topo (só administradores).
import { formatDateBR } from '../ui/formatters.js';

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const when = iso => (iso ? formatDateBR(iso, true) : '—');
const LABEL = { clients: 'clientes', vehicles: 'veículos', subscriptions: 'assinaturas', charges: 'cobranças', payments: 'pagamentos', expenses: 'despesas' };
const yes = (ok, good, bad) => (ok ? `<span class="badge badge-ok">${good}</span>` : `<span class="badge badge-alert">${bad}</span>`);

export function renderAlerts(items = []) {
  if (!items.length) return '';
  return `<div class="admin-alerts" role="status">${items.map(a => `<div class="admin-alert admin-alert-${a.level === 'error' ? 'error' : 'warn'}" data-alert="${esc(a.code)}">${esc(a.message)}</div>`).join('')}</div>`;
}

export function renderDiagnostics(d = {}) {
  const c = d.cloud || {}, b = d.backup || {}, k = d.disk || {};
  const pending = c.pending_since ? when(new Date(Number(c.pending_since) * 1000).toISOString()) : '—';
  const errors = (d.errors || []).length
    ? `<div class="table-wrap"><table class="compact-table" data-no-filter><thead><tr><th>Quando</th><th>Onde</th><th>Erro</th></tr></thead><tbody>${d.errors.map(e => `<tr><td>${esc(e.at)}</td><td>${esc(e.route)}</td><td>${esc(e.error)}</td></tr>`).join('')}</tbody></table></div>`
    : '<p class="muted">Nenhum erro registrado.</p>';
  const counts = b.counts ? Object.entries(b.counts).map(([t, n]) => `${esc(LABEL[t] || t)}: ${esc(n)}`).join(' · ') : '—';
  return `${renderAlerts(d.alerts || [])}
  <div class="panel"><h3>Diagnóstico</h3><dl class="runtime-grid">
    <dt>Versão</dt><dd>${esc(d.version || '—')} (banco ${esc(d.schema_version || '—')})</dd>
    <dt>Nuvem</dt><dd>${c.enabled ? (c.conflict ? yes(false, '', 'Conflito') : yes(true, 'Ligada', '')) : '<span class="badge badge-muted">Não conectada</span>'}</dd>
    <dt>Último envio à nuvem</dt><dd>${esc(when(c.last_upload_at))}</dd>
    <dt>Alterações esperando envio desde</dt><dd>${esc(pending)}</dd>
    <dt>Última cópia de segurança</dt><dd>${esc(when(b.last_at))} ${b.last_at ? yes(b.verified, 'Conferida', 'Falhou') : ''}</dd>
    <dt>Última cópia conferida</dt><dd>${esc(when(b.last_verified_at))}</dd>
    <dt>Conteúdo conferido</dt><dd>${counts}</dd>
    <dt>Cópias guardadas</dt><dd>${esc(b.files ?? 0)} (${esc(b.size_mb ?? 0)} MB)</dd>
    <dt>Espaço livre</dt><dd>${esc(k.free_gb ?? '—')} GB de ${esc(k.total_gb ?? '—')} GB</dd>
    <dt>Usuários ativos</dt><dd>${esc(d.users_active ?? 0)}</dd>
    <dt>Computadores</dt><dd>${esc((d.stations || []).map(s => s.name).join(', ') || '—')}</dd>
  </dl></div>
  <div class="panel"><h3>Últimos erros</h3>${errors}</div>
  <div class="panel"><h3>Suporte</h3><p class="muted">Gera um arquivo .zip com este diagnóstico e o registro de erros, <b>sem</b> senhas, chaves, banco de dados nem dados de clientes. Envie ao suporte quando pedirem.</p>
    <div class="actions"><button type="button" class="ui-btn ui-btn-secondary" data-support-package>Gerar pacote de suporte</button></div></div>`;
}
