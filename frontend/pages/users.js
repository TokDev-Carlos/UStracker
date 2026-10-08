// U-02 — Sistema › Usuários: usuários (login próprio) e pacotes de acesso.
import { formatDateBR } from '../ui/formatters.js';

const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

function packageOptions(packages, selected = 'OPERADOR') {
  return packages.filter(p => p.allowed !== false).map(p => `<option value="${esc(p.id)}"${p.id === selected ? ' selected' : ''}>${esc(p.title)}</option>`).join('');
}

/** Permission grid grouped by module, as checkboxes. */
export function renderPermissionGrid(permissions = [], checked = [], { disabled = false } = {}) {
  const on = new Set(checked);
  const groups = new Map();
  permissions.forEach(p => { if (!groups.has(p.group)) groups.set(p.group, []); groups.get(p.group).push(p); });
  return `<div class="perm-grid">${[...groups.entries()].map(([group, items]) => `<fieldset class="perm-group"><legend>${esc(group)}</legend>${items.map(p => `<label class="ui-check"><input type="checkbox" name="perm" value="${esc(p.key)}"${on.has(p.key) ? ' checked' : ''}${disabled ? ' disabled' : ''}> ${esc(p.label)}</label>`).join('')}</fieldset>`).join('')}</div>`;
}

export function renderUsersTab(data = {}) {
  const users = data.items || [];
  const packages = data.packages || [];
  const userRows = users.map(u => `<tr class="${u.active ? '' : 'is-muted'}"><td><strong>${esc(u.name)}</strong>${u.full_name ? `<div class="muted">${esc(u.full_name)}</div>` : ''}</td><td>${esc(u.package_title || u.package_id)}</td><td>${u.active ? '<span class="badge badge-ok">Ativo</span>' : '<span class="badge badge-muted">Desativado</span>'}</td><td>${esc(formatDateBR(u.created_at, false) || '—')}</td><td><div class="row-actions"><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-user-edit="${esc(u.id)}">Editar</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-user-toggle="${esc(u.id)}" data-active="${u.active ? 1 : 0}">${u.active ? 'Desativar' : 'Reativar'}</button><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-user-delete="${esc(u.id)}" data-name="${esc(u.name)}">Excluir</button></div></td></tr>`).join('');
  const packageRows = packages.map(p => `<tr><td><strong>${esc(p.title)}</strong>${p.builtin ? ' <span class="badge">Padrão</span>' : ''}<div class="muted">${esc(p.description || '')}</div></td><td class="money">${Number(p.permissions?.length || 0)}</td><td class="money">${Number(p.users || 0)}</td><td><div class="row-actions"><button type="button" class="ui-btn ui-btn-subtle ui-btn-sm" data-package-view="${esc(p.id)}">${p.builtin ? 'Ver' : 'Editar'}</button>${p.builtin ? '' : `<button type="button" class="ui-btn ui-btn-subtle ui-btn-sm ui-btn-del" data-package-delete="${esc(p.id)}" data-title="${esc(p.title)}"${p.users ? ' disabled title="Em uso"' : ''}>Excluir</button>`}</div></td></tr>`).join('');
  const globalNote = data.global_users ? ' <b>O login vale em todos os computadores da empresa</b> e é único: criar, alterar ou excluir precisa de internet. Login excluído não pode ser usado de novo.' : '';
  const packagesPanel = data.can_packages === false ? '' : `<div class="panel"><div class="panel-head-row"><h3>Pacotes de acesso</h3><button type="button" class="ui-btn ui-btn-secondary" data-package-new>+ Novo pacote</button></div>
      <p class="muted"><b>Operador</b> cria e atualiza dados. <b>Gerente</b> também exclui, estorna, vê despesas, custos e relatórios e cria usuários (menos administradores). Crie pacotes próprios, como “Financeiro sem Despesas”.</p>
      <div class="table-wrap"><table class="compact-table"><thead><tr><th>Pacote</th><th class="money">Permissões</th><th class="money">Usuários</th><th></th></tr></thead><tbody>${packageRows}</tbody></table></div></div>`;
  return `<div class="panel"><div class="panel-head-row"><h3>Usuários</h3><button type="button" class="ui-btn ui-btn-primary" data-user-new>+ Novo usuário</button></div>
      <p class="muted">Cada pessoa entra com o próprio nome e senha e vê só o que o pacote dela permite. Os Administradores têm acesso a tudo.${globalNote}</p>
      ${users.length ? `<div class="table-wrap"><table class="compact-table"><thead><tr><th>Usuário</th><th>Pacote</th><th>Situação</th><th>Criado em</th><th></th></tr></thead><tbody>${userRows}</tbody></table></div>` : '<p class="cp-empty muted">Nenhum usuário ainda. Clique em “Novo usuário”.</p>'}</div>
    ${packagesPanel}`;
}

export function renderUserForm(user = null, packages = []) {
  return `<form id="userForm" class="cp-form"><div class="cp-form-grid">
    <div class="field"><label>Nome de acesso*</label><input name="name" required autocomplete="off" value="${esc(user?.name || '')}" placeholder="Ex.: ana.souza"${user ? ' disabled title="O login não muda depois de criado"' : ''}></div>
    <div class="field"><label>Nome completo</label><input name="full_name" value="${esc(user?.full_name || '')}"></div>
    <div class="field"><label>Pacote*</label><select name="package_id" required>${packageOptions(packages, user?.package_id || 'OPERADOR')}</select></div>
    <div class="field"><label>${user ? 'Nova senha (deixe vazio para manter)' : 'Senha inicial*'}</label><input name="password" type="password" autocomplete="new-password" minlength="4"${user ? '' : ' required'} placeholder="mínimo 4 caracteres"></div>
  </div><p class="muted">Login: letras, números, ponto, hífen ou sublinhado (3 a 32, sem espaço nem acento). A senha definida aqui é provisória: a pessoa troca ao entrar.</p>
  <div class="actions"><button type="submit" class="ui-btn ui-btn-primary">${user ? 'Salvar' : 'Criar usuário'}</button></div></form>`;
}

