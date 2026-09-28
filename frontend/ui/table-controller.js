const normalize = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

export function createTableController({ columns = [], rows = [], selectionMode = 'none', actions = [], pageSize = 20 } = {}) {
  let source = [...rows];
  let query = '';
  let sort = null;
  let ascending = true;
  let page = 0;
  const selected = new Set();

  const filtered = () => {
    const needle = normalize(query);
    const result = needle ? source.filter(row => columns.some(column => normalize(row[column.key]).includes(needle))) : [...source];
    if (sort) result.sort((left, right) => {
      const a = left[sort] ?? '';
      const b = right[sort] ?? '';
      const comparison = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), 'pt-BR', { numeric: true, sensitivity: 'base' });
      return ascending ? comparison : -comparison;
    });
    return result;
  };

  return {
    setRows(nextRows) { source = [...(nextRows || [])]; selected.clear(); page = 0; },
    setQuery(nextQuery) { query = nextQuery || ''; page = 0; },
    sortBy(key) { if (sort === key) ascending = !ascending; else { sort = key; ascending = true; } page = 0; },
    select(id) {
      if (selectionMode === 'none') return;
      if (selectionMode === 'single') selected.clear();
      if (selected.has(id) && selectionMode !== 'single') selected.delete(id); else selected.add(id);
    },
    setPage(nextPage) { page = Math.max(0, Number(nextPage) || 0); },
    view() {
      const matches = filtered();
      const pageCount = Math.max(1, Math.ceil(matches.length / pageSize));
      page = Math.min(page, pageCount - 1);
      return {
        columns, actions, selectionMode, rows: matches.slice(page * pageSize, (page + 1) * pageSize),
        total: matches.length, page, pageCount, query, sort, ascending,
        selectedIds: [...selected], empty: source.length === 0, noMatches: source.length > 0 && matches.length === 0,
      };
    },
  };
}

const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));

export function mountTableController(host, controller, { onSelectionChange = () => {} } = {}) {
  const render = () => {
    const state = controller.view();
    const selected = new Set(state.selectedIds.map(String));
    const selectionHead = state.selectionMode === 'none' ? '' : '<th class="ui-select-column">Selecionar</th>';
    const actionHead = state.actions.length ? '<th>Ações</th>' : '';
    const body = state.empty ? '<div class="ui-table-empty">Nenhum registro cadastrado.</div>' : state.noMatches ? '<div class="ui-table-empty">Nenhum resultado para este filtro.</div>' : `<div class="table-wrap"><table><thead><tr>${selectionHead}${state.columns.map(column => `<th data-sort="${escapeHtml(column.key)}">${escapeHtml(column.label)}${state.sort === column.key ? (state.ascending ? ' ▲' : ' ▼') : ''}</th>`).join('')}${actionHead}</tr></thead><tbody>${state.rows.map(row => `<tr class="${selected.has(String(row.id)) ? 'ui-row-selected' : ''}">${state.selectionMode === 'none' ? '' : `<td><input type="${state.selectionMode === 'single' ? 'radio' : 'checkbox'}" name="table-selection" data-select="${escapeHtml(row.id)}" ${selected.has(String(row.id)) ? 'checked' : ''} aria-label="Selecionar registro"></td>`}${state.columns.map(column => `<td>${column.format ? column.format(row[column.key], row) : escapeHtml(row[column.key])}</td>`).join('')}${state.actions.length ? `<td><div class="ui-row-actions">${state.actions.map(action => `<button type="button" class="ui-btn ui-btn-subtle" data-action="${escapeHtml(action.key)}" data-row="${escapeHtml(row.id)}">${iconImg(`action.${action.icon||action.key}`,{alt:''})}<span>${escapeHtml(action.label)}</span></button>`).join('')}</div></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
    host.innerHTML = `<div class="ui-workspace"><div class="ui-workspace-head"><input class="table-filter" aria-label="Filtrar registros" placeholder="Filtrar registros…" value="${escapeHtml(state.query)}"><span class="muted">${state.total} registro(s)</span></div><div class="ui-workspace-body">${body}</div><div class="pager"><button type="button" class="ui-btn ui-btn-secondary prev" ${state.page === 0 ? 'disabled' : ''}>Anterior</button><span>Página ${state.page + 1}/${state.pageCount}</span><button type="button" class="ui-btn ui-btn-secondary next" ${state.page >= state.pageCount - 1 ? 'disabled' : ''}>Próxima</button></div></div>`;
    host.querySelector('.table-filter').oninput = event => { controller.setQuery(event.target.value); render(); };
    host.querySelectorAll('[data-sort]').forEach(header => { header.onclick = () => { controller.sortBy(header.dataset.sort); render(); }; });
    host.querySelectorAll('[data-select]').forEach(input => { input.onchange = () => { controller.select(input.dataset.select); render(); onSelectionChange(controller.view().selectedIds); }; });
    host.querySelectorAll('[data-action]').forEach(button => { button.onclick = () => { const action = state.actions.find(item => item.key === button.dataset.action); const row = state.rows.find(item => String(item.id) === button.dataset.row); action?.onClick?.(row); }; });
    host.querySelector('.prev').onclick = () => { controller.setPage(state.page - 1); render(); };
    host.querySelector('.next').onclick = () => { controller.setPage(state.page + 1); render(); };
  };
  render();
  return { render };
}
import { iconImg } from './icon-registry.js';
