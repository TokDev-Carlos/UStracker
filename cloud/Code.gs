/**
 * UStracker Cloud — Apps Script (Google Drive) · protocolo v1
 *
 * Cofre cifrado e versionado para o UStracker. Tudo chega JÁ CIFRADO pelo computador;
 * este script só guarda e devolve bytes. Nada aqui consegue ler os dados.
 *
 * Instalação (uma vez):
 *   1. script.google.com → Novo projeto → cole este arquivo inteiro em Code.gs → Salvar.
 *   2. Selecione a função `instalar` → Executar → autorize. O registro mostra o CÓDIGO DE CONEXÃO.
 *   3. Implantar → Nova implantação → Tipo: App da Web → Executar como: Eu → Quem pode acessar: Qualquer pessoa.
 *   4. No UStracker: Sistema › Nuvem → cole a URL do App da Web e o Código de Conexão.
 *
 * Regras:
 *   - Pontos de restauração: todos os dos últimos 14 dias + SEMPRE o mais recente (nunca expira).
 *   - Arquivos (fotos/anexos) só são apagados quando o UStracker pede (fim dos 14 dias da Lixeira).
 *   - Envio de uma instância desatualizada é recusado (CONFLICT), protegendo a nuvem.
 */
var UST_VERSION = 1;
var UST_RETENTION_DAYS = 14;
var UST_FOLDER = 'UStracker Cloud';
var UST_MAX_SKEW_MS = 10 * 60 * 1000;

/* ---------------------------------------------------------------- instalação */
function instalar() {
  var props = PropertiesService.getScriptProperties();
  var root = ust_root_();
  ['uploads', 'snapshots', 'blobs', 'auth'].forEach(function (n) { ust_child_(root, n); });
  var secret = props.getProperty('SECRET');
  if (!secret) {
    secret = ust_hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.getUuid() + Utilities.getUuid() + new Date().getTime())).slice(0, 48);
    props.setProperty('SECRET', secret);
  }
  var triggers = ScriptApp.getProjectTriggers().filter(function (t) { return t.getHandlerFunction() === 'limpezaDiaria'; });
  if (!triggers.length) ScriptApp.newTrigger('limpezaDiaria').timeBased().everyDays(1).atHour(3).create();
  Logger.log('UStracker Cloud instalado. Pasta: ' + root.getName());
  Logger.log('CÓDIGO DE CONEXÃO (guarde junto com a URL do App da Web): ' + secret);
  return secret;
}

/* ---------------------------------------------------------------- HTTP */
function doGet() {
  return ust_json_({ ok: true, service: 'UStracker Cloud', version: UST_VERSION });
}

function doPost(e) {
  try {
    var req = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    ust_verify_(req);
    var body = JSON.parse(req.body || '{}');
    var handler = UST_ACTIONS[req.action];
    if (!handler) throw ust_err_('UNKNOWN_ACTION', req.action);
    var out = handler(body);
    out.ok = true;
    return ust_json_(out);
  } catch (err) {
    return ust_json_({ ok: false, error: err.code || 'SERVER_ERROR', detail: String(err.detail !== undefined ? err.detail : (err.message || err)) });
  }
}

var UST_ACTIONS = {
  ping: function () { return { version: UST_VERSION, head: ust_head_(), auth_head: ust_prop_json_('AUTH_HEAD'), lease: ust_prop_json_('LEASE'), now: new Date().toISOString() }; },
  put_part: ust_put_part_,
  commit: ust_commit_,
  list_snapshots: ust_list_snapshots_,
  get_manifest: ust_get_manifest_,
  get_part: ust_get_part_,
  put_blob: ust_put_blob_,
  list_blobs: ust_list_blobs_,
  get_blob: ust_get_blob_,
  delete_blobs: ust_delete_blobs_,
  compact: ust_compact_,
  lease: ust_lease_
};

/* ---------------------------------------------------------------- vez de gravar (S-03)
 * Um Servidor grava por vez. acquire: concede se livre, vencido ou já é dele; renew: estende;
 * release: solta. A vez vence sozinha (ttl) se o Servidor cair. */
