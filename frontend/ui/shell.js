import { iconImg } from './icon-registry.js';

const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]));


export function pageHeader(title, subtitle = '', actions = '') {
  return `<header class="ui-page-header"><div class="ui-page-heading"><h2 class="ui-page-title">${escapeHtml(title)}</h2>${subtitle ? `<p class="ui-page-subtitle">${escapeHtml(subtitle)}</p>` : ''}</div>${actions ? `<div class="ui-toolbar">${actions}</div>` : ''}</header>`;
}

export function renderAppShellMarkup({ me, nav }) {
  const user = escapeHtml(me?.name || 'Usuário');
  return `<div class="shell"><header class="topbar shell-topbar"><div class="topbar-brand">${iconImg('brand.logo',{className:'brand-logo',alt:''})}<span>UStracker</span></div><input id="globalSearch" class="search" aria-label="Busca global" placeholder="Pesquisar clientes, placas, planos…"><div class="topbar-actions"><button type="button" id="globalHelp" class="ui-btn ui-btn-subtle topbar-help" aria-label="Abrir ajuda" title="Ajuda contextual">?</button><button type="button" id="globalUser" class="ui-btn ui-btn-subtle topbar-user" aria-label="Abrir informações do usuário" title="Usuário atual">${user}</button><button type="button" id="globalLogout" class="ui-btn ui-btn-secondary" aria-label="Sair da sessão">${iconImg('action.logout',{alt:''})}<span>Sair</span></button><button type="button" id="globalShutdown" class="ui-btn ui-btn-danger" aria-label="Encerrar o UStracker">${iconImg('action.shutdown',{alt:''})}<span>Encerrar</span></button></div></header><aside class="sidebar"><nav aria-label="Menu principal">${nav.map(([key, label]) => `<button type="button" data-page="${escapeHtml(key)}">${iconImg(`nav.${key}`,{className:'nav-icon',alt:''})}<span>${escapeHtml(label)}</span></button>`).join('')}</nav></aside><main class="main"><div id="content"></div></main></div>`;
}

export function renderAppShell({ me, nav, onNavigate = () => {}, onSearch = () => {}, onHelp = () => {}, onUser = () => {}, onLogout = () => {}, onShutdown = () => {}, documentRef = globalThis.document }) {
  const root = documentRef.querySelector('#app');
  if (!root) throw new Error('UStracker app root not found');
  root.innerHTML = renderAppShellMarkup({ me, nav });
  root.querySelectorAll('[data-page]').forEach(button => { button.onclick = () => onNavigate(button.dataset.page); });
  const search = root.querySelector('#globalSearch');
  search.onkeydown = event => { if (event.key === 'Enter') onSearch(event.target.value); };
  root.querySelector('#globalHelp').onclick = onHelp;
  root.querySelector('#globalUser').onclick = onUser;
  root.querySelector('#globalLogout').onclick = onLogout;
  root.querySelector('#globalShutdown').onclick = onShutdown;
  return { setActive(page) { root.querySelectorAll('[data-page]').forEach(button => button.classList.toggle('active', button.dataset.page === page)); } };
}
