import { formatBRL, parseBRLInput } from './formatters.js';

const escapeAttribute = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));

export function renderMoneyInput({ name, label, valueCents = null, required = false, placeholder = 'R$ 0,00', className = '' } = {}) {
  const value = valueCents === null || valueCents === undefined || valueCents === '' ? '' : formatBRL(Number(valueCents));
  return `<div class="field ${escapeAttribute(className)}"><label>${escapeAttribute(label || 'Valor')}</label><input data-money-input name="${escapeAttribute(name)}" type="text" inputmode="decimal" autocomplete="off" placeholder="${escapeAttribute(placeholder)}" value="${escapeAttribute(value)}"${required ? ' required' : ''}></div>`;
}

export function bindMoneyInput(input) {
  if (!input || typeof input.addEventListener !== 'function') return input;
  input.setAttribute?.('inputmode', 'decimal');
  input.addEventListener('blur', () => {
    const raw = String(input.value ?? '').trim();
    if (!raw) { input.setCustomValidity?.(''); return; }
    try {
      input.value = formatBRL(parseBRLInput(raw));
      input.setCustomValidity?.('');
      input.removeAttribute?.('aria-invalid');
    } catch (error) {
      input.setCustomValidity?.(error.message || 'Valor monetário inválido.');
      input.setAttribute?.('aria-invalid', 'true');
    }
  });
  return input;
}

// 2.4.0 — "R$ 0,00" is only a hint: a zero value is cleared when the field gets focus (nothing to erase by hand).
export function isZeroMoney(value) {
  return /^\s*(R\$\s*)?0+([.,]0*)?\s*$/.test(String(value ?? ''));
}
export function clearZeroOnFocus(event) {
  const el = event?.target;
  if (!el || el.tagName !== 'INPUT' || el.readOnly || el.disabled) return;
  if (!(el.hasAttribute?.('data-money-input') || el.getAttribute?.('inputmode') === 'decimal')) return;
  if (isZeroMoney(el.value)) { el.value = ''; if (!el.placeholder) el.placeholder = 'R$ 0,00'; }
}
globalThis.document?.addEventListener?.('focusin', clearZeroOnFocus);

export function bindMoneyInputs(root = globalThis.document) {
  root?.querySelectorAll?.('[data-money-input]').forEach(bindMoneyInput);
}
