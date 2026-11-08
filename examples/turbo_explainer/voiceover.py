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
import subprocess

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

# story -> [(scene id, narration[, speed multiplier])]. Scene ids drive the camera/animation
# in scene.html. Punctuation (! ? ...) is deliberate: it is what gives Kokoro its expression.
# Every video ends on a "cta" line asking viewers to pick the next topic in the comments.
SCRIPTS = {
    "turbo": [
        ("intro", "Ever wonder how a tiny engine can hit like a big one? It's all about the turbo! Let's look inside.", 1.1),
        ("exhaust", "It starts with something your engine normally throws away... hot exhaust gas, often well over seven hundred degrees Celsius."),
        ("turbine", "That gas blasts through a turbine wheel and spins it insanely fast. Well over a hundred thousand RPM!"),
        ("shaft", "A steel shaft links that turbine to a compressor wheel on the cold side. When one spins, so does the other."),
        ("compressor", "The compressor sucks in fresh air and crams it into the engine, packing in way more oxygen."),
        ("intercooler", "But squeezing air makes it hot. So an intercooler cools it back down, making it even denser."),
        ("power", "More air means you can burn more fuel... and that means more power! That extra air pressure is what we call boost."),
        ("wastegate", "Too much boost could hurt the engine, so a wastegate opens and lets some exhaust skip the turbine."),
        ("outro", "Energy that was going straight out the tailpipe... turned into power. That's a turbo!"),
        ("cta", "So what should we break down next? Diesel versus gas, or how a differential works? Tell me in the comments!", 1.1),
    ],
    "lag": [
        ("lag_intro", "You floor it, and... nothing. Then boom, the boost hits all at once! That delay is turbo lag.", 1.08),
        ("lag_cause", "A turbo runs on exhaust. At low RPM, the engine just isn't making enough of it to spin the turbine fast. And the bigger the turbo, the worse it gets."),
        ("inertia", "And the wheels have mass, so it takes time to spool them up to speed."),
        ("twinscroll", "Twin-scroll turbos fight back by splitting the turbine housing into two separate passages."),
        ("pulses", "Cylinders are paired so their exhaust pulses don't interfere, and each pulse hits the turbine with more energy."),
        ("ts_result", "The result? The turbo spools sooner, with far less lag! That's why so many modern turbo engines use them."),
        ("antilag", "Race cars take it even further... with anti-lag."),
        ("antilag_how", "When the driver lifts off, the system retards the ignition and adds extra fuel and air, so it keeps burning in the exhaust, and the turbine never slows down."),
        ("antilag_cost", "That's the pops and bangs you hear from rally cars! Instant boost, but brutal on parts."),
        ("outro", "That's turbo lag, and how engineers kill it."),
        ("cta", "So what's next? Sequential turbos, or electric turbos? Drop your pick in the comments!", 1.1),
    ],
    "sc": [
        ("sc_intro", "Superchargers and turbos do the same job... cram extra air into your engine. So what's the difference? It's all about what drives them!", 1.08),
        ("turbo_side", "A turbo is exhaust-driven. Hot gas that would just blow out the tailpipe spins a turbine, which spins the compressor."),
        ("sc_belt", "A supercharger is belt-driven. A belt connects it straight to the crankshaft, so it spins whenever the engine spins."),
        ("sc_rotors", "In a Roots-style blower like this one, two twisted rotors mesh together and shove air down into the intake."),
        ("sc_instant", "Because it's tied to engine speed, the boost is right there the instant you hit the throttle. No lag at all!"),
        ("sc_cost", "But here's the catch. Spinning that blower eats engine power, sometimes tens of horsepower, so it's less efficient."),
        ("turbo_pro", "A turbo mostly runs on energy that was being wasted anyway, so it's more efficient... but it can lag."),
        ("verdict", "Supercharger: instant punch. Turbo: efficient power. And some cars, like the Lancia Delta S4, even run both!"),
        ("cta", "So what should we cover next? Twincharging, or centrifugal superchargers? Let me know in the comments!", 1.1),
    ],
    "rotary": [
        ("r_intro", "No pistons. No valves. Just a spinning triangle! This is the rotary engine.", 1.05),
        ("r_piston", "A normal engine slams pistons up and down, and a crankshaft turns that into rotation."),
        ("r_parts", "A rotary skips all that. A triangular rotor spins inside an oval-shaped housing, called an epitrochoid."),
        ("r_seals", "Apex seals on each tip slide along the wall, splitting it into three sealed chambers."),
        ("r_intake", "A chamber grows... and pulls in air and fuel through the intake port."),
        ("r_compress", "Then it shrinks, squeezing that mixture tight."),
        ("r_power", "The spark plugs fire, and the blast shoves the rotor around!"),
        ("r_exhaust", "Then it sweeps past the exhaust port and pushes the burnt gas out."),
        ("r_all", "All three chambers work at once, so there's a power stroke on every turn of the shaft."),
        ("r_shaft", "The rotor rides on an eccentric shaft that spins three times for every one turn of the rotor."),
        ("r_gears", "And a fixed gear inside keeps the two perfectly in sync."),
        ("r_pros", "Fewer moving parts, silky smooth, and big power from a tiny package!"),
        ("r_cons", "The catch? Apex seals wear, and it's thirsty for fuel and oil."),
        ("r_outro", "No pistons... just spin. That's the rotary!"),
        ("cta", "So what's next? Two-stroke engines, or the boxer engine? Tell me in the comments!", 1.1),
    ],
    "vtec": [
        ("v_intro", "Every engine has to breathe. And the camshaft decides exactly when!", 1.05),
        ("v_cam", "It's a spinning shaft with egg-shaped lobes. Each lobe that comes around pushes a valve open."),
        ("v_spring", "Then a stiff spring snaps it shut again... thousands of times a minute!"),
        ("v_belt", "A timing belt links it to the crank, so the cam turns once for every two crank turns."),
        ("v_profile", "The lobe's shape sets everything. How early the valve opens, how far, and how long."),
        ("v_tradeoff", "Here's the problem. A mild cam is smooth down low, but runs out of breath up high. A wild cam is the opposite."),
        ("v_vtec", "Honda's VTEC gives you both! Each pair of valves gets two mild lobes, plus one wild lobe in the middle."),
        ("v_low", "At low RPM, the middle rocker just floats on its own spring, doing nothing."),
        ("v_engage", "Then, around fifty-five hundred RPM on many engines, oil pressure shoves pins through all three rockers... locking them together!", 1.05),
        ("v_high", "Now both valves ride the wild lobe. More lift, longer duration, and a second wind of power!"),
        ("v_outro", "That's VTEC. Two cam profiles in one engine."),
        ("cta", "So what should we break down next? Variable valve timing, or dual-clutch gearboxes? Tell me in the comments!", 1.1),
    ],
}

