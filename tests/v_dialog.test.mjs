import test from 'node:test';
import assert from 'node:assert/strict';
import { renderDialog, renderPlateOwner } from '../frontend/ui/dialog.js';
import { renderSubscriptionWorkflow } from '../frontend/ui/subscription-workflow.js';

test('V-05: diálogo próprio com ações e escape de HTML', () => {
  const html = renderDialog({ title: '<x>', body: '<p>ok</p>', actions: [{ label: 'Cancelar' }, { label: 'Excluir', kind: 'danger' }] });
  assert.match(html, /&lt;x&gt;/);
  assert.match(html, /ui-btn-danger" data-dialog-action="1">Excluir/);
});

test('V-02: placa já cadastrada mostra veículo, cliente e foto', () => {
  const html = renderPlateOwner({ plate: 'ABC1D23', brand: 'Fiat', model: 'Uno', client_name: 'Alfa <SA>', media_id: 'm9' });
  assert.match(html, /ABC1D23/); assert.match(html, /Alfa &lt;SA&gt;/); assert.match(html, /media\/m9\/operational/);
  assert.match(renderPlateOwner({ plate: 'X' }), /Sem foto/);
});

test('V-07: alvos da assinatura em cartões com miniatura do veículo', () => {
  const html = renderSubscriptionWorkflow({ context: 'CLIENT_PROFILE', clientId: 'c1', clients: [{ id: 'c1', legal_name: 'A' }], catalog: [],
    vehicles: [{ id: 'v1', client_id: 'c1', plate: 'AAA1A11', brand: 'VW', model: 'Gol', type: 'Carro' }], fleets: [], vehicleMedia: { v1: [{ id: 'm1' }] } });
  assert.match(html, /class="sw-target"[\s\S]*media\/m1\/thumb[\s\S]*AAA1A11/);
  assert.match(html, /plano mensal de cada veículo/);
});
