const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]));

const environmentLabel = me => {
  if (me?.environment === 'test') return 'AMBIENTE TESTE';
  return me?.station?.is_writer ? 'PRODUÇÃO · ESCRITORA' : 'PRODUÇÃO · SOMENTE LEITURA';
};

export function pageHeader(title, subtitle = '', actions = '') {
  return `<header class="ui-page-header"><div class="ui-page-heading"><h2 class="ui-page-title">${escapeHtml(title)}</h2>${subtitle ? `<p class="ui-page-subtitle">${escapeHtml(subtitle)}</p>` : ''}</div>${actions ? `<div class="ui-toolbar">${actions}</div>` : ''}</header>`;
}

export function renderAppShell({ me, nav, onNavigate = () => {}, onSearch = () => {}, onHelp = () => {}, onUser = () => {}, onLogout = () => {}, onShutdown = () => {}, documentRef = globalThis.document }) {
  const root = documentRef.querySelector('#app');
  if (!root) throw new Error('UStracker app root not found');
  root.innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand">${iconImg('brand.logo',{className:'brand-logo',alt:''})}<span>UStracker</span></div><div class="muted sidebar-user">${escapeHtml(me?.name)} · ${escapeHtml(me?.environment)}</div><nav aria-label="Menu principal">${nav.map(([key, label]) => `<button type="button" data-page="${escapeHtml(key)}">${iconImg(`nav.${key}`,{className:'nav-icon',alt:''})}<span>${escapeHtml(label)}</span></button>`).join('')}</nav></aside><main class="main"><div class="topbar"><input id="globalSearch" class="search" aria-label="Busca global" placeholder="Pesquisar clientes, placas, planos…"><div class="topbar-actions"><span id="env" class="ui-pill ui-pill-active">${escapeHtml(environmentLabel(me))}</span><button type="button" id="globalHelp" class="ui-btn ui-btn-subtle" aria-label="Abrir ajuda" title="Ajuda contextual">? Ajuda</button><button type="button" id="globalUser" class="ui-btn ui-btn-subtle" aria-label="Abrir informações do usuário" title="Usuário atual">${escapeHtml(me?.name || 'Usuário')}</button><button type="button" id="globalLogout" class="ui-btn ui-btn-secondary" aria-label="Sair da sessão">${iconImg('action.logout',{alt:''})}<span>Sair</span></button><button type="button" id="globalShutdown" class="ui-btn ui-btn-danger" aria-label="Encerrar o UStracker">⏻ <span>Encerrar</span></button></div></div><div id="content"></div></main></div>`;
  root.querySelectorAll('[data-page]').forEach(button => { button.onclick = () => onNavigate(button.dataset.page); });
  const search = root.querySelector('#globalSearch');
  search.onkeydown = event => { if (event.key === 'Enter') onSearch(event.target.value); };
  root.querySelector('#globalHelp').onclick = onHelp;
  root.querySelector('#globalUser').onclick = onUser;
  root.querySelector('#globalLogout').onclick = onLogout;
  root.querySelector('#globalShutdown').onclick = onShutdown;
  return { setActive(page) { root.querySelectorAll('[data-page]').forEach(button => button.classList.toggle('active', button.dataset.page === page)); } };
}
import { iconImg } from './icon-registry.js';
