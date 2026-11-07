// Render scene.html frame-by-frame in headless Chromium and encode with ffmpeg.
//
//   node render.mjs --build <dir with voice.wav + timeline.json> --out turbo.mp4 [--fps 30]
//   node render.mjs --build <dir> --stills 2,8,15     (preview PNGs only)
//
// <build>/node_modules/three must exist (npm i three@0.170.0 in that dir).
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = path.dirname(fileURLToPath(import.meta.url));

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) =>
  (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]]) : a), []));
const build = path.resolve(args.build);
const fps = Number(args.fps || 30);

// static server: scene.html from this folder, everything else from build dir
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);
  const file = url === '/' || url === '/scene.html' ? path.join(here, 'scene.html') : path.join(build, url);
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'content-type': types[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
page.on('console', m => { if (m.type() === 'error') console.error('[page]', m.text()); });
page.on('pageerror', e => console.error('[pageerror]', e.message));
await page.goto(`http://127.0.0.1:${port}/scene.html`);
await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
await page.evaluate(() => document.fonts.ready);
const duration = await page.evaluate(() => window.duration);

if (args.stills) {
  const times = String(args.stills).split(',').map(Number);
  // walk time forward so time-integrated state (rotor angle) is sensible
  for (const t of times) {
    await page.evaluate(t => { window.renderAt(Math.max(0, t - 0.1)); window.renderAt(t); }, t);
    const f = path.join(build, `still_${t.toFixed(1)}.png`);
    await page.screenshot({ path: f });
    console.log('wrote', f);
  }
} else {
  const out = path.resolve(args.out || path.join(build, 'turbo.mp4'));
  const nFrames = Math.ceil(duration * fps);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-i', path.join(build, 'voice.wav'),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', String(fps),
    '-c:a', 'aac', '-b:a', '192k', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
    '-movflags', '+faststart', '-shortest', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let i = 0; i < nFrames; i++) {
    await page.evaluate(t => window.renderAt(t), i / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 60 === 0) {
      const el = (Date.now() - t0) / 1000;
      console.log(`frame ${i}/${nFrames}  ${el.toFixed(0)}s elapsed, eta ${((nFrames - i) * el / Math.max(1, i)).toFixed(0)}s`);
    }
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.log('wrote', out);
}
await browser.close();
server.close();
