// Shared helpers for the 3D explainer scenes (three.js, deterministic, time-driven).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const smooth = x => { x = clamp(x); return x * x * (3 - 2 * x); };
export const ease = x => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
export const easeOut = x => 1 - Math.pow(1 - clamp(x), 3);
export const seg = (t, a, b, f = ease) => f((t - a) / Math.max(b - a, 1e-6));
export const lerp = (a, b, u) => a + (b - a) * u;
export const hash = (i, n = 0) => { const s = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453; return s - Math.floor(s); };
/** Fade in over [a, a+fi], hold, fade out over [b-fo, b]. */
export const window01 = (t, a, b, fi = 0.35, fo = 0.35) => Math.min(seg(t, a, a + fi, smooth), 1 - seg(t, b - fo, b, smooth));

export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export function canvasTexture(w, h, draw, { srgb = true, aniso = 8 } = {}) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const tex = new THREE.CanvasTexture(c);
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = aniso;
  return tex;
}

/** Timeline lookups over timings.json produced by tts.py. */
export function timeline(data) {
  const byId = Object.fromEntries(data.scenes.map(s => [s.id, s]));
  return {
    S: id => byId[id],
    L: (id, i) => byId[id].lines[i],
    duration: data.duration,
  };
}

/** Camera path through keyframes {t, p:[x,y,z], l:[x,y,z], fov}. Catmull-Rom with eased timing. */
export class CamPath {
  constructor(keys) { this.k = keys.slice().sort((a, b) => a.t - b.t); }
  at(t) {
    const k = this.k;
    if (t <= k[0].t) return { p: k[0].p, l: k[0].l, fov: k[0].fov };
    if (t >= k[k.length - 1].t) { const z = k[k.length - 1]; return { p: z.p, l: z.l, fov: z.fov }; }
    let i = 0; while (k[i + 1].t < t) i++;
    const a = k[i], b = k[i + 1];
    let u = (t - a.t) / (b.t - a.t);
    u = b.linear ? u : 0.35 * u + 0.65 * ease(u);
    const k0 = k[Math.max(i - 1, 0)], k3 = k[Math.min(i + 2, k.length - 1)];
    const cr = (key) => {
      const P0 = k0[key], P1 = a[key], P2 = b[key], P3 = k3[key];
      if (P1.every((v, j) => Math.abs(v - P2[j]) < 1e-6)) return P1.slice();
      const u2 = u * u, u3 = u2 * u;
      return P1.map((_, j) => 0.5 * ((2 * P1[j]) + (-P0[j] + P2[j]) * u + (2 * P0[j] - 5 * P1[j] + 4 * P2[j] - P3[j]) * u2 + (-P0[j] + 3 * P1[j] - 3 * P2[j] + P3[j]) * u3));
    };
    return { p: cr('p'), l: cr('l'), fov: lerp(a.fov, b.fov, ease((t - a.t) / (b.t - a.t))) };
  }
}

