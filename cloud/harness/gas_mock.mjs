// Test harness: runs the real cloud/Code.gs inside Node with in-memory Google services.
// Used only by the developer test-suite; never shipped to users.
import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';

const signed = buf => Array.from(buf, b => (b > 127 ? b - 256 : b));
const toBuf = bytes => Buffer.from(bytes.map(b => (b < 0 ? b + 256 : b)));

export function createGas({ now = () => Date.now() } = {}) {
  let seq = 0;
  const id = () => 'id' + (++seq);
  const items = new Map(); // id -> node
  const mkIter = list => { let i = 0; return { hasNext: () => i < list.length, next: () => list[i++] }; };
  function mkFolder(name, parent) {
    const node = { kind: 'folder', id: id(), name, parent, trashed: false, created: new Date(now()) };
    items.set(node.id, node);
    return wrapFolder(node);
  }
  const children = node => [...items.values()].filter(x => x.parent === node.id && !x.trashed && !ancestorTrashed(x));
  const ancestorTrashed = x => { let p = x.parent && items.get(x.parent); while (p) { if (p.trashed) return true; p = p.parent && items.get(p.parent); } return false; };
  function wrapFolder(node) {
    return {
      getId: () => node.id, getName: () => node.name, getDateCreated: () => node.created,
      getFoldersByName: n => mkIter(children(node).filter(x => x.kind === 'folder' && x.name === n).map(wrapFolder)),
      getFilesByName: n => mkIter(children(node).filter(x => x.kind === 'file' && x.name === n).map(wrapFile)),
      getFolders: () => mkIter(children(node).filter(x => x.kind === 'folder').map(wrapFolder)),
      getFiles: () => mkIter(children(node).filter(x => x.kind === 'file').map(wrapFile)),
      createFolder: n => mkFolder(n, node.id),
      createFile: blob => { const f = { kind: 'file', id: id(), name: blob.getName(), parent: node.id, data: Buffer.from(blob._bytes), description: null, trashed: false, created: new Date(now()) }; items.set(f.id, f); return wrapFile(f); },
      setTrashed: v => { node.trashed = !!v; },
      moveTo: folder => { node.parent = folder.getId(); },
      _node: node,
    };
  }
  function wrapFile(node) {
    return {
      getId: () => node.id, getName: () => node.name, getDateCreated: () => node.created,
      getBlob: () => ({ getBytes: () => signed(node.data), getDataAsString: () => node.data.toString('utf8') }),
      getDescription: () => node.description, setDescription: d => { node.description = d; },
      moveTo: folder => { node.parent = folder.getId(); },
      setTrashed: v => { node.trashed = !!v; },
      _node: node,
    };
  }
  const rootDrive = { kind: 'folder', id: 'root', name: 'Meu Drive', parent: null, trashed: false, created: new Date(now()) };
  items.set('root', rootDrive);
  const props = new Map(); const cache = new Map(); const triggers = [];
  const ctx = {
    Logger: { log: m => ctx.__log.push(String(m)) }, __log: [],
    Utilities: {
      DigestAlgorithm: { SHA_256: 'sha256' },
      computeDigest: (alg, v) => signed(crypto.createHash('sha256').update(Array.isArray(v) ? toBuf(v) : Buffer.from(String(v), 'utf8')).digest()),
      computeHmacSha256Signature: (v, k) => signed(crypto.createHmac('sha256', Buffer.from(k, 'utf8')).update(Buffer.from(v, 'utf8')).digest()),
      base64Decode: s => signed(Buffer.from(s, 'base64')),
      base64Encode: bytes => toBuf(bytes).toString('base64'),
      newBlob: (bytes, mime, name) => ({ _bytes: typeof bytes === 'string' ? Buffer.from(bytes, 'utf8') : toBuf(bytes), getName: () => name }),
      getUuid: () => crypto.randomUUID(),
    },
    DriveApp: {
      getFolderById: fid => { const n = items.get(fid); if (!n || n.trashed || n.kind !== 'folder') throw new Error('not found'); return wrapFolder(n); },
      getFoldersByName: n => mkIter(children(rootDrive).filter(x => x.kind === 'folder' && x.name === n).map(wrapFolder)),
      createFolder: n => mkFolder(n, 'root'),
    },
    PropertiesService: { getScriptProperties: () => ({ getProperty: k => (props.has(k) ? props.get(k) : null), setProperty: (k, v) => props.set(k, String(v)), deleteProperty: k => props.delete(k) }) },
    CacheService: { getScriptCache: () => ({ get: k => cache.get(k) ?? null, put: (k, v) => cache.set(k, v) }) },
    LockService: { getScriptLock: () => ({ waitLock: () => {}, releaseLock: () => {} }) },
    ContentService: { MimeType: { JSON: 'json' }, createTextOutput: t => ({ _text: t, setMimeType() { return this; } }) },
    UrlFetchApp: { fetch: (url, opt) => { const fid = url.split('/').pop(); const n = items.get(fid); if (n) { items.delete(fid); for (const [k, v] of items) if (isDesc(v, fid)) items.delete(k); } return { getResponseCode: () => 204 }; } },
    ScriptApp: {
      getOAuthToken: () => 'token', getProjectTriggers: () => triggers.map(t => ({ getHandlerFunction: () => t })),
      newTrigger: fn => ({ timeBased: () => ({ everyDays: () => ({ atHour: () => ({ create: () => triggers.push(fn) }) }) }) }),
    },
    Date: class extends Date { constructor(...a) { super(...(a.length ? a : [now()])); } static now() { return now(); } },
    JSON, Math, Number, String, Array, Error, Object,
  };
  const isDesc = (node, ancestorId) => { let p = node.parent; while (p) { if (p === ancestorId) return true; p = items.get(p)?.parent; } return false; };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(new URL('../Code.gs', import.meta.url), 'utf8'), ctx, { filename: 'Code.gs' });
  return {
    ctx, props, items,
    install: () => ctx.instalar(),
    post: payload => JSON.parse(ctx.doPost({ postData: { contents: typeof payload === 'string' ? payload : JSON.stringify(payload) } })._text),
    daily: () => ctx.limpezaDiaria(),
    liveFiles: () => [...items.values()].filter(x => x.kind === 'file' && !x.trashed && !ancestorTrashed(x)),
  };
}

export function signRequest(secret, action, body, { ts = Date.now(), nonce = crypto.randomBytes(16).toString('hex') } = {}) {
  const b = JSON.stringify(body);
  const sig = crypto.createHmac('sha256', Buffer.from(secret, 'utf8')).update(`${action}\n${ts}\n${nonce}\n${b}`).digest('hex');
  return { v: 1, action, ts, nonce, body: b, sig };
}
