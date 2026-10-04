const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));

export function closeOverlay(documentRef = globalThis.document) {
  documentRef.querySelector('#uiOverlay')?.remove();
}

export function openDrawer({ title, subtitle = '', content = '', actions = '', documentRef = globalThis.document }) {
  closeOverlay(documentRef);
  const host = documentRef.createElement('div');
  host.id = 'uiOverlay';
  host.className = 'ui-overlay';
  host.innerHTML = `<div class="ui-overlay-backdrop" data-close-overlay></div><section class="ui-drawer" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="uiDrawerTitle"><header class="ui-drawer-head"><div><h2 id="uiDrawerTitle">${escapeHtml(title)}</h2>${subtitle ? `<p class="muted">${escapeHtml(subtitle)}</p>` : ''}</div><button type="button" class="ui-icon-btn" data-close-overlay aria-label="Fechar">×</button></header><div class="ui-drawer-body">${content}</div>${actions ? `<footer class="ui-drawer-actions">${actions}</footer>` : ''}</section>`;
  documentRef.body.append(host);
  host.querySelectorAll('[data-close-overlay]').forEach(element => { element.onclick = () => closeOverlay(documentRef); });
  // AJ-15: Esc closes; focus moves into the drawer.
  host.addEventListener('keydown', event => { if (event.key === 'Escape' && !event.defaultPrevented && !documentRef.querySelector('#uiActionMenu')) closeOverlay(documentRef); });
  globalThis.setTimeout?.(() => { const first = host.querySelector('.ui-drawer-body input:not([type=hidden]):not([disabled]),.ui-drawer-body select,.ui-drawer-body button'); (first || host.querySelector('.ui-drawer'))?.focus?.({ preventScroll: true }); }, 30);
  return host;
}

export function toast({ type = 'success', message, action = null, documentRef = globalThis.document }) {
  let region = documentRef.querySelector('#uiToasts');
  if (!region) {
    region = documentRef.createElement('div');
    region.id = 'uiToasts';
    region.className = 'ui-toasts';
    region.setAttribute('aria-live', 'polite');
    documentRef.body.append(region);
  }
  const item = documentRef.createElement('div');
  item.className = `ui-toast ui-toast-${type}`;
  item.textContent = message;
  item.setAttribute('role', type === 'error' ? 'alert' : 'status');
  region.append(item);
  const leave = () => { item.classList.add('is-leaving'); globalThis.setTimeout(() => item.remove(), 220); };
  item.onclick = leave;
  if (action?.label && typeof action.onClick === 'function') {
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = 'ui-toast-action';
    button.textContent = action.label;
    button.onclick = event => { event.stopPropagation(); leave(); action.onClick(); };
    item.append(button);
  }
  globalThis.setTimeout(leave, type === 'error' ? 6000 : action ? 8000 : 3500);
  return item;
}
