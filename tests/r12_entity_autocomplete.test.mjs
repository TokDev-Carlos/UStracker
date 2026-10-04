import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createEntityAutocomplete,
  renderEntityAutocomplete,
  renderEntityAutocompleteResults,
} from '../frontend/ui/entity-autocomplete.js';


function fakeScheduler() {
  const tasks = [];
  return {
    tasks,
    schedule(callback, delay) {
      const task = { callback, delay, cancelled: false };
      tasks.push(task);
      return task;
    },
    cancel(task) { if (task) task.cancelled = true; },
    next() {
      const task = tasks.find(item => !item.cancelled && !item.started);
      if (!task) throw new Error('no scheduled task');
      task.started = true;
      return task.callback();
    },
    pending() { return tasks.filter(item => !item.cancelled && !item.started); },
  };
}

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

test('debounce de 200 ms mantém apenas a consulta incremental mais recente', async () => {
  const scheduler = fakeScheduler();
  const queries = [];
  const controller = createEntityAutocomplete({
    search: async query => { queries.push(query); return [{ id: query, display_name: query }]; },
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancel,
  });
  controller.input('C');
  controller.input('Car');
  controller.input('Carlo');
  assert.equal(scheduler.pending().length, 1);
  assert.equal(scheduler.pending()[0].delay, 200);
  await scheduler.next();
  assert.deepEqual(queries, ['Carlo']);
  assert.equal(controller.getState().items[0].display_name, 'Carlo');
});

test('resposta antiga não sobrescreve a consulta nova e erro fica no estado', async () => {
  const scheduler = fakeScheduler();
  const oldRequest = deferred();
  const newRequest = deferred();
  const failedRequest = deferred();
  const controller = createEntityAutocomplete({
    search: query => query === 'Car' ? oldRequest.promise : query === 'Carlo' ? newRequest.promise : failedRequest.promise,
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancel,
  });
  controller.input('Car');
  const oldRun = scheduler.next();
  controller.input('Carlo');
  const newRun = scheduler.next();
  newRequest.resolve([{ id: 'new', display_name: 'Carlo' }]);
  await newRun;
  oldRequest.resolve([{ id: 'old', display_name: 'Car' }]);
  await oldRun;
  assert.deepEqual(controller.getState().items.map(item => item.id), ['new']);

  controller.input('falha');
  const failure = scheduler.next();
  failedRequest.reject(new Error('rede indisponível'));
  await failure;
  assert.match(controller.getState().error, /rede indisponível/);
});

test('teclado seleciona resultado, Escape fecha e limpar restaura estado', async () => {
  const scheduler = fakeScheduler();
  const controller = createEntityAutocomplete({
    search: async () => [
      { id: 'c1', display_name: 'Cliente Um' },
      { id: 'c2', display_name: 'Cliente Dois' },
    ],
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancel,
  });
  controller.input('cliente');
  await scheduler.next();
  controller.keyDown('ArrowDown');
  controller.keyDown('ArrowDown');
  controller.keyDown('Enter');
  assert.equal(controller.getState().selected.id, 'c2');
  assert.equal(controller.getState().open, false);
  controller.input('novo');
  controller.keyDown('Escape');
  assert.equal(controller.getState().open, false);
  controller.clear();
  assert.deepEqual(controller.getState(), {
    query: '', items: [], activeIndex: -1, selected: null, loading: false, error: '', open: false,
  });
});

test('renderização é limitada e entrada vazia não materializa 1000 clientes', () => {
  const source = Array.from({ length: 1005 }, (_, index) => ({ id: `c${index}`, display_name: `Cliente ${index}` }));
  const empty = renderEntityAutocomplete({ name: 'client_id', label: 'Cliente' });
  const results = renderEntityAutocompleteResults({ items: source, open: true, activeIndex: 0 });
  assert.match(empty, /type="hidden" name="client_id"/);
  assert.equal((empty.match(/data-entity-option/g) || []).length, 0);
  assert.equal((results.match(/data-entity-option/g) || []).length, 30);
  assert.doesNotMatch(results, /Cliente 1000/);
});
