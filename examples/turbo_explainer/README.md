# How a Turbo Works — 3D short-form explainer

A ~41 s vertical (1080×1920, 30 fps) 3D explainer video with an AI voice-over
and word-by-word "karaoke" captions.

| Step | Tool | File |
|------|------|------|
| Script + AI voice-over + caption timings | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) neural TTS (offline, voice `am_michael`) | `voiceover.py` |
| 3D scene: cut-away turbocharger, engine, intercooler, wastegate, particle air/exhaust flow, labels, HUD, captions | three.js (WebGL) | `scene.html` |
| Frame-by-frame render + encode with audio | Playwright (headless Chromium) + ffmpeg | `render.mjs` |

## Build

```bash
./build.sh            # writes ./build/how_a_turbo_works.mp4
```

Requirements: Python 3 (`pip install kokoro-onnx soundfile`), Node 18+ with
`playwright` and a Chromium, and `ffmpeg`. `build.sh` downloads the Kokoro
model files (~350 MB) from GitHub releases and `three@0.170.0` from npm on
first run.

To tweak the narration, edit `SCRIPT` in `voiceover.py`; the scene ids map to
camera shots, labels and effects in `scene.html` (`shots`, `sceneLabels`).
Preview individual frames without rendering the whole video:

```bash
node render.mjs --build build --stills 2,10,25
```
