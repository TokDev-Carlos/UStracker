// H-07 (2.4.0): CNPJ como tipo de documento do cliente (empresa).
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderClientEditor } from '../frontend/pages/clients.js';
import { normalizeDocument } from '../frontend/ui/formatters.js';

test('editor oferece CNPJ e normaliza 14 dígitos', () => {
  const html = renderClientEditor({ document_type: 'CNPJ' });
  assert.match(html, /<option value="CNPJ" selected>CNPJ<\/option>/);
  assert.equal(normalizeDocument('CNPJ', '11.222.333/0001-81'), '11222333000181');
});
