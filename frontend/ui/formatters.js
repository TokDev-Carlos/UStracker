const CURRENCY_PREFIX = 'R$';

const asIntegerCents = value => {
  const cents = Number(value ?? 0);
  if (!Number.isFinite(cents) || !Number.isInteger(cents)) throw new TypeError('Centavos devem ser um inteiro finito.');
  return cents;
};

export function formatBRL(cents) {
  const value = asIntegerCents(cents);
  const negative = value < 0;
  const absolute = Math.abs(value);
  const integer = Math.floor(absolute / 100).toLocaleString('pt-BR', { useGrouping: true });
  const fraction = String(absolute % 100).padStart(2, '0');
  return `${negative ? '-' : ''}${CURRENCY_PREFIX} ${integer},${fraction}`;
}

export function parseBRLInput(text) {
  let raw = String(text ?? '').trim().replace(/[\u00a0\u202f\s]/g, '');
  if (!raw) throw new TypeError('Valor monetário vazio.');
  raw = raw.replace(/^R\$/i, '').replace(/^(-)R\$/i, '$1');
  let negative = false;
  if (raw.startsWith('-')) { negative = true; raw = raw.slice(1); }
  raw = raw.replace(/^R\$/i, '');
  if (!raw) throw new TypeError('Valor monetário inválido.');
  if (!/^\d{1,3}(?:\.\d{3})*(?:,\d{0,2})?$|^\d+(?:,\d{0,2})?$/.test(raw)) {
    throw new TypeError('Valor monetário inválido; use no máximo duas casas decimais.');
  }
  const [integerPart, fractionPart = ''] = raw.split(',');
  const integer = Number(integerPart.replaceAll('.', ''));
  const fraction = Number((fractionPart + '00').slice(0, 2));
  const cents = integer * 100 + fraction;
  return negative ? -cents : cents;
}

export function formatDateBR(iso, withTime = false) {
  const raw = String(iso ?? '').trim();
  if (!raw) return '—';
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (!match) return raw;
  const [, year, month, day, hour, minute, second] = match;
  const date = `${day}/${month}/${year}`;
  if (!withTime || hour === undefined) return date;
  return `${date} - ${hour}:${minute}:${second ?? '00'}`;
}

export function normalizePlate(text) {
  return String(text ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 7);
}

export function normalizeDocument(type, text) {
  const kind = String(type ?? '').trim().toUpperCase();
  const raw = String(text ?? '').toUpperCase();
  if (kind === 'CPF' || kind === 'CNH') return raw.replace(/\D/g, '').slice(0, 11);
  if (kind === 'RG') return raw.replace(/[^A-Z0-9]/g, '');
  return raw.trim();
}
