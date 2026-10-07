// H-08 (2.4.0): filtro por coluna estilo planilha (lógica pura + tabela de Clientes paginada).
import test from 'node:test';
import assert from 'node:assert/strict';
import { compareCells, distinctValues, rowPasses, narrowValues, sortableValue, EMPTY_LABEL } from '../frontend/ui/table-filters.js';
import { createTableController } from '../frontend/ui/table-controller.js';

test('ordena dinheiro, datas e texto como planilha', () => {
  assert.deepEqual(sortableValue('R$ 1.234,56'), { n: 1234.56 });
  assert.deepEqual(sortableValue('05/10/2026'), { n: 20261005 });
  const money = ['R$ 10,00', 'R$ 2,00', 'R$ 1.000,00'].sort(compareCells);
  assert.deepEqual(money, ['R$ 2,00', 'R$ 10,00', 'R$ 1.000,00']);
  assert.deepEqual(['01/02/2026', '31/01/2026'].sort(compareCells), ['31/01/2026', '01/02/2026']);
  assert.deepEqual(['b', '', 'Á'].sort(compareCells), ['Á', 'b', '']);
});

test('valores distintos com contagem, vazio e busca sem acento', () => {
  const v = distinctValues(['Ativo', 'Pausado', 'Ativo', '']);
  assert.deepEqual(v, [{ value: 'Ativo', count: 2 }, { value: 'Pausado', count: 1 }, { value: EMPTY_LABEL, count: 1 }]);
  assert.deepEqual(narrowValues(v, 'paus').map(x => x.value), ['Pausado']);
  assert.ok(rowPasses(['x', 'Ativo'], { 1: new Set(['Ativo']) }));
  assert.ok(!rowPasses(['x', ''], { 1: new Set(['Ativo']) }));
  assert.ok(rowPasses(['x', ''], { 1: new Set([EMPTY_LABEL]) }));
});

test('tabela paginada filtra por coluna em TODAS as páginas', () => {
  const rows = Array.from({ length: 45 }, (_, i) => ({ id: i, name: `C${i}`, status: i % 3 ? 'ACTIVE' : 'PAUSED' }));
  const c = createTableController({ columns: [{ key: 'name', label: 'Nome' }, { key: 'status', label: 'Situação', format: v => `<b>${v === 'ACTIVE' ? 'Ativo' : 'Pausado'}</b>` }], rows, pageSize: 20 });
  assert.deepEqual(c.columnValues('status'), [{ value: 'Ativo', count: 30 }, { value: 'Pausado', count: 15 }]);
  c.setColumnFilter('status', ['Pausado']);
  const v = c.view();
  assert.equal(v.total, 15); assert.equal(v.pageCount, 1); assert.deepEqual(v.filteredColumns, ['status']);
  c.setSort('name', false);
  assert.equal(c.view().rows[0].name, 'C42');
  c.setColumnFilter('status', null);
  assert.equal(c.view().total, 45);
});
