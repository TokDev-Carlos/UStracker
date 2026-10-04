// C-04..C-06 / C-09 — Nuvem, pontos de restauração, Lixeira e restauração em máquina nova.
import { formatDateBR } from '../ui/formatters.js';

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const size = n => { const v = Number(n || 0); return v > 1048576 ? `${(v / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(v / 1024))} KB`; };
const when = iso => iso ? formatDateBR(iso, true) : '—';

export function cloudStatusBadge(s = {}) {
  if (!s.enabled) return '<span class="badge badge-muted">Não conectada</span>';
  if (s.conflict) return '<span class="badge badge-alert">Conflito</span>';
  if (s.last_error) return '<span class="badge badge-warn">Com erro</span>';
  if (s.running) return '<span class="badge badge-info">Enviando…</span>';
  if (s.pending_changes) return '<span class="badge badge-info">Alterações aguardando envio</span>';
  return '<span class="badge badge-ok">Protegido</span>';
}

export function renderCloudPanel(s = {}) {
  const connectForm = `<form id="cloudConnectForm" class="cloud-connect"><div class="row">
      <div class="field field-wide"><label>URL do App da Web (Apps Script)</label><input name="url" type="url" required placeholder="https://script.google.com/macros/s/…/exec" value="${esc(s.url || '')}"></div>
      <div class="field"><label>Código de conexão</label><input name="secret" type="password" required autocomplete="off" placeholder="48 caracteres"></div></div>
      <div class="actions"><button class="ui-btn ui-btn-primary">${s.enabled ? 'Reconectar' : 'Conectar e enviar agora'}</button></div></form>`;
  const status = s.enabled ? `<dl class="cloud-facts">
      <dt>Situação</dt><dd>${cloudStatusBadge(s)}</dd>
      <dt>Último envio</dt><dd>${esc(when(s.last_upload_at))}${s.last_upload_size ? ` · ${esc(size(s.last_upload_size))}` : ''}</dd>
      <dt>Versão na nuvem</dt><dd>${esc(s.generation || 0)}</dd>
      <dt>Fotos e anexos na nuvem</dt><dd>${esc(s.files_in_cloud || 0)}</dd>
      <dt>Envio automático</dt><dd>Segundos após cada alteração e ao fechar o sistema</dd></dl>
    ${s.last_error && !s.conflict ? `<p class="notice">Último erro: ${esc(s.last_error)}. O sistema tenta de novo sozinho.</p>` : ''}
    ${s.conflict ? `<div class="notice cloud-conflict"><strong>Outra máquina enviou dados mais novos.</strong><p>Para não perder nada, este computador parou de enviar. Se esta é a máquina certa, substitua a nuvem; senão, use Avançado › Restaurar da nuvem.</p><div class="actions"><button type="button" class="ui-btn ui-btn-danger" data-cloud-force>Usar este computador e substituir a nuvem</button></div></div>` : ''}
    <div class="actions"><button type="button" class="ui-btn ui-btn-primary" data-cloud-sync>Enviar agora</button><button type="button" class="ui-btn ui-btn-secondary" data-cloud-points>Pontos de restauração</button><button type="button" class="ui-btn ui-btn-subtle" data-cloud-kit>Kit de recuperação</button><button type="button" class="ui-btn ui-btn-subtle" data-cloud-disconnect>Desconectar</button></div>
    <details class="more-options"><summary>Trocar conexão</summary>${connectForm}</details>`
    : `<p>Guarde uma cópia cifrada de tudo no seu Google Drive. Se o computador quebrar ou a pasta for apagada, você recupera em outra máquina.</p>
       <ol class="cloud-steps"><li>Publique o script <b>UStracker Cloud</b> no seu Google (guia: <code>Docs\\NUVEM_GOOGLE_DRIVE.md</code>, 5 minutos).</li><li>Cole aqui a URL do App da Web e o Código de conexão.</li></ol>${connectForm}`;
  return `<div class="panel cloud-panel"><h3>Nuvem (Google Drive)</h3>
    <p class="muted">Tudo sai do computador já cifrado: o Google guarda, mas não consegue ler. Só o que for excluído dentro do sistema sai da nuvem, depois de 14 dias na Lixeira.</p>
    ${status}<div data-cloud-points-box></div>
    <details class="more-options cloud-advanced"><summary>Avançado (Administrador)</summary>
      <p class="muted">Computadores novos recebem os dados sozinhos. Use só para trocar à força os dados <b>deste</b> computador pelos de uma nuvem.</p>
      <div class="actions"><button type="button" class="ui-btn ui-btn-danger" data-cloud-restore-admin>Restaurar da nuvem…</button></div></details></div>`;
}

export function renderPointsTable(items = []) {
  if (!items.length) return '<p class="muted">Nenhum ponto de restauração.</p>';
  return `<h4>Pontos de restauração (últimos 14 dias; o mais recente nunca expira)</h4><div class="table-wrap"><table class="compact-table"><thead><tr><th>Data</th><th>Versão</th><th>Tamanho</th><th>Clientes</th><th></th></tr></thead><tbody>${items.map(p => `<tr><td>${esc(when(p.created_at))}</td><td>${esc(p.generation)}${p.is_head ? ' <span class="badge badge-ok">atual</span>' : ''}</td><td>${esc(size(p.size))}</td><td>${esc(p.meta?.counts?.clients ?? '—')}</td><td>${p.is_head ? '' : `<button type="button" class="ui-btn ui-btn-secondary ui-btn-sm" data-cloud-restore-point="${esc(p.id)}">Voltar para este ponto</button>`}</td></tr>`).join('')}</tbody></table></div>`;
}

