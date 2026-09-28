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

export function bindMoneyInputs(root = globalThis.document) {
  root?.querySelectorAll?.('[data-money-input]').forEach(bindMoneyInput);
}