function ust_lease_(b) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var props = PropertiesService.getScriptProperties();
    var now = new Date().getTime();
    var cur = ust_prop_json_('LEASE');
    var holder = String(b.holder || '');
    if (!/^[0-9a-f-]{8,64}$/.test(holder)) throw ust_err_('BAD_REQUEST', 'holder');
    var free = !cur || Number(cur.expires) <= now || cur.holder === holder;
    if (b.op === 'release') {
      if (cur && cur.holder === holder) props.deleteProperty('LEASE');
      return { released: true };
    }
    if (!free) return { granted: false, holder: cur.holder, holder_name: cur.name, expires: cur.expires, now: now };
    var ttl = Math.max(15, Math.min(300, Number(b.ttl || 120))) * 1000;
    var lease = { holder: holder, name: String(b.name || 'Servidor').slice(0, 80), since: (cur && cur.holder === holder) ? cur.since : now, expires: now + ttl };
    props.setProperty('LEASE', JSON.stringify(lease));
    return { granted: true, lease: lease, head: ust_head_(), auth_head: ust_prop_json_('AUTH_HEAD'), now: now };
  } finally {
    lock.releaseLock();
  }
}

/* ---------------------------------------------------------------- segurança */
function ust_verify_(req) {
  var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
  if (!secret) throw ust_err_('NOT_INSTALLED', 'execute a função instalar');
  if (req.v !== UST_VERSION) throw ust_err_('VERSION', 'protocolo ' + req.v);
  var ts = Number(req.ts);
  if (!ts || Math.abs(new Date().getTime() - ts) > UST_MAX_SKEW_MS) throw ust_err_('CLOCK', 'relógio do computador fora de hora');
  if (!/^[0-9a-f]{32}$/.test(String(req.nonce || ''))) throw ust_err_('AUTH', 'nonce');
  var message = req.action + '\n' + req.ts + '\n' + req.nonce + '\n' + (req.body || '');
  var expected = ust_hex_(Utilities.computeHmacSha256Signature(message, secret));
  if (!ust_safe_eq_(expected, String(req.sig || ''))) throw ust_err_('AUTH', 'assinatura inválida');
  var cache = CacheService.getScriptCache();
  if (cache.get('n:' + req.nonce)) throw ust_err_('REPLAY', 'pedido repetido');
  cache.put('n:' + req.nonce, '1', 21600);
}

function ust_safe_eq_(a, b) {
  if (a.length !== b.length) return false;
  var r = 0;
  for (var i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

/* ---------------------------------------------------------------- pastas e utilidades */
function ust_root_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('FOLDER_ID');
  if (id) { try { return DriveApp.getFolderById(id); } catch (e) { /* recria abaixo */ } }
  var it = DriveApp.getFoldersByName(UST_FOLDER);
  var folder = it.hasNext() ? it.next() : DriveApp.createFolder(UST_FOLDER);
  props.setProperty('FOLDER_ID', folder.getId());
  return folder;
}
function ust_child_(parent, name) {
  var it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}
function ust_file_(folder, name) {
  var it = folder.getFilesByName(name);
  return it.hasNext() ? it.next() : null;
}
function ust_hex_(bytes) {
  return bytes.map(function (b) { var v = (b < 0 ? b + 256 : b).toString(16); return v.length === 1 ? '0' + v : v; }).join('');
}
function ust_sha_(bytes) { return ust_hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)); }
function ust_err_(code, detail) { var e = new Error(code); e.code = code; e.detail = detail; return e; }
function ust_json_(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }
function ust_name_ok_(name, re) { if (!re.test(String(name || ''))) throw ust_err_('BAD_NAME', name); return String(name); }
function ust_prop_json_(key) { var v = PropertiesService.getScriptProperties().getProperty(key); return v ? JSON.parse(v) : null; }
function ust_head_() { return ust_prop_json_('HEAD'); }
function ust_write_(folder, name, bytes) {
  var old = ust_file_(folder, name);
  if (old) ust_remove_(old);
  return folder.createFile(Utilities.newBlob(bytes, 'application/octet-stream', name));
}
/** Exclusão definitiva (API do Drive); se indisponível, vai para a lixeira do Drive. */
function ust_remove_(fileOrFolder) {
  try {
    var resp = UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + fileOrFolder.getId(), {
      method: 'delete', muteHttpExceptions: true, headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }
    });
    if (resp.getResponseCode() < 300 || resp.getResponseCode() === 404) return;
  } catch (e) { /* cai para lixeira */ }
  fileOrFolder.setTrashed(true);
}

