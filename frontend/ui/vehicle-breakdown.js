// AJ-02 — one semantic map for vehicle categories on every screen (data comes from the backend).
import { iconImg } from './icon-registry.js';

const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));

export const VEHICLE_CATEGORIES = [
  { key: 'CAR', label: 'Carros', singular: 'Carro', icon: 'vehicle.car' },
  { key: 'MOTO', label: 'Motos', singular: 'Moto', icon: 'vehicle.moto' },
  { key: 'TRUCK', label: 'Caminhões', singular: 'Caminhão', icon: 'vehicle.truck' },
  { key: 'BOAT', label: 'Embarcações', singular: 'Embarcação', icon: 'vehicle.boat' },
  { key: 'OTHER', label: 'Outros', singular: 'Outro', icon: 'vehicle.other' },
];

export function normalizeBreakdown(breakdown = {}) {
  const byKey = new Map((breakdown.categories || []).map(item => [item.key, item]));
  const categories = VEHICLE_CATEGORIES.map(base => ({ ...base, count: Number(byKey.get(base.key)?.count || 0), custom_types: byKey.get(base.key)?.custom_types || [] }));
  const total = categories.reduce((sum, item) => sum + item.count, 0);
  return { total, categories };
}

export function categoryIcon(key, alt = '') {
  const meta = VEHICLE_CATEGORIES.find(item => item.key === key) || VEHICLE_CATEGORIES[4];
  return iconImg(meta.icon, { className: 'vehicle-category-icon', alt: alt || meta.singular });
}

/** Total Geral on top; five compact groups below (icon, name, quantity under the icon). */
export function renderVehicleBreakdown(breakdown = {}, { title = 'Veículos', compact = false } = {}) {
  const data = normalizeBreakdown(breakdown);
  const groups = data.categories.map(item => {
    const tip = item.key === 'OTHER' && item.custom_types.length ? ` title="${esc('Tipos: ' + item.custom_types.join(', '))}"` : '';
    return `<li class="vehicle-breakdown-item" data-vehicle-category="${esc(item.key)}"${tip}>${categoryIcon(item.key, '')}<strong class="vehicle-breakdown-count">${item.count}</strong><span class="vehicle-breakdown-label">${esc(item.label)}</span></li>`;
  }).join('');
  return `<section class="vehicle-breakdown${compact ? ' vehicle-breakdown-compact' : ''}" aria-label="${esc(title)} por categoria">
    <div class="vehicle-breakdown-total"><span class="vehicle-breakdown-title">${esc(title)}</span><strong>${data.total}</strong><span class="muted">Total Geral</span></div>
    <ul class="vehicle-breakdown-groups">${groups}</ul></section>`;
}
