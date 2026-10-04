const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[character]));

const initialState = () => ({
  query: '', items: [], activeIndex: -1, selected: null,
  loading: false, error: '', open: false,
});

export function createEntityAutocomplete({
  search,
  debounceMs = 200,
  limit = 30,
  schedule = globalThis.setTimeout,
  cancelSchedule = globalThis.clearTimeout,
  onState = () => {},
  onSelection = () => {},
} = {}) {
  if (typeof search !== 'function') throw new Error('search function is required');
  let state = initialState();
  let timer = null;
  let requestSequence = 0;
  const publish = patch => {
    state = { ...state, ...patch };
    onState({ ...state });
    return state;
  };
  const select = item => {
    if (!item) return null;
    publish({ query: item.display_name || '', selected: item, activeIndex: -1, open: false, error: '' });
    onSelection(item);
    return item;
  };
  const clear = () => {
    requestSequence += 1;
    if (timer) cancelSchedule(timer);
    timer = null;
    state = initialState();
    onState({ ...state });
    onSelection(null);
  };
  const input = value => {
    const query = String(value ?? '');
    requestSequence += 1;
    const sequence = requestSequence;
    if (timer) cancelSchedule(timer);
    timer = null;
    if (!query.trim()) {
      clear();
      return;
    }
    publish({ query, items: [], activeIndex: -1, selected: null, loading: false, error: '', open: true });
    onSelection(null);
    timer = schedule(async () => {
      timer = null;
      publish({ loading: true, error: '', open: true });
      try {
        const result = await search(query, limit);
        if (sequence !== requestSequence) return;
        const items = (Array.isArray(result) ? result : result?.items || []).slice(0, Math.min(Number(limit) || 30, 30));
        publish({ items, activeIndex: -1, loading: false, error: '', open: true });
      } catch (error) {
        if (sequence !== requestSequence) return;
        publish({ items: [], activeIndex: -1, loading: false, error: error?.message || 'Falha ao pesquisar.', open: true });
      }
    }, debounceMs);
  };
  const keyDown = key => {
    if (key === 'Escape') { publish({ open: false, activeIndex: -1 }); return null; }
    if (!state.items.length) return null;
    if (key === 'ArrowDown') {
      publish({ activeIndex: (state.activeIndex + 1) % state.items.length, open: true });
      return null;
    }
    if (key === 'ArrowUp') {
      publish({ activeIndex: state.activeIndex <= 0 ? state.items.length - 1 : state.activeIndex - 1, open: true });
      return null;
    }
    if (key === 'Enter' && state.activeIndex >= 0) return select(state.items[state.activeIndex]);
    return null;
  };
  return { input, keyDown, clear, select, getState: () => ({ ...state }) };
}

export function renderEntityAutocompleteResults(state = {}) {
  if (!state.open) return '';
  if (state.loading) return '<div class="muted" data-entity-status>Pesquisando…</div>';
  if (state.error) return `<div class="error" data-entity-status>${escapeHtml(state.error)}</div>`;
  const items = (state.items || []).slice(0, 30);
  if (!items.length) return state.query ? '<div class="muted" data-entity-status>Nenhum resultado.</div>' : '';
  return items.map((item, index) => `<button type="button" role="option" data-entity-option="${escapeHtml(item.id)}" class="entity-autocomplete-option ${index === state.activeIndex ? 'active' : ''}" aria-selected="${index === state.activeIndex ? 'true' : 'false'}"><strong>${escapeHtml(item.display_name || item.code || 'Cliente')}</strong>${item.code ? `<span class="ui-code">${escapeHtml(item.code)}</span>` : ''}${item.primary_company ? `<span>${escapeHtml(item.primary_company)}</span>` : ''}${item.primary_document ? `<span>${escapeHtml(item.primary_document)}</span>` : ''}</button>`).join('');
}

export function renderEntityAutocomplete({ name = 'client_id', label = 'Cliente', selected = null, required = false, placeholder = 'Digite para pesquisar' } = {}) {
  const query = selected?.display_name || '';
  return `<div class="field entity-autocomplete" data-entity-autocomplete><label>${escapeHtml(label)}${required ? '*' : ''}</label><div class="entity-autocomplete-input"><input type="search" data-entity-query value="${escapeHtml(query)}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" ${required ? 'required' : ''} aria-autocomplete="list"><input type="hidden" name="${escapeHtml(name)}" value="${escapeHtml(selected?.id || '')}"><button type="button" class="ui-btn ui-btn-subtle" data-entity-clear aria-label="Limpar seleção">×</button></div><div class="entity-autocomplete-results" data-entity-results role="listbox"></div></div>`;
}

export function bindEntityAutocomplete(root, { search, debounceMs = 200, limit = 30, onSelection = () => {} } = {}) {
  const host = root?.matches?.('[data-entity-autocomplete]') ? root : root?.querySelector?.('[data-entity-autocomplete]');
  if (!host) return null;
  const queryInput = host.querySelector('[data-entity-query]');
  const hiddenInput = host.querySelector('input[type=hidden]');
  const results = host.querySelector('[data-entity-results]');
  const clearButton = host.querySelector('[data-entity-clear]');
  const controller = createEntityAutocomplete({
    search, debounceMs, limit,
    onState: state => {
      results.innerHTML = renderEntityAutocompleteResults(state);
      hiddenInput.value = state.selected?.id || '';
      if (state.selected && queryInput.value !== state.query) queryInput.value = state.query;
    },
    onSelection,
  });
  queryInput.oninput = () => controller.input(queryInput.value);
  queryInput.onkeydown = event => {
    if (['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(event.key)) {
      event.preventDefault();
      controller.keyDown(event.key);
    }
  };
  clearButton.onclick = () => { controller.clear(); queryInput.value = ''; queryInput.focus(); };
  results.onclick = event => {
    const option = event.target.closest('[data-entity-option]');
    if (!option) return;
    const item = controller.getState().items.find(row => String(row.id) === option.dataset.entityOption);
    if (item) { controller.select(item); queryInput.value = item.display_name || ''; }
  };
  return controller;
}
