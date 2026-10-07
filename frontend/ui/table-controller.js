import { distinctValues, EMPTY_LABEL, filterButton, openFilterPopover } from './table-filters.js';

// texto exibido na célula (sem HTML), usado pelo filtro por coluna (H-08)
export const cellLabel = (column, row) => {
  const html = column.format ? String(column.format(row[column.key], row) ?? '') : String(row[column.key] ?? '');
  const text = html.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
  return text || EMPTY_LABEL;
};

const normalize = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

export function createTableController({ columns = [], rows = [], selectionMode = 'none', actions = [], pageSize = 20 } = {}) {
  let source = [...rows];
  let query = '';
  let sort = null;
  let ascending = true;
  let page = 0;
  const selected = new Set();
  const columnFilters = {}; // H-08: { key: Set(rótulos permitidos) }

  const filtered = () => {
    const needle = normalize(query);
    let result = needle ? source.filter(row => columns.some(column => normalize(row[column.key]).includes(needle))) : [...source];
    const active = columns.filter(column => columnFilters[column.key]);
    if (active.length) result = result.filter(row => active.every(column => columnFilters[column.key].has(cellLabel(column, row))));
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
    columnValues(key) { const column = columns.find(c => c.key === key); return column ? distinctValues(source.map(row => cellLabel(column, row))) : []; },
    columnFilter(key) { return columnFilters[key] ? [...columnFilters[key]] : null; },
    setColumnFilter(key, values) { if (values) columnFilters[key] = new Set(values); else delete columnFilters[key]; page = 0; },
    setSort(key, asc) { sort = key; ascending = asc !== false; page = 0; },
    setPage(nextPage) { page = Math.max(0, Number(nextPage) || 0); },
    view() {
      const matches = filtered();
      const pageCount = Math.max(1, Math.ceil(matches.length / pageSize));
      page = Math.min(page, pageCount - 1);
      return {
        columns, actions, selectionMode, rows: matches.slice(page * pageSize, (page + 1) * pageSize),
        total: matches.length, page, filteredColumns: Object.keys(columnFilters), pageCount, query, sort, ascending,
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
    const body = state.empty ? '<div class="ui-table-empty">Nenhum registro cadastrado.</div>' : state.noMatches ? '<div class="ui-table-empty">Nenhum resultado para este filtro.</div>' : `<div class="table-wrap"><table data-no-filter><thead><tr>${selectionHead}${state.columns.map(column => `<th data-sort="${escapeHtml(column.key)}">${escapeHtml(column.label)}${state.sort === column.key ? (state.ascending ? ' ▲' : ' ▼') : ''}</th>`).join('')}${actionHead}</tr></thead><tbody>${state.rows.map(row => `<tr class="${selected.has(String(row.id)) ? 'ui-row-selected' : ''}">${state.selectionMode === 'none' ? '' : `<td><input type="${state.selectionMode === 'single' ? 'radio' : 'checkbox'}" name="table-selection" data-select="${escapeHtml(row.id)}" ${selected.has(String(row.id)) ? 'checked' : ''} aria-label="Selecionar registro"></td>`}${state.columns.map(column => `<td>${column.format ? column.format(row[column.key], row) : escapeHtml(row[column.key])}</td>`).join('')}${state.actions.length ? `<td><div class="ui-row-actions">${state.actions.map(action => `<button type="button" class="ui-btn ui-btn-subtle" data-action="${escapeHtml(action.key)}" data-row="${escapeHtml(row.id)}">${iconImg(`action.${action.icon||action.key}`,{alt:''})}<span>${escapeHtml(action.label)}</span></button>`).join('')}</div></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
    host.innerHTML = `<div class="ui-workspace"><div class="ui-workspace-head"><input class="table-filter" aria-label="Filtrar registros" placeholder="Filtrar registros…" value="${escapeHtml(state.query)}"><span class="muted">${state.total} registro(s)</span>${state.filteredColumns.length ? '<button type="button" class="tf-clear-all" data-clear-columns>Limpar filtros</button>' : ''}</div><div class="ui-workspace-body">${body}</div><div class="pager"><button type="button" class="ui-btn ui-btn-secondary prev" ${state.page === 0 ? 'disabled' : ''}>Anterior</button><span>Página ${state.page + 1}/${state.pageCount}</span><button type="button" class="ui-btn ui-btn-secondary next" ${state.page >= state.pageCount - 1 ? 'disabled' : ''}>Próxima</button></div></div>`;
    host.querySelectorAll('th[data-sort]').forEach(th => {
      const key = th.dataset.sort;
      const column = state.columns.find(c => c.key === key);
      if (!column) return;
      th.classList.add('tf-th');
      th.classList.toggle('tf-active', state.filteredColumns.includes(key));
      const btn = filterButton(column.label, anchor => openFilterPopover(anchor, {
        title: column.label, values: controller.columnValues(key), selected: controller.columnFilter(key),
        onSort: asc => { controller.setSort(key, asc); render(); },
        onClear: () => { controller.setColumnFilter(key, null); render(); },
        onApply: chosen => { controller.setColumnFilter(key, chosen); render(); },
      }));
      if (state.filteredColumns.includes(key)) btn.textContent = '⧩';
      th.appendChild(btn);
    });
    const clearColumns = host.querySelector('[data-clear-columns]');
    if (clearColumns) clearColumns.onclick = () => { state.filteredColumns.forEach(key => controller.setColumnFilter(key, null)); render(); };
    host.querySelector('.table-filter').oninput = event => { controller.setQuery(event.target.value); render(); };
    host.querySelectorAll('[data-sort]').forEach(header => { header.onclick = () => { controller.sortBy(header.dataset.sort); render(); }; });
    host.querySelectorAll('[data-select]').forEach(input => { input.onchange = () => { controller.select(input.dataset.select); render(); onSelectionChange(controller.view().selectedIds); }; });
    host.querySelectorAll('[data-action]').forEach(button => { button.onclick = () => { const action = state.actions.find(item => item.key === button.dataset.action); const row = state.rows.find(item => String(item.id) === button.dataset.row); action?.onClick?.(row); }; });
    // 1.006: clicking anywhere on a row runs its first action (e.g. "Abrir ficha"); checkboxes and buttons keep their own behavior.
    if (state.actions.length) host.querySelectorAll('tbody tr').forEach((tr, index) => {
      tr.setAttribute('data-open-row', '');
      tr.onclick = event => { if (event.target.closest?.('input,button,a,label,select')) return; const row = state.rows[index]; if (row) state.actions[0]?.onClick?.(row); };
    });
    host.querySelector('.prev').onclick = () => { controller.setPage(state.page - 1); render(); };
    host.querySelector('.next').onclick = () => { controller.setPage(state.page + 1); render(); };
  };
  render();
  return { render };
}
import { iconImg } from './icon-registry.js';
