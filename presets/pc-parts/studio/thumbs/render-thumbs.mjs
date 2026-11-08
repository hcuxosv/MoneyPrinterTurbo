// Render one 1280x720 thumbnail per video:  node thumbs/render-thumbs.mjs <out_dir> [part ...]
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.resolve(process.argv[2] || 'out/thumbnails');
const parts = process.argv.slice(3).length ? process.argv.slice(3)
  : ['cpu', 'gpu', 'ram', 'storage', 'board', 'psu', 'cooling', 'laptop', 'battery', 'screen'];
fs.mkdirSync(out, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript' };
const server = http.createServer((req, res) => {
  const f = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(root)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, b) => { if (e) { res.writeHead(404); return res.end(); } res.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); res.end(b); });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
page.on('pageerror', e => console.error('[pageerror]', e.message));
for (const [i, p] of parts.entries()) {
  await page.goto(`http://127.0.0.1:${server.address().port}/thumbs/thumb.html?part=${p}`);
  await page.waitForFunction(() => window.thumbReady === true, null, { timeout: 60000 });
  const file = path.join(out, `${String(['cpu', 'gpu', 'ram', 'storage', 'board', 'psu', 'cooling', 'laptop', 'battery', 'screen'].indexOf(p) + 1).padStart(2, '0')}_${p}.jpg`);
  await page.screenshot({ path: file, type: 'jpeg', quality: 92 });
  console.error('thumb', file);
}
await browser.close(); server.close();
