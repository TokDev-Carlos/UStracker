// H-08 (2.4.0): filtro por coluna estilo planilha em todas as tabelas (ordenar, buscar, marcar valores).
// Funciona sobre o HTML já renderizado: qualquer <table> com <thead> ganha um botão ▾ em cada coluna.
// O filtro é lembrado enquanto o app estiver aberto (mesma tela + mesmas colunas), inclusive após recarregar a tabela.

const fold = value => String(value ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLocaleLowerCase('pt-BR').trim();
export const EMPTY_LABEL = '(vazio)';

// Texto -> valor comparável: dinheiro "R$ 1.234,56", número "1.234,5", data "dd/mm/aaaa" ou texto.
export function sortableValue(text) {
  const raw = String(text ?? '').trim();
  const date = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (date) return { n: Number(`${date[3]}${date[2]}${date[1]}`) };
  const money = raw.replace(/^(-?)\s*R\$\s*/, '$1');
  if (/^-?[\d.]+(,\d+)?%?$/.test(money) && /\d/.test(money)) return { n: Number(money.replace(/%$/, '').replace(/\./g, '').replace(',', '.')) };
  return { s: raw };
}

export function compareCells(a, b) {
  const x = sortableValue(a), y = sortableValue(b);
  if ('n' in x && 'n' in y) return x.n - y.n;
  if (!String(a ?? '').trim()) return 1;
  if (!String(b ?? '').trim()) return -1;
  return String(a).localeCompare(String(b), 'pt-BR', { numeric: true, sensitivity: 'base' });
}

// Valores distintos de uma coluna, ordenados, com contagem.
export function distinctValues(texts) {
  const counts = new Map();
  for (const text of texts) {
    const label = String(text ?? '').trim() || EMPTY_LABEL;
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => compareCells(a[0] === EMPTY_LABEL ? '' : a[0], b[0] === EMPTY_LABEL ? '' : b[0])).map(([value, count]) => ({ value, count }));
}

// filters: { [colIndex]: Set(valores permitidos) } ; cells: textos da linha.
export function rowPasses(cells, filters) {
  return Object.entries(filters).every(([index, allowed]) => !allowed || allowed.has(String(cells[index] ?? '').trim() || EMPTY_LABEL));
}

export function narrowValues(values, search) {
  const needle = fold(search);
  return needle ? values.filter(item => fold(item.value).includes(needle)) : values;
}

/* ---------- DOM ---------- */
const memory = new Map(); // chave da tabela -> { filters: {idx: [valores]}, sort: {index, asc} }
let popover = null;

const cellText = cell => (cell?.innerText ?? cell?.textContent ?? '').replace(/\s+/g, ' ').trim();

function tableKey(table, headers) {
  const page = (typeof location !== 'undefined' ? location.hash : '') || (document.querySelector('[data-page].active,[aria-current="page"]')?.textContent || '');
  return `${page}|${table.id || ''}|${headers.join('¦')}`;
}

// grupos: linha principal + linhas de detalhe (colspan) que vêm logo abaixo dela
function rowGroups(table, columnCount) {
  const body = table.tBodies[0];
  if (!body) return [];
  const groups = [];
  for (const tr of [...body.rows]) {
    const isDetail = tr.cells.length < columnCount && groups.length;
    if (isDetail) groups[groups.length - 1].extra.push(tr); else groups.push({ main: tr, extra: [] });
  }
  return groups;
}

function apply(table) {
  const state = table.__tf;
  const filters = Object.fromEntries(Object.entries(state.filters).map(([k, v]) => [k, v ? new Set(v) : null]));
  const groups = rowGroups(table, state.columns);
  if (state.sort) {
    const { index, asc } = state.sort;
    const sorted = [...groups].sort((g1, g2) => compareCells(cellText(g1.main.cells[index]), cellText(g2.main.cells[index])) * (asc ? 1 : -1));
    const body = table.tBodies[0];
    for (const g of sorted) { body.appendChild(g.main); g.extra.forEach(tr => body.appendChild(tr)); }
  }
  let shown = 0;
  for (const g of groups) {
    const ok = rowPasses([...g.main.cells].map(cellText), filters);
    for (const tr of [g.main, ...g.extra]) tr.classList.toggle('tf-hidden', !ok);
    if (ok) shown += 1;
  }
  [...table.tHead.rows[0].cells].forEach((th, i) => {
    th.classList.toggle('tf-active', Boolean(state.filters[i]) || state.sort?.index === i);
    const btn = th.querySelector('.tf-btn');
    if (btn) btn.textContent = state.sort?.index === i ? (state.sort.asc ? '▲' : '▼') : state.filters[i] ? '⧩' : '▾';
  });
  let note = table.parentElement?.querySelector(':scope > .tf-note');
  const active = Object.values(state.filters).some(Boolean);
  if (active) {
    if (!note) { note = document.createElement('div'); note.className = 'tf-note'; table.parentElement.insertBefore(note, table); }
    note.innerHTML = `Filtro ativo: ${shown} de ${groups.length} linha(s). <button type="button" class="tf-clear-all">Limpar filtros</button>`;
    note.querySelector('.tf-clear-all').onclick = () => { state.filters = {}; save(table); apply(table); };
  } else note?.remove();
}

function save(table) {
  const s = table.__tf;
  memory.set(s.key, { filters: { ...s.filters }, sort: s.sort ? { ...s.sort } : null });
}

export function closeFilterPopover() { popover?.remove(); popover = null; document.removeEventListener('mousedown', outside, true); }
function outside(event) { if (popover && !popover.contains(event.target) && !event.target.closest?.('.tf-btn')) closeFilterPopover(); }

// Popover genérico (usado pelas tabelas HTML e pela tabela de Clientes, que é paginada).
// opts: { title, values:[{value,count}], selected:[valores]|null, onSort(asc), onClear(), onApply([valores]|null) }
export function openFilterPopover(anchor, opts) {
  closeFilterPopover();
  const { title, values } = opts;
  const chosen = new Set(opts.selected || values.map(v => v.value));
  const esc = v => String(v).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
  popover = document.createElement('div');
  popover.className = 'tf-pop';
  popover.setAttribute('role', 'dialog');
  popover.__anchor = anchor;
  popover.innerHTML = `<div class="tf-title">${esc(title)}</div>
    <div class="tf-sort"><button type="button" data-sort="asc">↑ Ordenar A→Z / menor→maior</button><button type="button" data-sort="desc">↓ Ordenar Z→A / maior→menor</button></div>
    <input type="search" class="tf-search" placeholder="Buscar valor…" aria-label="Buscar valor">
    <label class="tf-all"><input type="checkbox" data-all> (Selecionar tudo)</label>
    <div class="tf-list"></div>
    <div class="tf-actions"><button type="button" class="ui-btn ui-btn-secondary" data-clear>Limpar</button><button type="button" class="ui-btn ui-btn-primary" data-apply>Aplicar</button></div>`;
  const list = popover.querySelector('.tf-list');
  const all = popover.querySelector('[data-all]');
  const search = popover.querySelector('.tf-search');
  const draw = () => {
    const visible = narrowValues(values, search.value);
    list.innerHTML = visible.length ? visible.map(v => `<label><input type="checkbox" data-v="${esc(v.value)}" ${chosen.has(v.value) ? 'checked' : ''}> <span>${esc(v.value)}</span> <small>${v.count}</small></label>`).join('') : '<p class="muted">Nada encontrado.</p>';
    all.checked = visible.length > 0 && visible.every(v => chosen.has(v.value));
    list.querySelectorAll('[data-v]').forEach(cb => { cb.onchange = () => { cb.checked ? chosen.add(cb.dataset.v) : chosen.delete(cb.dataset.v); all.checked = narrowValues(values, search.value).every(v => chosen.has(v.value)); }; });
  };
  search.oninput = draw;
  all.onchange = () => { narrowValues(values, search.value).forEach(v => all.checked ? chosen.add(v.value) : chosen.delete(v.value)); draw(); };
  popover.querySelectorAll('[data-sort]').forEach(b => { b.onclick = () => { closeFilterPopover(); opts.onSort(b.dataset.sort === 'asc'); }; });
  popover.querySelector('[data-clear]').onclick = () => { closeFilterPopover(); opts.onClear(); };
  popover.querySelector('[data-apply]').onclick = () => {
    // com busca digitada, aplica só o que está visível e marcado (como no Excel)
    const scope = search.value ? narrowValues(values, search.value).filter(v => chosen.has(v.value)).map(v => v.value) : [...chosen];
    closeFilterPopover();
    opts.onApply(scope.length === values.length ? null : scope);
  };
  search.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); popover.querySelector('[data-apply]').click(); } if (e.key === 'Escape') closeFilterPopover(); };
  draw();
  document.body.appendChild(popover);
  const r = anchor.getBoundingClientRect();
  const width = popover.offsetWidth || 260;
  popover.style.top = `${Math.round(r.bottom + window.scrollY + 4)}px`;
  popover.style.left = `${Math.round(Math.max(8, Math.min(r.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - width - 8)))}px`;
  document.addEventListener('mousedown', outside, true);
  search.focus();
}