export function renderPackageForm(pkg = null, permissions = []) {
  const readonly = !!pkg?.builtin;
  return `<form id="packageForm" class="cp-form">
    <div class="cp-form-grid"><div class="field"><label>Título*</label><input name="title" required value="${esc(pkg?.title || '')}"${readonly ? ' disabled' : ''} placeholder="Ex.: Financeiro sem Despesas"></div>
    <div class="field field-wide"><label>Descrição</label><input name="description" value="${esc(pkg?.description || '')}"${readonly ? ' disabled' : ''}></div></div>
    ${readonly ? '<p class="muted">Pacote padrão: não pode ser alterado. Para outro conjunto, crie um pacote novo.</p>' : ''}
    ${renderPermissionGrid(permissions, pkg?.permissions || [], { disabled: readonly })}
    ${readonly ? '' : '<div class="actions"><button type="submit" class="ui-btn ui-btn-primary">Salvar pacote</button></div>'}</form>`;
}

export function bindUsersTab(section, { data, api, toast, confirmDialog, openDrawer, closeOverlay, bindActionForm, bindActionButton, reload }) {
  const packages = data.packages || [];
  const permissions = data.permissions || [];
  const users = data.items || [];
  const formJson = form => Object.fromEntries(new FormData(form).entries());
  const openUser = user => {
    const drawer = openDrawer({ title: user ? `Usuário ${user.name}` : 'Novo usuário', subtitle: 'Login próprio com pacote de acesso', content: renderUserForm(user, packages) });
    const form = drawer.querySelector('#userForm');
    bindActionForm(form, { key: 'user-save', notify: toast, successMessage: user ? 'Usuário atualizado.' : 'Usuário criado.',
      action: async () => { const p = formJson(form); if (user && !p.password) delete p.password; await api(user ? `/users/${user.id}` : '/users', { method: user ? 'PATCH' : 'POST', body: JSON.stringify(p) }); closeOverlay(); },
      refresh: reload });
  };
  const openPackage = pkg => {
    const drawer = openDrawer({ title: pkg ? `Pacote ${pkg.title}` : 'Novo pacote', subtitle: 'Marque o que este pacote pode ver e fazer', content: renderPackageForm(pkg, permissions) });
    drawer.querySelector('.ui-drawer')?.classList.add('r2-profile-wide');
    const form = drawer.querySelector('#packageForm');
    if (pkg?.builtin) return;
    bindActionForm(form, { key: 'package-save', notify: toast, successMessage: 'Pacote salvo.',
      action: async () => { const fd = new FormData(form); const body = { title: fd.get('title'), description: fd.get('description'), permissions: fd.getAll('perm') }; await api(pkg ? `/packages/${pkg.id}` : '/packages', { method: pkg ? 'PATCH' : 'POST', body: JSON.stringify(body) }); closeOverlay(); },
      refresh: reload });
  };
  section.querySelector('[data-user-new]')?.addEventListener('click', () => openUser(null));
  section.querySelector('[data-package-new]')?.addEventListener('click', () => openPackage(null));
  section.querySelectorAll('[data-user-edit]').forEach(button => { button.onclick = () => openUser(users.find(u => String(u.id) === button.dataset.userEdit)); });
  section.querySelectorAll('[data-package-view]').forEach(button => { button.onclick = () => openPackage(packages.find(p => p.id === button.dataset.packageView)); });
  section.querySelectorAll('[data-user-toggle]').forEach(button => bindActionButton(button, {
    key: 'user-toggle:' + button.dataset.userToggle, notify: toast, refresh: reload,
    confirm: button.dataset.active === '1' ? 'Desativar este usuário? Ele não consegue mais entrar (pode ser reativado).' : '',
    successMessage: button.dataset.active === '1' ? 'Usuário desativado.' : 'Usuário reativado.',
    action: () => api(`/users/${button.dataset.userToggle}`, { method: 'PATCH', body: JSON.stringify({ active: button.dataset.active !== '1' }) }) }));
  section.querySelectorAll('[data-user-delete]').forEach(button => bindActionButton(button, {
    key: 'user-delete:' + button.dataset.userDelete, notify: toast, refresh: reload,
    confirm: `Excluir o usuário “${button.dataset.name}” em todos os computadores? O login fica reservado e não pode ser criado de novo.`,
    successMessage: 'Usuário excluído.', action: () => api(`/users/${button.dataset.userDelete}`, { method: 'PATCH', body: JSON.stringify({ deleted: true }) }) }));
  section.querySelectorAll('[data-package-delete]').forEach(button => bindActionButton(button, {
    key: 'package-delete:' + button.dataset.packageDelete, notify: toast, refresh: reload, confirm: `Excluir o pacote “${button.dataset.title}”?`,
    successMessage: 'Pacote excluído.', action: () => api(`/packages/${button.dataset.packageDelete}`, { method: 'DELETE' }) }));
}
