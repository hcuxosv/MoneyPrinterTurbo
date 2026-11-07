# Turbo 3D short-form explainers

Vertical (1080×1920, 30 fps) 3D explainer videos with an AI voice-over and
word-by-word "karaoke" captions. Two "stories" share one 3D turbo model:

| Story | Video | Length |
|-------|-------|--------|
| `turbo` | How a Turbo Works: exhaust → turbine → shaft → compressor → intercooler → wastegate | ~41 s |
| `lag` | Turbo lag: causes (low exhaust energy, rotating inertia), twin-scroll pulse separation, anti-lag | ~54 s |

| Step | Tool | File |
|------|------|------|
| Script + AI voice-over + caption timings | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) neural TTS (offline, voice `am_michael`) | `voiceover.py` |
| 3D scene: cut-away turbocharger, engine, intercooler, wastegate, particle air/exhaust flow, labels, HUD, captions | three.js (WebGL) | `scene.html` |
| Frame-by-frame render + encode with audio | Playwright (headless Chromium) + ffmpeg | `render.mjs` |

## Build

```bash
./build.sh            # writes ./build/how_a_turbo_works.mp4
./build.sh lag        # writes ./build/turbo_lag_twin_scroll_anti_lag.mp4
```

Requirements: Python 3 (`pip install kokoro-onnx soundfile`), Node 18+ with
`playwright` and a Chromium, and `ffmpeg`. `build.sh` downloads the Kokoro
model files (~350 MB) from GitHub releases and `three@0.170.0` from npm on
first run.

To tweak the narration, edit `SCRIPTS` in `voiceover.py`. Each line's scene id
maps to a camera shot and a per-frame state (spool speed, flows, labels, HUD,
twin-scroll, fireballs…) in the matching entry of `stories` in `scene.html`.
Caption word times are anchored to the pauses detected in the generated audio.
Preview individual frames without rendering the whole video:

```bash
node render.mjs --build build/lag --stills 2,10,25
```
