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

const jsonResponse = (status, payload) => ({
  status,
  ok: status >= 200 && status < 300,
  headers: { get: name => name.toLowerCase() === 'content-type' ? 'application/json' : '' },
  async json() { return payload; },
  async text() { return JSON.stringify(payload); },
});

global.fetch = async (url) => {
  if (url.endsWith('/api/v1/public')) return jsonResponse(200, { brand: {}, catalog: [] });
  if (url.endsWith('/api/v1/auth/setup-status')) return jsonResponse(200, { slots: 3, enrolled: 3, complete: true, admins: [] });
  if (url.endsWith('/api/v1/auth/me')) return jsonResponse(500, { detail: 'backend exploded' });
  throw new Error(`Unexpected fetch: ${url}`);
};

require(path.resolve(__dirname, '../frontend/app.js'));

(async () => {
  await new Promise(resolve => setTimeout(resolve, 30));
  try {
    assert.doesNotMatch(app.innerHTML, /id="login"/, 'backend failure must not be disguised as login');
    assert.match(app.innerHTML, /backend exploded/, 'backend failure must be visible');
    process.exit(0);
  } catch (err) {
    console.error(err.stack || err);
    process.exit(1);
  }
})();
