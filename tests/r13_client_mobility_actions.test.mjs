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

test('mobilidade usa ação compartilhada em criação, edição, upload e transferência', () => {
  for (const key of ['vehicle-create', 'fleet-create', 'transfer-create', 'transfer-complete', 'transfer-cancel', 'fleet-edit', 'fleet-photo']) {
    assert.match(mobility, new RegExp(key));
  }
  assert.ok((mobility.match(/bindActionForm/g) || []).length >= 5);
  assert.ok((mobility.match(/bindActionButton/g) || []).length >= 2);
  assert.match(mobility, /successMessage/);
  assert.match(mobility, /notify:toast/);
});
