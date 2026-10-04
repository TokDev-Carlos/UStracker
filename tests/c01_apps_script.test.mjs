import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { createGas, signRequest } from '../cloud/harness/gas_mock.mjs';

const sha = b => crypto.createHash('sha256').update(b).digest('hex');
function setup(clock = { t: Date.now() }) {
  const gas = createGas({ now: () => clock.t });
  const secret = gas.install();
  const call = (action, body, opts) => gas.post(signRequest(secret, action, body, { ts: clock.t, ...opts }));
  const upload = (bytes, meta) => {
    const uploadId = crypto.randomBytes(16).toString('hex');
    const parts = [];
    for (let i = 0, off = 0; off < bytes.length; i++, off += 5) {
      const chunk = bytes.subarray(off, off + 5);
      assert.equal(call('put_part', { upload_id: uploadId, index: i, data: chunk.toString('base64'), sha256: sha(chunk) }).ok, true);
      parts.push({ index: i, sha256: sha(chunk), size: chunk.length });
    }
    return call('commit', { upload_id: uploadId, parts, total_sha256: sha(bytes), size: bytes.length, ...meta });
  };
  return { gas, secret, call, upload, clock };
}

test('C-01: instalar gera código e gatilho diário; assinatura, relógio e repetição protegidos', () => {
  const { gas, secret, call, clock } = setup();
  assert.match(secret, /^[0-9a-f]{48}$/);
  assert.equal(gas.install(), secret, 'instalar de novo não troca o código');
  assert.equal(call('ping', {}).ok, true);
  assert.equal(gas.post(signRequest('outro-segredo', 'ping', {}, { ts: clock.t })).error, 'AUTH');
  assert.equal(gas.post(signRequest(secret, 'ping', {}, { ts: clock.t - 3600e3 })).error, 'CLOCK');
  const req = signRequest(secret, 'ping', {}, { ts: clock.t });
  assert.equal(gas.post(req).ok, true);
  assert.equal(gas.post(req).error, 'REPLAY');
  const tampered = { ...signRequest(secret, 'list_blobs', {}, { ts: clock.t }), body: '{"x":1}' };
  assert.equal(gas.post(tampered).error, 'AUTH');
});

test('C-01: envio em partes, versão, conflito de geração e leitura de volta', () => {
  const { call, upload } = setup();
  const data = Buffer.from('banco-cifrado-de-teste-123456789');
  const first = upload(data, { kind: 'db', dataset_id: 'D1', generation: 1, base_generation: 0, station_id: 'S1' });
  assert.equal(first.ok, true, JSON.stringify(first));
  assert.equal(call('ping', {}).head.generation, 1);
  const stale = upload(Buffer.from('outra-maquina'), { kind: 'db', dataset_id: 'D1', generation: 1, base_generation: 0 });
  assert.equal(stale.error, 'CONFLICT');
  const other = upload(Buffer.from('outro-dataset'), { kind: 'db', dataset_id: 'D2', generation: 1, base_generation: 0 });
  assert.equal(other.error, 'CONFLICT');
  assert.equal(upload(Buffer.from('segunda-versao'), { kind: 'db', dataset_id: 'D1', generation: 2, base_generation: 1 }).ok, true);
  const list = call('list_snapshots', { kind: 'db' }).items;
  assert.equal(list.length, 2);
  assert.equal(list[0].is_head, true);
  const man = call('get_manifest', { kind: 'db', id: first.snapshot.id }).manifest;
  const back = Buffer.concat(man.parts.map(p => Buffer.from(call('get_part', { kind: 'db', id: man.id, index: p.index }).data, 'base64')));
  assert.equal(back.toString(), data.toString());
  const bad = call('put_part', { upload_id: 'a'.repeat(32), index: 0, data: Buffer.from('x').toString('base64'), sha256: 'f'.repeat(64) });
  assert.equal(bad.error, 'HASH');
});

test('C-01: arquivos por nome, idempotentes; exclusão só quando o sistema pede', () => {
  const { call } = setup();
  const b = Buffer.from('foto-cifrada');
  assert.equal(call('put_blob', { name: 'abc123.webp.aead', data: b.toString('base64'), sha256: sha(b) }).existed, false);
  assert.equal(call('put_blob', { name: 'abc123.webp.aead', data: b.toString('base64'), sha256: sha(b) }).existed, true);
  assert.deepEqual(call('list_blobs', {}).names, ['abc123.webp.aead']);
  assert.equal(Buffer.from(call('get_blob', { name: 'abc123.webp.aead' }).data, 'base64').toString(), 'foto-cifrada');
  assert.equal(call('put_blob', { name: '../x', data: '', sha256: sha(Buffer.alloc(0)) }).error, 'BAD_NAME');
  assert.equal(call('delete_blobs', { names: ['abc123.webp.aead'] }).removed, 1);
  assert.deepEqual(call('list_blobs', {}).names, []);
});

test('C-01: 14 dias — pontos antigos expiram, o mais recente nunca; compactar a pedido', () => {
  const clock = { t: Date.parse('2026-10-01T12:00:00Z') };
  const { gas, call, upload } = setup(clock);
  upload(Buffer.from('v1'), { kind: 'db', dataset_id: 'D', generation: 1, base_generation: 0 });
  clock.t += 5 * 86400e3;
  upload(Buffer.from('v2'), { kind: 'db', dataset_id: 'D', generation: 2, base_generation: 1 });
  clock.t += 10 * 86400e3; // v1 has 15 days, v2 has 10
  gas.daily();
  assert.deepEqual(call('list_snapshots', { kind: 'db' }).items.map(i => i.generation), [2]);
  clock.t += 30 * 86400e3; // head is 40 days old: still kept
  gas.daily();
  assert.equal(call('list_snapshots', { kind: 'db' }).items.length, 1);
  upload(Buffer.from('v3'), { kind: 'db', dataset_id: 'D', generation: 3, base_generation: 2 });
  clock.t += 1000;
  assert.equal(call('compact', { before: new Date(clock.t).toISOString() }).removed, 1);
  assert.deepEqual(call('list_snapshots', { kind: 'db' }).items.map(i => i.generation), [3]);
});
