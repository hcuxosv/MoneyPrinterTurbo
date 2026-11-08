// Deterministic frame renderer: serves this folder, opens a scene page in headless
// Chromium, calls window.renderAt(t) for every frame and pipes JPEGs into ffmpeg.
//
//   node render.mjs --page cpu/scene.html --data <timings.json> --out out/cpu_raw.mp4
//   node render.mjs --page cpu/scene.html --data <timings.json> --still 40 --out still.jpg
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
// Playwright may be installed globally (require() honours NODE_PATH; ESM import does not).
const { chromium } = createRequire(import.meta.url)('playwright');

const root = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return acc;
}, []));
const W = +(args.width || 1920), H = +(args.height || 1080), FPS = +(args.fps || 30);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' };

const dataPath = args.data ? path.resolve(args.data) : null;
const server = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);
  const file = url === '/__data.json' && dataPath ? dataPath : path.join(root, url);
  if (!file.startsWith(root) && file !== dataPath) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': types[path.extname(file)] || 'application/octet-stream' });
    res.end(buf);
  });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
page.on('pageerror', e => console.error('[pageerror]', e.message));
const q = new URLSearchParams({ w: W, h: H, ...(args.query ? Object.fromEntries(new URLSearchParams(args.query)) : {}) });
await page.goto(`http://127.0.0.1:${port}/${args.page}?${q}`);
await page.waitForFunction(() => window.sceneReady === true, null, { timeout: 120000 });
const duration = await page.evaluate(() => window.sceneDuration);

const grab = async t => {
  const b64 = await page.evaluate(async tt => window.renderAt(tt), t);
  return Buffer.from(b64.split(',')[1], 'base64');
};

if (args.still !== undefined) {
  const times = String(args.still).split(',').map(Number);
  for (const [i, t] of times.entries()) {
    const out = times.length > 1 ? args.out.replace(/(\.\w+)$/, `_${String(i).padStart(2, '0')}$1`) : args.out;
    fs.writeFileSync(out, await grab(t));
    console.error('still', t, '->', out);
  }
} else {
  const start = +(args.start || 0), end = +(args.end || duration);
  const total = Math.round((end - start) * FPS);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', args.out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = 0; f < total; f++) {
    const buf = await grab(start + f / FPS);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 60 === 0) console.error(`frame ${f}/${total}  ${((Date.now() - t0) / 1000 / (f + 1)).toFixed(2)}s/frame`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
}
await browser.close();
server.close();