export function filterButton(title, onOpen) {
  const btn = document.createElement('button');
  btn.type = 'button'; btn.className = 'tf-btn'; btn.textContent = '▾';
  btn.title = `Filtrar/ordenar por ${title}`; btn.setAttribute('aria-label', btn.title);
  btn.onclick = event => { event.stopPropagation(); event.preventDefault(); if (popover && popover.__anchor === btn) closeFilterPopover(); else onOpen(btn); };
  return btn;
}

function openPopover(table, index, anchor) {
  const state = table.__tf;
  const values = distinctValues(rowGroups(table, state.columns).map(g => cellText(g.main.cells[index])));
  openFilterPopover(anchor, {
    title: state.headers[index], values, selected: state.filters[index] || null,
    onSort: asc => { state.sort = { index, asc }; save(table); apply(table); },
    onClear: () => { delete state.filters[index]; if (state.sort?.index === index) state.sort = null; save(table); apply(table); },
    onApply: chosen => { if (chosen) state.filters[index] = chosen; else delete state.filters[index]; save(table); apply(table); },
  });
}

export function enhanceTable(table) {
  if (table.__tf || table.dataset.noFilter !== undefined || !table.tHead?.rows.length || !table.tBodies[0]) return false;
  const headRow = table.tHead.rows[0];
  const headers = [...headRow.cells].map(cellText);
  const columns = headers.length;
  if (!rowGroups(table, columns).length) return false; // sem linhas: nada a filtrar
  const key = tableKey(table, headers);
  const saved = memory.get(key);
  table.__tf = { key, headers, columns, filters: saved ? { ...saved.filters } : {}, sort: saved?.sort ? { ...saved.sort } : null };
  [...headRow.cells].forEach((th, index) => {
    if (!headers[index] || th.colSpan > 1 || /^(ações|ação|selecionar)$/i.test(headers[index])) return;
    const btn = filterButton(headers[index], anchor => openPopover(table, index, anchor));
    th.classList.add('tf-th');
    th.appendChild(btn);
  });
  if (saved) apply(table);
  return true;
}

export function enhanceTables(root = document) {
  root.querySelectorAll?.('table').forEach(enhanceTable);
}

export function installTableFilters(root = document.body) {
  if (typeof MutationObserver === 'undefined' || !root) return;
  let pending = false;
  const run = () => { pending = false; enhanceTables(root); };
  new MutationObserver(() => { if (!pending) { pending = true; requestAnimationFrame(run); } }).observe(root, { childList: true, subtree: true });
  window.addEventListener('hashchange', closeFilterPopover);
  run();
}
