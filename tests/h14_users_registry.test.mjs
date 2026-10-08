// H-14 (2.5.0): cadastro global de usuários no Apps Script — chave única por login, criação atômica,
// revisão (conflito), excluído fica reservado, leitura incremental.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createGas, signRequest } from '../cloud/harness/gas_mock.mjs';

function setup() {
  const clock = { t: Date.now() };
  const gas = createGas({ now: () => clock.t });
  const secret = gas.install();
  const call = (action, body) => gas.post(signRequest(secret, action, { epoch: 25, ...body }, { ts: clock.t }));
  call('reset_company', { epoch: 25 });
  return { call };
}
const K = c => c.repeat(64);

test('criar, recusar repetido, atualizar com revisão e ler incremental', () => {
  const { call } = setup();
  const a = call('user_put', { key: K('a'), record: 'cifrado-1', expected_rev: 0 });
  assert.equal(a.ok, true); assert.equal(a.rev, 1);
  assert.equal(call('user_put', { key: K('a'), record: 'outro', expected_rev: 0 }).error, 'LOGIN_EXISTS');
  assert.equal(call('user_put', { key: K('a'), record: 'cifrado-2', expected_rev: 5 }).error, 'CONFLICT');
  const b = call('user_put', { key: K('b'), record: 'cifrado-b', expected_rev: 0 });
  assert.equal(b.rev, 2);
  const upd = call('user_put', { key: K('a'), record: 'cifrado-1b', expected_rev: 1 });
  assert.equal(upd.rev, 3);
  const all = call('users_get', { since: 0 });
  assert.equal(all.rev, 3);
  assert.deepEqual(all.items.map(i => [i.key[0], i.rev, i.record]).sort(), [['a', 3, 'cifrado-1b'], ['b', 2, 'cifrado-b']]);
  assert.deepEqual(call('users_get', { since: 2 }).items.map(i => i.key[0]), ['a']);
});

test('excluído fica reservado (não volta a ser criado) e chave inválida é recusada', () => {
  const { call } = setup();
  call('user_put', { key: K('c'), record: 'x', expected_rev: 0 });
  const del = call('user_put', { key: K('c'), record: 'x', expected_rev: 1, deleted: true });
  assert.equal(del.ok, true);
  assert.equal(call('users_get', { since: 0 }).items[0].deleted, true);
  assert.equal(call('user_put', { key: K('c'), record: 'novo', expected_rev: 0 }).error, 'LOGIN_EXISTS');
  assert.equal(call('user_put', { key: 'curta', record: 'x', expected_rev: 0 }).error, 'BAD_NAME');
});

test('cadastro sem a época certa é recusado', () => {
  const { call } = setup();
  assert.equal(call('user_put', { key: K('d'), record: 'x', expected_rev: 0, epoch: 1 }).error, 'EPOCH');
});