/* ---------------------------------------------------------------- envio em partes */
function ust_put_part_(b) {
  var uploadId = ust_name_ok_(b.upload_id, /^[0-9a-f]{32}$/);
  var index = Number(b.index);
  if (!(index >= 0 && index < 10000)) throw ust_err_('BAD_PART', b.index);
  var bytes = Utilities.base64Decode(String(b.data || ''));
  if (ust_sha_(bytes) !== b.sha256) throw ust_err_('HASH', 'parte ' + index + ' corrompida no envio');
  var folder = ust_child_(ust_child_(ust_root_(), 'uploads'), uploadId);
  ust_write_(folder, ('0000' + index).slice(-4) + '.part', bytes);
  return { index: index };
}

function ust_commit_(b) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var kind = b.kind === 'auth' ? 'auth' : 'db';
    var uploadId = ust_name_ok_(b.upload_id, /^[0-9a-f]{32}$/);
    var root = ust_root_();
    var head = ust_head_();
    if (kind === 'db') {
      if (head && !b.force) {
        if (head.dataset_id !== b.dataset_id) throw ust_err_('CONFLICT', JSON.stringify({ reason: 'dataset', head: head }));
        if (Number(head.generation) !== Number(b.base_generation)) throw ust_err_('CONFLICT', JSON.stringify({ reason: 'generation', head: head }));
      }
    } else if (head && !b.force && head.dataset_id !== b.dataset_id) {
      throw ust_err_('CONFLICT', JSON.stringify({ reason: 'dataset', head: head }));
    }
    var upFolder = ust_child_(ust_child_(root, 'uploads'), uploadId);
    var parts = b.parts || [];
    if (!parts.length) throw ust_err_('NO_PARTS', uploadId);
    var stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*/, '');
    var generation = kind === 'db' ? Number(b.generation) : Math.floor(new Date().getTime() / 1000);
    var targetName = ('0000000000' + generation).slice(-10) + '-' + stamp + '-' + uploadId.slice(0, 8);
    var target = ust_child_(ust_child_(root, kind === 'db' ? 'snapshots' : 'auth'), targetName);
    parts.forEach(function (p) {
      var name = ('0000' + Number(p.index)).slice(-4) + '.part';
      var f = ust_file_(upFolder, name);
      if (!f) throw ust_err_('MISSING_PART', p.index);
      if (ust_sha_(f.getBlob().getBytes()) !== p.sha256) throw ust_err_('HASH', 'parte ' + p.index);
      f.moveTo(target);
    });
    var manifest = {
      id: targetName, kind: kind, environment: b.environment || 'production', generation: generation,
      dataset_id: b.dataset_id, station_id: b.station_id || null, created_at: new Date().toISOString(),
      client_created_at: b.created_at || null, parts: parts, total_sha256: b.total_sha256, size: Number(b.size || 0), meta: b.meta || {}
    };
    target.createFile(Utilities.newBlob(JSON.stringify(manifest), 'application/json', 'manifest.json'));
    ust_remove_(upFolder);
    var props = PropertiesService.getScriptProperties();
    var record = { id: targetName, generation: generation, dataset_id: b.dataset_id, station_id: b.station_id || null, created_at: manifest.created_at, size: manifest.size };
    props.setProperty(kind === 'db' ? 'HEAD' : 'AUTH_HEAD', JSON.stringify(record));
    return { snapshot: record };
  } finally {
    lock.releaseLock();
  }
}

/* ---------------------------------------------------------------- leitura */
function ust_kind_folder_(kind) { return ust_child_(ust_root_(), kind === 'auth' ? 'auth' : 'snapshots'); }

function ust_list_snapshots_(b) {
  var head = ust_head_();
  var out = [];
  var it = ust_kind_folder_(b.kind).getFolders();
  while (it.hasNext()) {
    var f = it.next();
    var m = ust_file_(f, 'manifest.json');
    if (!m) continue;
    var man = JSON.parse(m.getBlob().getDataAsString());
    out.push({ id: man.id, generation: man.generation, created_at: man.created_at, size: man.size, environment: man.environment,
               is_head: !!(head && head.id === man.id), meta: man.meta || {} });
  }
  out.sort(function (a, c) { return a.created_at < c.created_at ? 1 : -1; });
  return { items: out };
}

function ust_snapshot_folder_(kind, id) {
  if (!id || id === 'head') {
    var h = ust_prop_json_(kind === 'auth' ? 'AUTH_HEAD' : 'HEAD');
    if (!h) throw ust_err_('EMPTY', 'nenhum ponto de restauração');
    id = h.id;
  }
  ust_name_ok_(id, /^[0-9]{10}-[0-9TZ]+-[0-9a-f]{8}$/);
  var it = ust_kind_folder_(kind).getFoldersByName(id);
  if (!it.hasNext()) throw ust_err_('NOT_FOUND', id);
  return it.next();
}

