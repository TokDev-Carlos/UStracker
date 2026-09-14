const assert = require('node:assert/strict');
const path = require('node:path');

const app = { innerHTML: '' };
const dummy = {};
global.document = {
  cookie: '',
  title: '',
  documentElement: { style: { setProperty() {} } },
  querySelector(selector) {
    if (selector === '#app') return app;
    if (selector === '#dynamicFavicon') return null;
    return dummy;
  },
  createElement() { return {}; },
  head: { appendChild() {} },
};
global.window = { addEventListener() {} };
global.CSS = { escape: s => s };

let authMeCalls = 0;
const jsonResponse = (status, payload) => ({
  status,
  ok: status >= 200 && status < 300,
  headers: { get: name => name.toLowerCase() === 'content-type' ? 'application/json' : '' },
  async json() { return payload; },
  async text() { return JSON.stringify(payload); },
});

global.fetch = async (url) => {
  if (url.endsWith('/api/v1/public')) return jsonResponse(200, { brand: {}, catalog: [] });
  if (url.endsWith('/api/v1/auth/setup-status')) {
    return jsonResponse(200, { slots: 3, enrolled: 3, complete: true, admins: [] });
  }
  if (url.endsWith('/api/v1/auth/me')) {
    authMeCalls += 1;
    await new Promise(resolve => setTimeout(resolve, 0));
    return jsonResponse(401, { detail: 'ADMIN session required' });
  }
  throw new Error(`Unexpected fetch: ${url}`);
};

require(path.resolve(__dirname, '../frontend/app.js'));

(async () => {
  await new Promise(resolve => setTimeout(resolve, 50));
  try {
    assert.equal(authMeCalls, 1, `expected one auth probe, got ${authMeCalls}`);
    assert.match(app.innerHTML, /id="login"/, 'unauthenticated completed setup must render login');
    process.exit(0);
  } catch (err) {
    console.error(err.stack || err);
    process.exit(1);
  }
})();
