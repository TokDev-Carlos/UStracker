// Serves the real Code.gs over HTTP (with the same 302 redirect dance as Apps Script) for client tests.
import http from 'node:http';
import { createGas } from './gas_mock.mjs';
let offset = 0;
const gas = createGas({ now: () => Date.now() + offset });
const secret = gas.install();
const replies = new Map();
const server = http.createServer((req, res) => {
  let chunks = [];
  req.on('data', c => chunks.push(c));
  req.on('end', () => {
    const url = new URL(req.url, 'http://x');
    if (req.method === 'POST' && url.pathname === '/exec') {
      const out = gas.post(Buffer.concat(chunks).toString('utf8'));
      const key = Math.random().toString(16).slice(2);
      replies.set(key, out);
      res.writeHead(302, { Location: `/echo?k=${key}` }); return res.end();
    }
    if (req.method === 'GET' && url.pathname === '/echo') {
      const out = replies.get(url.searchParams.get('k')); replies.delete(url.searchParams.get('k'));
      res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end(JSON.stringify(out));
    }
    if (url.pathname === '/__daily') { const r = gas.daily(); res.writeHead(200); return res.end(JSON.stringify(r)); }
    if (url.pathname === '/__clock') { offset = Number(url.searchParams.get('days')) * 86400000; res.writeHead(200); return res.end('{}'); }
    if (url.pathname === '/__files') { res.writeHead(200); return res.end(JSON.stringify(gas.liveFiles().map(f => f.name))); }
    res.writeHead(404); res.end();
  });
});
server.listen(0, '127.0.0.1', () => { process.stdout.write(JSON.stringify({ port: server.address().port, secret }) + '\n'); });