function ust_get_manifest_(b) {
  var f = ust_snapshot_folder_(b.kind, b.id);
  return { manifest: JSON.parse(ust_file_(f, 'manifest.json').getBlob().getDataAsString()) };
}

function ust_get_part_(b) {
  var f = ust_snapshot_folder_(b.kind, b.id);
  var file = ust_file_(f, ('0000' + Number(b.index)).slice(-4) + '.part');
  if (!file) throw ust_err_('MISSING_PART', b.index);
  var bytes = file.getBlob().getBytes();
  return { data: Utilities.base64Encode(bytes), sha256: ust_sha_(bytes) };
}

/* ---------------------------------------------------------------- arquivos (fotos/anexos) */
var UST_BLOB_RE = /^[0-9A-Za-z._-]{6,120}$/;

function ust_put_blob_(b) {
  var name = ust_name_ok_(b.name, UST_BLOB_RE);
  var bytes = Utilities.base64Decode(String(b.data || ''));
  if (ust_sha_(bytes) !== b.sha256) throw ust_err_('HASH', name);
  var folder = ust_child_(ust_root_(), 'blobs');
  var existing = ust_file_(folder, name);
  if (existing && existing.getDescription() === b.sha256) return { name: name, existed: true };
  var f = ust_write_(folder, name, bytes);
  f.setDescription(b.sha256);
  return { name: name, existed: false };
}

function ust_list_blobs_() {
  var it = ust_child_(ust_root_(), 'blobs').getFiles();
  var names = [];
  while (it.hasNext()) names.push(it.next().getName());
  return { names: names };
}

function ust_get_blob_(b) {
  var name = ust_name_ok_(b.name, UST_BLOB_RE);
  var f = ust_file_(ust_child_(ust_root_(), 'blobs'), name);
  if (!f) throw ust_err_('NOT_FOUND', name);
  var bytes = f.getBlob().getBytes();
  return { data: Utilities.base64Encode(bytes), sha256: ust_sha_(bytes) };
}

/** Pedido do UStracker: a foto ficou 14 dias na Lixeira e foi apagada de vez. */
function ust_delete_blobs_(b) {
  var folder = ust_child_(ust_root_(), 'blobs');
  var removed = 0;
  (b.names || []).forEach(function (n) {
    var f = ust_file_(folder, ust_name_ok_(n, UST_BLOB_RE));
    if (f) { ust_remove_(f); removed++; }
  });
  return { removed: removed };
}

/** Pedido do UStracker após expurgo da Lixeira: pontos antigos que ainda continham o item saem já. */
function ust_compact_(b) {
  var before = String(b.before || '');
  if (!/^\d{4}-\d{2}-\d{2}T/.test(before)) throw ust_err_('BAD_DATE', before);
  return { removed: ust_expire_('db', before) + ust_expire_('auth', before) };
}

/* ---------------------------------------------------------------- limpeza */
function ust_expire_(kind, beforeIso) {
  var head = ust_prop_json_(kind === 'auth' ? 'AUTH_HEAD' : 'HEAD');
  var removed = 0;
  var it = ust_kind_folder_(kind).getFolders();
  var doomed = [];
  while (it.hasNext()) {
    var f = it.next();
    if (head && f.getName() === head.id) continue;
    var m = ust_file_(f, 'manifest.json');
    var created = m ? JSON.parse(m.getBlob().getDataAsString()).created_at : f.getDateCreated().toISOString();
    if (created < beforeIso) doomed.push(f);
  }
  doomed.forEach(function (f) { ust_remove_(f); removed++; });
  return removed;
}

function limpezaDiaria() {
  var limit = new Date(new Date().getTime() - UST_RETENTION_DAYS * 86400000).toISOString();
  var removed = ust_expire_('db', limit) + ust_expire_('auth', limit);
  var day = new Date(new Date().getTime() - 86400000);
  var it = ust_child_(ust_root_(), 'uploads').getFolders();
  var stale = [];
  while (it.hasNext()) { var f = it.next(); if (f.getDateCreated() < day) stale.push(f); }
  stale.forEach(function (f) { ust_remove_(f); });
  Logger.log('Limpeza: ' + removed + ' pontos expirados, ' + stale.length + ' envios incompletos removidos.');
  return { removed: removed, stale_uploads: stale.length };
}
