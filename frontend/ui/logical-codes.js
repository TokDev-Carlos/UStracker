// AJ-04 — presentation of logical public codes. UUIDs stay in data-* attributes and API calls only.
import { categoryIcon } from './vehicle-breakdown.js';
const esc = value => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

const fold = value => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

// Fallback only. The backend (vehicle_types.py) is the source of truth and sends category/category_label.
const CATEGORY_ALIASES = [
  ['Carro', ['carro', 'carros', 'automovel', 'auto', 'utilitario', 'pickup', 'picape', 'van', 'suv']],
  ['Caminhão', ['caminhao', 'caminhoes', 'carreta', 'cavalo', 'truck', 'onibus']],
  ['Embarcação', ['embarcacao', 'embarcacoes', 'barco', 'lancha', 'navio', 'jet ski', 'jetski', 'veleiro']],
  ['Aeronave', ['aeronave', 'aeronaves', 'aviao', 'helicoptero', 'drone']],
];

const LABEL_TO_KEY = { 'Carro': 'CAR', 'Caminhão': 'TRUCK', 'Embarcação': 'BOAT', 'Aeronave': 'AIRCRAFT', 'Outro': 'OTHER' };

export function vehicleCategory(type, backendLabel = '') {
  if (backendLabel) return backendLabel;
  const key = fold(type);
  if (!key) return 'Outro';
  for (const [label, aliases] of CATEGORY_ALIASES) if (aliases.includes(key)) return label;
  return 'Outro';
}

export function codeTag(code) {
  return code ? `<span class="ui-code">${esc(code)}</span>` : '';
}

export function vehicleDetail(vehicle = {}) {
  const name = [vehicle.brand, vehicle.model].filter(Boolean).join(' ');
  return [name, vehicle.plate].filter(Boolean).join(' · ');
}

/** Detail/search reference: CLI-0001-V02 · Marca Modelo · Placa (plain text). */
export function vehicleRef(vehicle = {}) {
  return [vehicle.code, vehicleDetail(vehicle)].filter(Boolean).join(' · ') || 'Veículo';
}

/** Table cell whose meaning is "Veículo": category first, code small, details in tooltip. */
export function vehicleCell(vehicle = {}) {
  const category = vehicleCategory(vehicle.type, vehicle.category_label);
  const detail = vehicleDetail(vehicle);
  const original = vehicle.type && category === 'Outro' ? ` (${vehicle.type})` : '';
  const title = [vehicle.code, detail].filter(Boolean).join(' · ');
  const icon = categoryIcon(vehicle.category || LABEL_TO_KEY[category] || 'OTHER', category);
  return `<span class="ui-vehicle" title="${esc(title)}">${icon}<strong>${esc(category + original)}</strong>${codeTag(vehicle.code)}</span>`;
}

export function vehicleCells(vehicles = []) {
  return vehicles.length ? vehicles.map(vehicleCell).join(' ') : '—';
}