export function renderRecoveryKit(s = {}) {
  return `<div class="cloud-kit"><p>Guarde estas duas informações fora do computador (papel, cofre de senhas). Com elas e a sua senha de sempre você recupera tudo em outra máquina.</p>
    <dl class="cloud-facts"><dt>URL do App da Web</dt><dd><code>${esc(s.url || '')}</code></dd><dt>Código de conexão</dt><dd>O mesmo exibido pelo script ao executar <code>instalar</code> (não fica visível aqui por segurança).</dd></dl>
    <p class="muted">Computador novo: instale com <b>UStracker_install_x64.exe</b> e entre com seu usuário e senha — os dados chegam sozinhos da nuvem.</p></div>`;
}

export function renderTrashPanel(items = []) {
  const rows = items.map(i => `<tr><td><span class="cat-chip">${esc(i.kind_label)}</span></td><td>${esc(i.label)}</td><td>${esc(when(i.deleted_at))}</td><td>${i.days_left <= 2 ? `<span class="badge badge-alert">${esc(i.days_left)} dia(s)</span>` : `${esc(i.days_left)} dias`}</td><td><button type="button" class="ui-btn ui-btn-primary ui-btn-sm" data-trash-restore="${esc(i.id)}">Restaurar</button></td></tr>`).join('');
  return `<div class="panel"><h3>Lixeira (14 dias)</h3><p class="muted">O que for excluído no sistema fica aqui por 14 dias e pode voltar com um clique. Depois disso é apagado de vez, inclusive da nuvem. Clientes arquivados saem da Lixeira mas o histórico financeiro deles é mantido.</p>
    ${items.length ? `<div class="table-wrap"><table class="compact-table"><thead><tr><th>Tipo</th><th>Item</th><th>Excluído em</th><th>Apaga em</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="cp-empty muted">A Lixeira está vazia.</p>'}</div>`;
}

export function renderCloudRestoreForm() {
  return `<form id="cloudRestoreForm"><p><b>Uso interno do Administrador.</b> Substitui todos os dados deste computador pelos de uma nuvem (URL + código). Os dados atuais são guardados em <code>UserData\\Backups</code> antes. Depois, todos entram de novo.</p>
    <div class="field"><label>URL do App da Web</label><input name="url" type="url" required placeholder="https://script.google.com/macros/s/…/exec"></div>
    <div class="field"><label>Código de conexão</label><input name="secret" type="password" required autocomplete="off"></div>
    <label class="cloud-confirm"><input type="checkbox" name="ok" required> Entendo que os dados deste computador serão substituídos pelos da nuvem.</label>
    <div class="actions"><button class="ui-btn ui-btn-primary">Restaurar da nuvem</button></div><div data-cloud-restore-out></div></form>`;
}

// S-05..S-07 — Placa de direção: onde estão os bancos (Banco 1 principal, Banco 2+ espelhos).
export function renderPlacaPanel(d = {}, status = {}) {
  const gh = d.github || {};
  const mirrors = (status.mirrors || []).map((m, i) => `<li>Banco ${i + 2}: ${m.error ? `<span class="badge badge-warn">erro</span> ${esc(m.error)}` : m.last_ok ? `<span class="badge badge-ok">em dia</span> ${esc(when(m.last_ok))}` : '<span class="badge badge-muted">aguardando 1º envio</span>'}</li>`).join('');
  return `<div class="panel placa-panel"><h3>Placa de direção (Servidores)</h3>
    <p class="muted">Diz a todos os computadores onde ficam os bancos. <b>Banco 1</b> é o principal; <b>Banco 2</b> em diante recebem cópia de tudo. Para trocar de conta Google: acrescente a conta nova como Banco 2, espere “em dia”, passe-a para Banco 1 e publique. Os Servidores seguem sozinhos.</p>
    <p>Placa atual: <b>${d.seq ? `versão ${esc(d.seq)}` : 'ainda não publicada'}</b>${d.placa_url ? ` · <code>${esc(d.placa_url)}</code>` : ''}${status.placa_error ? ` · <span class="badge badge-warn">${esc(status.placa_error)}</span>` : ''}</p>
    ${mirrors ? `<ul class="placa-mirrors">${mirrors}</ul>` : ''}
    <form id="placaForm">
      <div class="field"><label>Bancos (formulário)</label><textarea name="form" rows="9" spellcheck="false" class="mono">${esc(d.form || '')}</textarea></div>
      <details class="more-options"${gh.repo ? '' : ' open'}><summary>Onde publicar (GitHub)</summary>
        <div class="row"><div class="field"><label>Repositório (dono/nome)</label><input name="repo" value="${esc(gh.repo || '')}" placeholder="ustracker/config"></div>
        <div class="field"><label>Arquivo</label><input name="path" value="${esc(gh.path || 'placa.json')}"></div>
        <div class="field"><label>Ramo</label><input name="branch" value="${esc(gh.branch || 'main')}"></div></div>
        <div class="row"><div class="field field-wide"><label>Token do GitHub ${d.github_token_saved ? '(já salvo; preencha só para trocar)' : '(permissão “Contents: write” só neste repositório)'}</label><input name="token" type="password" autocomplete="off"></div></div>
        <div class="field"><label>Ou endereço público da placa (se publicar à mão)</label><input name="placa_url" value="${esc(d.placa_url || '')}" placeholder="https://raw.githubusercontent.com/…/placa.json"></div>
      </details>
      <div class="actions"><button class="ui-btn ui-btn-primary">Publicar placa</button><button type="button" class="ui-btn ui-btn-secondary" data-placa-check>Verificar agora</button></div>
      <div data-placa-out></div></form></div>`;
}
