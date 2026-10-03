// AJ-15 — pleasant, immediate feedback on every click without changing business behaviour.
const RIPPLE_TARGETS = '.ui-btn, .sidebar nav button, .tabs button, .cp-tabs button, .mobility-tab, .action-menu-item';

export function installInteractions(documentRef = globalThis.document) {
  if (!documentRef || documentRef.__usInteractions) return;
  documentRef.__usInteractions = true;
  const reduced = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  documentRef.addEventListener('pointerdown', event => {
    if (reduced || event.button !== 0) return;
    const target = event.target.closest?.(RIPPLE_TARGETS);
    if (!target || target.disabled) return;
    const rect = target.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const ripple = documentRef.createElement('span');
    ripple.className = 'us-ripple';
    ripple.style.width = ripple.style.height = `${size}px`;
    ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
    ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
    target.append(ripple);
    globalThis.setTimeout(() => ripple.remove(), 520);
  }, { passive: true });
}

/** Thin progress bar while a page loads. */
export function navigationStarted(documentRef = globalThis.document) { documentRef.body?.classList.add('is-navigating'); }
export function navigationFinished(documentRef = globalThis.document) { documentRef.body?.classList.remove('is-navigating'); }
