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

# story -> [(scene id, narration)]. Scene ids drive the camera/animation in scene.html.
SCRIPTS = {
    "turbo": [
        ("intro", "Ever wondered how a turbo makes a small engine hit like a big one?"),
        ("exhaust", "It starts with hot exhaust gas leaving the engine."),
        ("turbine", "That gas blasts through a turbine wheel, spinning it at up to one hundred fifty thousand RPM."),
        ("shaft", "A shaft connects the turbine to a compressor wheel on the cold side."),
        ("compressor", "The compressor sucks in fresh air and squeezes it, packing in way more oxygen."),
        ("intercooler", "Squeezed air gets hot, so an intercooler cools it down, making it even denser."),
        ("power", "More air means more fuel can burn, and that means more power."),
        ("wastegate", "When boost gets too high, a wastegate opens and lets exhaust bypass the turbine."),
        ("outro", "Wasted energy, turned into power. That's how a turbo works."),
    ],
    "lag": [
        ("lag_intro", "You floor it, and... nothing. Then the boost hits all at once. That delay is turbo lag."),
        ("lag_cause", "A turbo is powered by exhaust. At low RPM, the engine just doesn't make enough of it to spin the turbine fast."),
        ("inertia", "On top of that, the wheels have mass, so it takes time to spool them up to speed."),
        ("twinscroll", "Twin-scroll turbos fight this by splitting the turbine housing into two separate passages."),
        ("pulses", "Cylinders are paired so their exhaust pulses don't collide, and each pulse hits the turbine harder."),
        ("ts_result", "The result? The turbo spools sooner, with far less lag."),
        ("antilag", "Race cars go even further, with anti-lag."),
        ("antilag_how", "When the driver lifts off, fuel and air are fed into the hot exhaust, where they ignite and keep the turbine spinning."),
        ("antilag_cost", "That's the pops and bangs you hear from rally cars. Instant boost, but brutal on parts."),
        ("outro", "That's turbo lag, and how engineers kill it."),
    ],
    "sc": [
        ("sc_intro", "Superchargers and turbos both cram extra air into your engine. The difference is what drives them."),
        ("turbo_side", "A turbo is exhaust-driven. Hot gas that would be wasted spins a turbine."),
        ("sc_belt", "A supercharger is belt-driven, powered straight off the crankshaft."),
        ("sc_rotors", "The belt spins a pair of rotors that force air down into the intake."),
        ("sc_instant", "Since it's tied to engine speed, boost is instant. No lag, right off idle."),
        ("sc_cost", "The catch? Turning it eats engine power, so it's less efficient."),
        ("turbo_pro", "A turbo recycles energy for free, so it's more efficient, but it can lag."),
        ("verdict", "Supercharger: instant punch. Turbo: efficient power. Which one would you pick?"),
    ],
}

VOICE = "am_michael"
SPEED = 1.08
# Spoken words -> how they appear in the captions (merged into one token).
CAPTION_MERGE = {"one hundred fifty thousand": "150,000"}
GAP = 0.25  # seconds of silence between lines
LEAD_IN = 0.35


def word_weight(w: str) -> float:
    core = re.sub(r"[^A-Za-z0-9]", "", w)
    vowels = len(re.findall(r"[aeiouy]+", core.lower())) or 1
    return 0.6 + vowels + (0.4 if re.search(r"[,.?!:]$", w) else 0)


def pauses(audio, sr, win=0.02, min_len=0.07, thresh=0.012):
    """Silent stretches inside the clip as (start, end, length) in seconds."""
    hop = int(win * sr)
    rms = np.array([np.sqrt(np.mean(audio[i:i + hop] ** 2)) for i in range(0, len(audio) - hop, hop)])
    out, start = [], None
    for k, quiet in enumerate(rms < thresh):
        if quiet and start is None:
            start = k
        elif not quiet and start is not None:
            if (k - start) * win >= min_len and start > 0:
                out.append((start * win, k * win, (k - start) * win))
            start = None
    return out


def word_timings(text, audio, sr, t0):
    """Word start/end times. Phrase boundaries (after , . ? !) are snapped to the
    longest pauses in the audio; words inside a phrase are spread by weight."""
    words = text.split()
    weights = [word_weight(w) for w in words]
    dur = len(audio) / sr
    gaps = pauses(audio, sr)
    breaks = [i for i, w in enumerate(words[:-1]) if re.search(r"[,.?!:]$", w)]
    # each break: expected time by weight, snapped to the nearest later pause within 0.6 s
    spans, bounds, cur = [], [0], 0.0
    for br in breaks:
        expected = dur * sum(weights[:br + 1]) / sum(weights)
        cands = [g for g in gaps if g[0] > cur + 0.15 and abs((g[0] + g[1]) / 2 - expected) < 0.6]
        if not cands:
            continue
        g = min(cands, key=lambda g: abs((g[0] + g[1]) / 2 - expected) - g[2])
        spans.append((cur, g[0]))
        bounds.append(br + 1)
        cur = g[1]
    spans.append((cur, dur))
    bounds.append(len(words))
    out = []
    for (s, e), a, b in zip(spans, bounds[:-1], bounds[1:]):
        ws, wg = words[a:b], weights[a:b]
        acc = s
        for w, wgt in zip(ws, wg):
            d = (e - s) * wgt / sum(wg)
            out.append({"w": w, "s": round(t0 + acc, 3), "e": round(t0 + acc + d, 3)})
            acc += d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--story", default="turbo", choices=sorted(SCRIPTS))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    kokoro = Kokoro(os.path.join(args.models, "kokoro-v1.0.onnx"),
                    os.path.join(args.models, "voices-v1.0.bin"))
    sr = 24000
    chunks = [np.zeros(int(LEAD_IN * sr), dtype=np.float32)]
    t = LEAD_IN
    lines = []
    for scene, text in SCRIPTS[args.story]:
        audio, sr = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        audio = audio.astype(np.float32)
        # trim leading/trailing near-silence so timings are tight
        idx = np.where(np.abs(audio) > 0.01)[0]
        if len(idx):
            audio = audio[max(0, idx[0] - 600): idx[-1] + 1200]
        dur = len(audio) / sr
        wt = word_timings(text, audio, sr, t)
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
        json.dump({"story": args.story, "duration": round(total_dur, 3), "lines": lines}, f, indent=1)
    print(f"total {total_dur:.2f}s")


if __name__ == "__main__":
    main()
