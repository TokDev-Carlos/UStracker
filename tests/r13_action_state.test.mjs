import test from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../frontend/ui/api.js';
import { createActionRunner, runDomAction } from '../frontend/ui/action-state.js';

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

test('ação duplicada compartilha uma escrita e percorre o ciclo completo', async () => {
  const states = [];
  const pending = deferred();
  let writes = 0;
  const runner = createActionRunner({ onState: state => states.push(state.status) });
  const task = () => { writes += 1; return pending.promise; };
  const first = runner.run('save-client', task);
  const second = runner.run('save-client', task);
  assert.equal(first, second);
  assert.equal(writes, 1);
  pending.resolve({ id: 'c1' });
  assert.deepEqual(await first, { id: 'c1' });
  assert.deepEqual(states, ['LOADING', 'SUCCESS', 'IDLE']);
});

test('erro preserva a superfície, restaura controles e produz feedback', async () => {
  const notifications = [];
  const button = { disabled: false };
  const scope = { setAttribute() {}, removeAttribute() {}, querySelectorAll: () => [button] };
  const previous = { rows: ['original'] };
  let refreshes = 0;
  const result = await runDomAction({
    key: 'payment', scope,
    action: async () => { throw new Error('rede indisponível'); },
    refresh: async () => { refreshes += 1; },
    notify: item => notifications.push(item),
  });
  assert.equal(result.ok, false);
  assert.equal(refreshes, 0);
  assert.deepEqual(previous, { rows: ['original'] });
  assert.equal(button.disabled, false);
  assert.deepEqual(notifications, [{ type: 'error', message: 'rede indisponível' }]);
});

test('modo latest ignora callbacks de resposta antiga', async () => {
  const oldRequest = deferred();
  const newRequest = deferred();
  const applied = [];
  const runner = createActionRunner();
  const oldRun = runner.latest('page', () => oldRequest.promise, { onSuccess: value => applied.push(value) });
  const newRun = runner.latest('page', () => newRequest.promise, { onSuccess: value => applied.push(value) });
  newRequest.resolve('novo');
  await newRun;
  oldRequest.resolve('antigo');
  await oldRun;
  assert.deepEqual(applied, ['novo']);
});

test('cliente HTTP coalesce mutações concorrentes idênticas', async () => {
  const pending = deferred();
  let calls = 0;
  const fetchImpl = async () => { calls += 1; await pending.promise; return {
    ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ ok: true }),
  }; };
  const api = createApi({ fetchImpl, operationId: () => 'op-1', csrfState: { get: () => 'csrf' } });
  const options = { method: 'POST', body: JSON.stringify({ id: 'c1' }) };
  const first = api.request('/clients/archive', options);
  const second = api.request('/clients/archive', options);
  assert.equal(first, second);
  assert.equal(calls, 1);
  pending.resolve();
  assert.deepEqual(await first, { ok: true });
});
