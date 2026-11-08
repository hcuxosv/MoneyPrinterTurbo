# 3D explainer studio

This makes fully rendered 3D explainer videos without any paid video API. The
voiceover runs locally with Kokoro TTS. The 3D scene is three.js, rendered frame by
frame in headless Chromium and synced to the narration. Captions highlight each word
as it's spoken, and the music ducks under the voice.

| File | What it is |
| --- | --- |
| `cpu/script.json` | Narration split into scenes and lines. Per-line `speed` and `pause` control delivery |
| `cpu/scene.html` | The 3D animation (board → socket → exploded layers → die → transistors → clock → buying tips) |
| `tts.py` | script.json → `voice.wav` + `timings.json` (Kokoro, default voice `af_heart`) |
| `render.mjs` | Renders any scene page to MP4, or single frames with `--still 12,40` |
| `captions.py` | timings.json → word-highlighted `.ass` captions |
| `make_video.sh` | Runs the whole pipeline: `./make_video.sh cpu` → `out/cpu/cpu_explainer.mp4` |
| `thumbs/` | Thumbnail generator for all 10 videos (`node thumbs/render-thumbs.mjs out/thumbnails`) |

## Setup

```sh
cd presets/pc-parts/studio
npm install                                   # three.js
uv venv .venv && uv pip install --python .venv/bin/python kokoro-onnx soundfile
mkdir -p models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd .. && KOKORO_PY=.venv/bin/python ./make_video.sh cpu
```

Playwright with Chromium and ffmpeg (with libass) must be installed. Rendering is
CPU-only (SwiftShader): about 1 s per 1080p frame, so a 100-second video takes
around an hour. A machine with a GPU is much faster. To render with GPU WebGL, drop
the `--use-angle=swiftshader` flag in `render.mjs`.

## Changing things

- **Voice:** set `"voice"` in `script.json`. Good options are `af_heart` and
  `af_bella` (female), and `am_michael` and `am_fenrir` (male). Delete
  `out/<part>/timings.json` to regenerate.
- **Wording:** edit `script.json`. The 3D timing follows the new lines
  automatically, because every camera move and label is keyed to line start/end
  times.
- **Music:** `MUSIC=path/to/track.mp3 ./make_video.sh cpu`
- **Vertical / Shorts:** `render.mjs --width 1080 --height 1920` and
  `captions.py --width 1080 --height 1920`. You'll need to reframe the camera keys
  in the scene for portrait.
- **Next parts:** copy `cpu/` to e.g. `gpu/` and write a new `script.json` and
  `scene.html`. `lib.js` has the shared camera path, labels, bloom and HUD helpers.