# The narrator is a blend of Kokoro voice styles (style vectors are mixed linearly).
# All moods share the same core (fenrir) so it stays one person; the mix shifts per
# sentence: punchy sentences lean on fenrir/puck (wide pitch range), explanations pull
# in onyx/michael for a deeper, calmer tone. Measured on the same text:
#   base  ~112 Hz median, 13.6 semitone range   hype ~122 Hz, 15.4 st   calm ~110 Hz, 9.9 st
MOODS = {
    "base": {"am_fenrir": 0.5, "am_puck": 0.25, "am_onyx": 0.25},
    "hype": {"am_fenrir": 0.6, "am_puck": 0.35, "am_onyx": 0.05},
    "calm": {"am_fenrir": 0.35, "am_onyx": 0.35, "am_michael": 0.3},
}
CALM_CUES = ("but ", "so ", "and ", "because", "that means", "the result")
SENT_PAUSE = {".": 0.24, "!": 0.26, "?": 0.3, "…": 0.32}
# Post-processing for a less "dry TTS" sound: warmth, a touch of presence,
# gentle compression and a very small room.
VOICE_FX = ("highpass=f=70,equalizer=f=140:t=q:w=1:g=3,equalizer=f=3200:t=q:w=1.2:g=2,"
            "equalizer=f=7500:t=q:w=1:g=-2,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2,"
            "aecho=0.8:0.85:28|47:0.08|0.05")
