// H-13 (2.5.0): empresa começa limpa — reset_company move tudo para a lixeira da nuvem, grava a época
// e a partir daí só aceita gravações da época certa (versões antigas não sobem dados velhos).
import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { createGas, signRequest } from '../cloud/harness/gas_mock.mjs';

const sha = b => crypto.createHash('sha256').update(b).digest('hex');
function setup() {
  const clock = { t: Date.now() };
  const gas = createGas({ now: () => clock.t });
  const secret = gas.install();
  const call = (action, body) => gas.post(signRequest(secret, action, body, { ts: clock.t }));
  const upload = (bytes, meta) => {
    const uploadId = crypto.randomBytes(16).toString('hex');
    assert.equal(call('put_part', { upload_id: uploadId, index: 0, data: bytes.toString('base64'), sha256: sha(bytes), ...(meta.epoch ? { epoch: meta.epoch } : {}) }).ok, true);
    return call('commit', { upload_id: uploadId, parts: [{ index: 0, sha256: sha(bytes) }], total_sha256: sha(bytes), size: bytes.length, ...meta });
  };
  return { gas, call, upload };
}

test('reset_company: tudo para _lixeira, época 25, uma vez só', () => {
  const { gas, call, upload } = setup();
  assert.equal(call('ping', {}).epoch, 0);
  assert.equal(upload(Buffer.from('dados-antigos-2.2'), { kind: 'db', generation: 1, base_generation: 0, dataset_id: 'velho' }).ok, true);
  assert.equal(call('put_blob', { name: 'foto-antiga.webp', data: Buffer.from('x').toString('base64'), sha256: sha(Buffer.from('x')) }).ok, true);
  const out = call('reset_company', { epoch: 25 });
  assert.equal(out.ok, true);
  assert.ok(out.moved >= 2, 'snapshots e blobs foram para a lixeira');
  const ping = call('ping', {});
  assert.equal(ping.epoch, 25); assert.equal(ping.head, null); assert.equal(ping.auth_head, null);
  assert.deepEqual(call('list_blobs', {}).names, []);
  const names = gas.liveFiles().map(f => f.name);
  assert.ok(names.includes('foto-antiga.webp'), 'nada apagado: está na _lixeira');
  assert.equal(call('reset_company', { epoch: 25 }).error, 'EPOCH', 'não zera duas vezes');
});

test('depois do reset: gravação sem a época certa é recusada (versões antigas)', () => {
  const { call, upload } = setup();
  call('reset_company', { epoch: 25 });
  assert.equal(upload(Buffer.from('velho'), { kind: 'db', generation: 1, base_generation: 0, dataset_id: 'velho' }).error, 'EPOCH');
  assert.equal(call('put_blob', { name: 'foto-velha.webp', data: Buffer.from('y').toString('base64'), sha256: sha(Buffer.from('y')) }).error, 'EPOCH');
  assert.equal(upload(Buffer.from('novo'), { kind: 'db', generation: 1, base_generation: 0, dataset_id: 'novo', epoch: 25 }).ok, true);
  assert.equal(call('put_blob', { name: 'foto-nova.webp', data: Buffer.from('z').toString('base64'), sha256: sha(Buffer.from('z')), epoch: 25 }).ok, true);
});