/** Text drawn to a canvas, shown as a sprite (world) or HUD element. */
export function textSprite(lines, { height = 1, align = 'center', accent = '#38e1ff', pill = true, anchor = [0.5, 0.5] } = {}) {
  // lines: [{text, size, weight, color, font, spacing}]
  const pad = 40, scale = 2;
  const meas = document.createElement('canvas').getContext('2d');
  const fontOf = l => `${l.weight || 800} ${l.size * scale}px "${l.font || 'Inter Display'}"`;
  let w = 0, h = pad * 2;
  for (const l of lines) {
    meas.font = fontOf(l);
    if ('letterSpacing' in meas) meas.letterSpacing = `${(l.spacing || 0) * scale}px`;
    w = Math.max(w, meas.measureText(l.text).width); h += l.size * scale * 1.18;
  }
  const accentW = pill && accent && align === 'left' ? 14 * scale : 0;
  w = Math.ceil(w + pad * 2 + accentW); h = Math.ceil(h);
  const tex = canvasTexture(w, h, (g) => {
    if (pill) {
      g.fillStyle = 'rgba(6,10,16,0.62)';
      const r = 18 * scale; g.beginPath(); g.roundRect(0, 0, w, h, r); g.fill();
      g.strokeStyle = 'rgba(120,220,255,0.35)'; g.lineWidth = 2 * scale; g.stroke();
      if (accentW) { g.fillStyle = accent; g.fillRect(pad * 0.6, pad, 6 * scale, h - pad * 2); }
    }
    let y = pad;
    for (const l of lines) {
      g.font = fontOf(l);
      if ('letterSpacing' in g) g.letterSpacing = `${(l.spacing || 0) * scale}px`;
      g.fillStyle = l.color || '#e6ebef'; g.textBaseline = 'top';
      g.shadowColor = pill ? 'transparent' : 'rgba(0,0,0,0.75)'; g.shadowBlur = pill ? 0 : 18 * scale;
      const x = align === 'left' ? pad + accentW : (w - g.measureText(l.text).width) / 2;
      g.fillText(l.text, x, y + l.size * scale * 0.08); y += l.size * scale * 1.18;
    }
  });
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false, toneMapped: false });
  const s = new THREE.Sprite(mat);
  s.center.set(anchor[0], anchor[1]);
  s.scale.set(height * w / h, height, 1);
  s.renderOrder = 999;
  s.userData.aspect = w / h;
  return s;
}

export function makeRenderer(W, H) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  document.body.appendChild(renderer.domElement);
  return renderer;
}

export function envMap(renderer) {
  const pm = new THREE.PMREMGenerator(renderer);
  return pm.fromScene(new RoomEnvironment(renderer), 0.04).texture;
}

const FinishShader = {
  uniforms: { tDiffuse: { value: null }, flash: { value: 0 }, fade: { value: 0 }, vig: { value: 0.9 }, time: { value: 0 } },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float flash, fade, vig, time; varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + time*7.0) * 43758.5453); }
    void main(){
      vec4 c = texture2D(tDiffuse, vUv);
      vec2 d = vUv - 0.5; d.x *= 1.25;
      float v = smoothstep(0.95, 0.25, length(d) * vig);
      c.rgb *= mix(0.55, 1.0, v);
      c.rgb += (h(vUv * 1000.0) - 0.5) * 0.018;
      c.rgb = mix(c.rgb, vec3(1.0), flash);
      c.rgb *= (1.0 - fade);
      gl_FragColor = c;
    }`,
};

/** Bloom + tone mapping + vignette/grain/flash/fade, plus an orthographic HUD layer on top. */
export function makePipeline(renderer, W, H) {
  const composer = new EffectComposer(renderer);
  const renderPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
  const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.55, 0.5, 0.88);
  const finish = new ShaderPass(FinishShader);
  composer.addPass(renderPass); composer.addPass(bloom); composer.addPass(new OutputPass()); composer.addPass(finish);
  const hud = new THREE.Scene();
  const hudCam = new THREE.OrthographicCamera(0, W, H, 0, -10, 10);
  return {
    composer, renderPass, bloom, finish, hud, hudCam,
    render(scene, camera, { flash = 0, fade = 0, time = 0 } = {}) {
      renderPass.scene = scene; renderPass.camera = camera;
      finish.uniforms.flash.value = flash; finish.uniforms.fade.value = fade; finish.uniforms.time.value = time;
      renderer.autoClear = true;
      composer.render();
      renderer.autoClear = false;
      renderer.render(hud, hudCam);
      renderer.autoClear = true;
    },
  };
}

/** Place a HUD sprite in pixel coordinates (origin bottom-left) with height in px. */
export function hudPlace(sprite, x, y, hPx) {
  sprite.position.set(x, y, 0);
  sprite.scale.set(hPx * sprite.userData.aspect, hPx, 1);
}

export async function loadFonts() {
  await Promise.all(['800 40px "Inter Display"', '900 40px "Inter Display"', '600 40px "Inter Display"', '700 40px "JetBrains Mono"']
    .map(f => document.fonts.load(f).catch(() => null)));
}
