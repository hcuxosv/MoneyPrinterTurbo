# Turbo 3D short-form explainers

Vertical (1080×1920, 30 fps) 3D explainer videos with an AI voice-over and
word-by-word "karaoke" captions. Five "stories" share one 3D scene:

| Story | Video | Length |
|-------|-------|--------|
| `turbo` | How a Turbo Works: exhaust → turbine → shaft → compressor → intercooler → wastegate | ~63 s |
| `lag` | Turbo lag: causes (low exhaust energy, rotating inertia), twin-scroll pulse separation, anti-lag | ~64 s |
| `sc` | Supercharger vs turbo: belt-driven Roots blower vs exhaust-driven turbo, instant boost vs efficiency | ~63 s |
| `rotary` | Rotary (Wankel) engine: epitrochoid housing, apex seals, the four strokes in three chambers, eccentric shaft (3:1), phasing gears, pros and cons | ~67 s |
| `vtec` | Camshaft + VTEC: lobes, rockers, valves and springs, 2:1 timing belt, lift/duration/timing graph, Honda VTEC locking pins | ~67 s |

| Step | Tool | File |
|------|------|------|
| Script + AI voice-over + caption timings | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) neural TTS (offline, blended voice) | `voiceover.py` |
| 3D scene: cut-away turbocharger, engine, intercooler, wastegate, particle air/exhaust flow, labels, HUD, captions | three.js (WebGL) | `scene.html` |
| Frame-by-frame render + encode with audio | Playwright (headless Chromium) + ffmpeg | `render.mjs` |
| Covers / thumbnails | `render.mjs --clean` + PIL | `thumbnails.py` |

## What each video includes

- ~63–67 s long (just over a minute, so it qualifies for TikTok's Creator Rewards).
- Blended, more natural AI voice: each sentence is voiced with a mix of Kokoro styles
  (`am_fenrir` + `am_puck` + `am_onyx`/`am_michael`). Punchy lines lean energetic and wider in
  pitch, explanations lean deeper and calmer, with natural pauses between sentences; then EQ
  warmth, light compression and a small room (`MOODS` / `VOICE_FX` in `voiceover.py`).
- An end card asking viewers to pick the next topic (A or B in the comments).
- A distinct 1080×1920 cover per video from `thumbnails.py`.

## Build

```bash
./build.sh            # writes ./build/how_a_turbo_works.mp4
./build.sh lag        # writes ./build/turbo_lag_twin_scroll_anti_lag.mp4
./build.sh sc         # writes ./build/supercharger_vs_turbo.mp4
./build.sh rotary     # writes ./build/rotary_engine.mp4
./build.sh vtec       # writes ./build/camshaft_and_vtec.mp4
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

### Rotary model notes

The Wankel is built from its real kinematics rather than hand-animated: the
housing bore is the epitrochoid `x = e·cos3θ + R·cosθ, y = e·sin3θ + R·sinθ`
(R = 1, e = 0.15), the rotor is the numerically computed inner envelope of that
bore (apex tips run on the wall), the rotor centre orbits on the eccentric
lobe while the rotor turns at one third of shaft speed, and the ring/stationary
gears have 3e/2e pitch radii. Chamber fills and gas particles are rebuilt from
the rotor and housing every frame, so the visible compression is real geometry.
