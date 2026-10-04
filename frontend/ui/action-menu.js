// AJ-10 — small anchored "Ações" menu. Keyboard: arrows move, Esc closes, Enter activates.
const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

export function renderActionMenu(items = []) {
  return `<div class="action-menu" role="menu">${items.map((item, i) => item.separator
    ? '<hr role="separator">'
    : `<button type="button" role="menuitem" data-menu-index="${i}" class="action-menu-item${item.danger ? ' is-danger' : ''}${item.primary ? ' is-primary' : ''}">${esc(item.label)}${item.hint ? `<small>${esc(item.hint)}</small>` : ''}</button>`).join('')}</div>`;
}

export function closeActionMenu(documentRef = globalThis.document) {
  const open = documentRef.querySelector('#uiActionMenu');
  if (!open) return;
  open._anchor?.setAttribute('aria-expanded', 'false');
  open._cleanup?.();
  open.remove();
}

export function openActionMenu(anchor, allItems = [], documentRef = globalThis.document) {
  const items = allItems.filter(item => item && !item.hidden);
  const wasOpen = documentRef.querySelector('#uiActionMenu')?._anchor === anchor;
  closeActionMenu(documentRef);
  if (wasOpen) return null;
  const host = documentRef.createElement('div');
  host.id = 'uiActionMenu';
  host.className = 'action-menu-host';
  host.innerHTML = renderActionMenu(items);
  documentRef.body.append(host);
  const rect = anchor.getBoundingClientRect();
  const view = documentRef.documentElement;
  const width = host.offsetWidth || 240, height = host.offsetHeight || 200;
  const left = Math.max(8, Math.min(rect.right - width, view.clientWidth - width - 8));
  const top = rect.bottom + height + 8 > view.clientHeight ? Math.max(8, rect.top - height - 4) : rect.bottom + 4;
  host.style.left = `${left + globalThis.scrollX}px`;
  host.style.top = `${top + globalThis.scrollY}px`;
  host._anchor = anchor;
  anchor.setAttribute('aria-expanded', 'true');
  const buttons = [...host.querySelectorAll('[role=menuitem]')];
  buttons.forEach(button => button.onclick = () => {
    const item = items[Number(button.dataset.menuIndex)];
    closeActionMenu(documentRef);
    item?.onClick?.();
  });
  const onKey = event => {
    const i = buttons.indexOf(documentRef.activeElement);
    if (event.key === 'Escape') { closeActionMenu(documentRef); anchor.focus(); }
    else if (event.key === 'ArrowDown') { event.preventDefault(); buttons[(i + 1) % buttons.length]?.focus(); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); buttons[(i - 1 + buttons.length) % buttons.length]?.focus(); }
  };
  const onDown = event => { if (!host.contains(event.target) && event.target !== anchor && !anchor.contains(event.target)) closeActionMenu(documentRef); };
  documentRef.addEventListener('keydown', onKey);
  documentRef.addEventListener('mousedown', onDown);
  // 1.006: page scroll closes the menu, but not the scroll caused by opening it (focus / click-into-view).
  const openedAt = Date.now();
  const onScroll = event => { if (Date.now() - openedAt < 400 || host.contains(event.target)) return; closeActionMenu(documentRef); };
  globalThis.addEventListener?.('scroll', onScroll, { capture: true });
  host._cleanup = () => { documentRef.removeEventListener('keydown', onKey); documentRef.removeEventListener('mousedown', onDown); globalThis.removeEventListener?.('scroll', onScroll, { capture: true }); };
  buttons[0]?.focus?.({ preventScroll: true });
  return host;
}
