import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const app = await readFile(new URL('../frontend/app.js', import.meta.url), 'utf8');
const clientStart = app.indexOf('async function openClientProfile');
const mobilityStart = app.indexOf('async function mobilityPage');
const catalogStart = app.indexOf('async function catalogPage');
const clientProfile = app.slice(clientStart, app.indexOf('async function show', clientStart));
const clientsPage = app.slice(app.indexOf('async function clientsPage'), mobilityStart);
const mobility = app.slice(mobilityStart, catalogStart);

test('ficha e cadastro de cliente usam ação compartilhada com refresh explícito', () => {
  assert.match(app, /bindActionForm/);
  for (const variable of ['basics', 'companyForm', 'photoForm', 'signatureForm']) {
    assert.match(clientProfile, new RegExp(`bindActionForm\\(${variable}`));
  }
  assert.match(clientProfile, /refresh/);
  assert.match(clientsPage, /client-create/);
  assert.match(clientsPage, /client-archive/);
  assert.match(clientsPage, /runDomAction|bindActionButton/);
});

test('mobilidade usa ação compartilhada em criação, edição, upload e movimentação', () => {
  assert.match(app, /vehicle-move:/); // AJ-08: one simple move replaces pending transfer cases
  for (const key of ['vehicle-create', 'fleet-create', 'fleet-edit']) {
    assert.match(mobility, new RegExp(key));
  }
  assert.ok((mobility.match(/bindActionForm/g) || []).length >= 3); // fleet photo form replaced by the shared R14 handler
  // AJ-08: the move dialog is shared by Mobilidade, Ficha da Frota and Ficha do Cliente.
  assert.match(app, /function openMoveVehicle[\s\S]{0,2500}bindActionForm\(form,\{key:`vehicle-move:/);
  assert.match(mobility, /successMessage/);
  assert.match(mobility, /notify:toast/);
  // R14: photo upload/removal moved to one shared, delegated single-action handler.
  assert.match(app, /dataset\?\.fleetPhoto[\s\S]{0,400}runDomAction/);
  // V-05: "×" remove at once (photo goes to the 14-day Lixeira, toast offers Desfazer) — no browser confirm()
  assert.match(app, /data-remove-photo[\s\S]{0,400}undoToast\(/);
  assert.doesNotMatch(app, /[^.\w]confirm\(/);
});
