"""Render a script.json to voice.wav + timings.json using local Kokoro TTS.

usage: python tts.py <script.json> <out_dir> --model kokoro-v1.0.onnx --voices voices-v1.0.bin
"""
import argparse, json, os, re
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

ap = argparse.ArgumentParser()
ap.add_argument("script"); ap.add_argument("out")
ap.add_argument("--model", required=True); ap.add_argument("--voices", required=True)
ap.add_argument("--voice"); ap.add_argument("--lead", type=float, default=0.6)
a = ap.parse_args()
spec = json.load(open(a.script))
voice = a.voice or spec.get("voice", "af_heart")
k = Kokoro(a.model, a.voices)
os.makedirs(a.out, exist_ok=True)

def trim(x, sr, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    if not len(idx): return x
    s = max(idx[0] - int(0.03 * sr), 0); e = min(idx[-1] + int(0.06 * sr), len(x))
    return x[s:e]

sr = 24000
chunks = [np.zeros(int(a.lead * sr), dtype=np.float32)]
t = a.lead
out = {"voice": voice, "scenes": []}
for sc in spec["scenes"]:
    s_start = t; lines = []
    for ln in sc["lines"]:
        audio, sr = k.create(ln["text"], voice=voice, speed=ln.get("speed", 1.0), lang="en-us")
        audio = trim(audio.astype(np.float32), sr)
        dur = len(audio) / sr
        lines.append({"text": ln["text"], "start": round(t, 3), "end": round(t + dur, 3)})
        chunks.append(audio); t += dur
        p = ln.get("pause", 0.3); chunks.append(np.zeros(int(p * sr), dtype=np.float32)); t += p
    out["scenes"].append({"id": sc["id"], "start": round(s_start, 3), "end": round(t, 3), "lines": lines})
chunks.append(np.zeros(int(1.0 * sr), dtype=np.float32)); t += 1.0
out["duration"] = round(t, 3)
wav = np.concatenate(chunks)
wav = wav / max(np.abs(wav).max(), 1e-6) * 0.89
sf.write(os.path.join(a.out, "voice.wav"), wav, sr)
json.dump(out, open(os.path.join(a.out, "timings.json"), "w"), indent=1)
print(f"duration {t:.1f}s, voice {voice}")
