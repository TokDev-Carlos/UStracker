// AJ-04 — presentation of logical public codes. UUIDs stay in data-* attributes and API calls only.
const esc = value => String(value ?? '')
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;').replaceAll("'", '&#39;');

const fold = value => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

// Display-only label. AJ-02 moves category normalization to the backend aggregate.
const CATEGORY_ALIASES = [
  ['Carro', ['carro', 'carros', 'automovel', 'auto', 'utilitario', 'pickup', 'picape', 'van', 'suv']],
  ['Caminhão', ['caminhao', 'caminhoes', 'carreta', 'cavalo', 'truck', 'onibus']],
  ['Embarcação', ['embarcacao', 'embarcacoes', 'barco', 'lancha', 'navio', 'jet ski', 'jetski', 'veleiro']],
  ['Aeronave', ['aeronave', 'aeronaves', 'aviao', 'helicoptero', 'drone']],
];

export function vehicleCategory(type) {
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
  const category = vehicleCategory(vehicle.type);
  const detail = vehicleDetail(vehicle);
  const original = vehicle.type && category === 'Outro' ? ` (${vehicle.type})` : '';
  const title = [vehicle.code, detail].filter(Boolean).join(' · ');
  return `<span class="ui-vehicle" title="${esc(title)}"><strong>${esc(category + original)}</strong>${codeTag(vehicle.code)}</span>`;
}

export function vehicleCells(vehicles = []) {
  return vehicles.length ? vehicles.map(vehicleCell).join(' ') : '—';
}
