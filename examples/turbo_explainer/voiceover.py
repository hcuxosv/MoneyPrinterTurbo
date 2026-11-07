"""Generate the AI voice-over and caption timings for the turbo explainer.

Uses Kokoro (open-source neural TTS, runs fully offline via onnxruntime).
Each narration line is synthesised separately so we know exactly when it
starts and ends; word timings inside a line are distributed by syllable-ish
weight, which is accurate enough for short-form "karaoke" captions.

Usage:
    python voiceover.py --models <dir with kokoro-v1.0.onnx + voices-v1.0.bin> --out <dir>
"""

import argparse
import json
import os
import re

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

# (scene id, narration). Scene ids drive the camera/animation in scene.html.
SCRIPT = [
    ("intro", "Ever wondered how a turbo makes a small engine hit like a big one?"),
    ("exhaust", "It starts with hot exhaust gas leaving the engine."),
    ("turbine", "That gas blasts through a turbine wheel, spinning it at up to one hundred fifty thousand RPM."),
    ("shaft", "A shaft connects the turbine to a compressor wheel on the cold side."),
    ("compressor", "The compressor sucks in fresh air and squeezes it, packing in way more oxygen."),
    ("intercooler", "Squeezed air gets hot, so an intercooler cools it down, making it even denser."),
    ("power", "More air means more fuel can burn, and that means more power."),
    ("wastegate", "When boost gets too high, a wastegate opens and lets exhaust bypass the turbine."),
    ("outro", "Wasted energy, turned into power. That's how a turbo works."),
]

VOICE = "am_michael"
SPEED = 1.08
# Spoken words -> how they appear in the captions (merged into one token).
CAPTION_MERGE = {"one hundred fifty thousand": "150,000"}
GAP = 0.25  # seconds of silence between lines
LEAD_IN = 0.35


def word_weight(w: str) -> float:
    core = re.sub(r"[^A-Za-z0-9]", "", w)
    vowels = len(re.findall(r"[aeiouy]+", core.lower())) or 1
    return 0.6 + vowels + (0.4 if re.search(r"[,.?!]$", w) else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    kokoro = Kokoro(os.path.join(args.models, "kokoro-v1.0.onnx"),
                    os.path.join(args.models, "voices-v1.0.bin"))
    sr = 24000
    chunks = [np.zeros(int(LEAD_IN * sr), dtype=np.float32)]
    t = LEAD_IN
    lines = []
    for scene, text in SCRIPT:
        audio, sr = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        audio = audio.astype(np.float32)
        # trim leading/trailing near-silence so timings are tight
        idx = np.where(np.abs(audio) > 0.01)[0]
        if len(idx):
            audio = audio[max(0, idx[0] - 600): idx[-1] + 1200]
        dur = len(audio) / sr
        words = text.split()
        weights = [word_weight(w) for w in words]
        total = sum(weights)
        wt, acc = [], t
        for w, wgt in zip(words, weights):
            d = dur * wgt / total
            wt.append({"w": w, "s": round(acc, 3), "e": round(acc + d, 3)})
            acc += d
        for spoken, shown in CAPTION_MERGE.items():
            n = len(spoken.split())
            for i in range(len(wt) - n + 1):
                if " ".join(x["w"] for x in wt[i:i + n]).lower() == spoken:
                    wt[i:i + n] = [{"w": shown, "s": wt[i]["s"], "e": wt[i + n - 1]["e"]}]
                    break
        lines.append({"scene": scene, "text": text, "s": round(t, 3), "e": round(t + dur, 3), "words": wt})
        chunks.append(audio)
        chunks.append(np.zeros(int(GAP * sr), dtype=np.float32))
        t += dur + GAP
        print(f"{scene:12s} {dur:5.2f}s  {text}")

    chunks.append(np.zeros(int(1.0 * sr), dtype=np.float32))
    full = np.concatenate(chunks)
    sf.write(os.path.join(args.out, "voice.wav"), full, sr)
    total_dur = len(full) / sr
    with open(os.path.join(args.out, "timeline.json"), "w") as f:
        json.dump({"duration": round(total_dur, 3), "lines": lines}, f, indent=1)
    print(f"total {total_dur:.2f}s")


if __name__ == "__main__":
    main()
