// U-05 — the screen shows only what the user's package allows. The server enforces the same rules;
// hiding here just keeps the screen clean (no button that would answer "sem permissão").
let current = { admin: true, perms: new Set() };

export const NAV_PERMISSION = {
  dashboard: ['dashboard.view'], clients: ['clients.view'], mobility: ['mobility.view'], catalog: ['catalog.view'],
  commercial: ['commercial.view'], finance: ['finance.view', 'expenses.view', 'fiscal.view'], files: ['files.view'],
  reports: ['reports.view'], system: ['system', 'trash.view', 'users.manage'],
};

// selector → permission(s) needed for the element to be shown
export const ELEMENT_PERMISSION = [
  ['#newClient, [data-cp-edit], [data-cp-toggle="clientCompanyForm"], [data-cp-toggle="clientVehicleForm"], [data-cp-toggle="clientFleetForm"], [data-journey="mobility"], #clientPhotoForm label, #clientPhotoForm .cp-photo-remove', ['clients.edit']],
  ['#archiveClients, [data-select]', ['clients.delete']],
  ['[data-cp-toggle="clientPurchaseForm"], [data-journey="purchase"], [data-client-new-subscription], [data-journey-subscription], [data-new-subscription], #commercialPurchaseForm', ['commercial.edit']],
  ['[data-client-payment], [data-open-payment]', ['finance.pay']],
  ['[data-reverse-payment]', ['finance.reverse']],
  ['#newVehicle, #newFleet, [data-open-vehicle-transfer], [data-add-vehicle-fleet], #fleetEditForm button, .cp-vehicle-photo input, .cp-vehicle-remove, label:has(> [data-fleet-photo])', ['mobility.edit']],
  ['[data-delete-vehicle], [data-delete-fleet]', ['mobility.delete']],
  ['#catalogForm, details:has(> #catalogForm), [data-catalog-edit]', ['catalog.edit']],
  ['[data-catalog-delete], [data-catalog-archive], [data-catalog-restore]', ['catalog.delete']],
  ['[data-finance-tab="payments"]', ['finance.view']],
  ['[data-finance-tab="expenses"]', ['expenses.view']],
  ['[data-finance-tab="fiscal"]', ['fiscal.view']],
  ['[data-expense-pay], [data-expense-sell], [data-expense-stop], #financeExpenseForm, details:has(> #financeExpenseForm)', ['expenses.edit']],
  ['[data-expense-delete]', ['expenses.delete']],
  ['#financeFiscalForm', ['fiscal.edit']],
  ['#financePaymentForm, details:has(> #financePaymentForm), #coverageForm', ['finance.pay']],
  ['[data-remove-media]', ['files.delete']],
  ['#clientSignatureForm, #attachmentUploadForm, #attachmentLinkForm, #mediaForm', ['files.edit', 'clients.edit']],
  ['[data-trash-restore]', ['trash.restore']],
  ['[data-cp-export]', ['system']],
  ['[data-overview-drilldown]', ['dashboard.full']],
];

export function setAccess(me = {}) {
  const admin = !me || me.kind !== 'user';
  current = { admin, perms: new Set(me?.permissions || []) };
  globalThis.document?.documentElement?.setAttribute('data-access', admin ? 'admin' : 'user');
}

export function can(...needs) {
  if (current.admin) return true;
  return needs.flat().some(p => current.perms.has(p));
}

export const isAdmin = () => current.admin;

export function allowedPages(pages) {
  return pages.filter(page => can(NAV_PERMISSION[page] || ['system']));
}

export function applyPermissions(root = globalThis.document) {
  if (!root?.querySelectorAll || current.admin) return;
  for (const [selector, needs] of ELEMENT_PERMISSION) {
    if (can(needs)) continue;
    let found;
    try { found = root.querySelectorAll(selector); } catch { continue; }
    found.forEach(element => { element.hidden = true; element.setAttribute('data-perm-hidden', ''); });
  }
}

let observer = null;
export function watchPermissions(documentRef = globalThis.document) {
  if (observer || !documentRef?.body || typeof MutationObserver === 'undefined') return;
  let pending = false;
  observer = new MutationObserver(() => {
    if (pending) return;
    pending = true;
    queueMicrotask(() => { pending = false; applyPermissions(documentRef); });
  });
  observer.observe(documentRef.body, { childList: true, subtree: true });
}

/** Action-menu items (Comercial › Ações) by permission. */
export const MENU_PERMISSION = { pay: 'finance.pay', amend: 'commercial.edit', purchase: 'commercial.edit', pause: 'commercial.edit', resume: 'commercial.edit', cancel: 'commercial.delete' };
export function filterMenu(items = []) {
  return items.map(item => (item.key && MENU_PERMISSION[item.key] && !can(MENU_PERMISSION[item.key]) ? { ...item, hidden: true } : item));
}