SPEED = 1.0
# Spoken words -> how they appear in the captions (merged into one token).
CAPTION_MERGE = {"one hundred fifty thousand": "150,000", "fifty-five hundred": "5,500", "seven hundred": "700", "a hundred thousand": "100,000"}
GAP = 0.35  # seconds of silence between lines
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


def mood_of(sentence, idx, n_sent, scene):
    low = sentence.lower()
    if scene in ("intro", "cta") or scene.endswith("_intro") or sentence.rstrip().endswith("!"):
        return "hype"
    if sentence.rstrip().endswith("?"):
        return "base"
    if idx > 0 and low.startswith(CALM_CUES):
        return "calm"
    return "base" if idx % 2 == 0 else "calm"


def split_sentences(text):
    # keep the terminal punctuation; "..." stays inside its sentence (a dramatic pause)
    parts = re.findall(r".+?(?:(?<!\.)[.!?](?!\.)|$)(?:\s+|$)", text)
    return [p.strip() for p in parts if p.strip()]


def synth_line(kokoro, styles, scene, text, speed):
    """Synthesise sentence by sentence, each with its own mood blend, and return
    the joined audio plus (audio, sentence) pieces with their offsets for timing."""
    sents = split_sentences(text)
    pieces, out, t = [], [], 0.0
    sr = 24000
    for i, sen in enumerate(sents):
        mood = mood_of(sen, i, len(sents), scene)
        sp = speed * (1.04 if mood == "hype" else 0.97 if mood == "calm" else 1.0)
        a, sr = kokoro.create(sen, voice=styles[mood], speed=sp, lang="en-us")
        a = a.astype(np.float32)
        idx = np.where(np.abs(a) > 0.01)[0]
        if len(idx):
            a = a[max(0, idx[0] - 600): idx[-1] + 1200]
        pieces.append((t, a, sen, mood))
        out.append(a)
        t += len(a) / sr
        if i < len(sents) - 1:
            pause = SENT_PAUSE.get(sen.rstrip()[-1], 0.22)
            out.append(np.zeros(int(pause * sr), dtype=np.float32))
            t += pause
    return np.concatenate(out), sr, pieces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--story", default="turbo", choices=sorted(SCRIPTS))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    kokoro = Kokoro(os.path.join(args.models, "kokoro-v1.0.onnx"),
                    os.path.join(args.models, "voices-v1.0.bin"))
    styles = {m: sum(w * kokoro.get_voice_style(v) for v, w in mix.items()).astype(np.float32)
              for m, mix in MOODS.items()}
    sr = 24000
    chunks = [np.zeros(int(LEAD_IN * sr), dtype=np.float32)]
    t = LEAD_IN
    lines = []
    for entry in SCRIPTS[args.story]:
        scene, text = entry[0], entry[1]
        mult = entry[2] if len(entry) > 2 else 1.0
        audio, sr, pieces = synth_line(kokoro, styles, scene, text, SPEED * mult)
        dur = len(audio) / sr
        wt = []
        for off, a, sen, mood in pieces:
            wt += word_timings(sen, a, sr, t + off)
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
        print(f"{scene:12s} {dur:5.2f}s  " + " | ".join(f"[{m}] {x}" for _, _, x, m in pieces))

    chunks.append(np.zeros(int(1.0 * sr), dtype=np.float32))
    full = np.concatenate(chunks)
    dry = os.path.join(args.out, "voice_dry.wav")
    sf.write(dry, full, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", dry, "-af", VOICE_FX,
                    os.path.join(args.out, "voice.wav")], check=True)
    total_dur = len(full) / sr
    with open(os.path.join(args.out, "timeline.json"), "w") as f:
        json.dump({"story": args.story, "duration": round(total_dur, 3), "lines": lines}, f, indent=1)
    print(f"total {total_dur:.2f}s")


if __name__ == "__main__":
    main()
