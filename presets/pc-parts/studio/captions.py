"""Build word-highlighted .ass captions from timings.json (written by tts.py).

Kokoro gives line-level timing only, so word times inside a line are estimated from
word length plus extra weight for the pauses at punctuation.

usage: python captions.py <timings.json> <out.ass> [--width 1920 --height 1080]
"""
import argparse, json, re

ap = argparse.ArgumentParser()
ap.add_argument("timings"); ap.add_argument("out")
ap.add_argument("--width", type=int, default=1920); ap.add_argument("--height", type=int, default=1080)
ap.add_argument("--max-words", type=int, default=5); ap.add_argument("--max-chars", type=int, default=28)
a = ap.parse_args()
data = json.load(open(a.timings))
W, H = a.width, a.height
fs = round(H * 0.064)

def ts(t):
    t = max(t, 0); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def words_with_times(line):
    words = line["text"].split()
    wts = []
    for i, w in enumerate(words):
        wt = len(re.sub(r"[^\w]", "", w)) + 1.6
        if i < len(words) - 1:
            if w.endswith("..."): wt += 9
            elif w[-1] in ".!?": wt += 7
            elif w[-1] in ",;:": wt += 4
        wts.append(wt)
    total = sum(wts); t = line["start"]; span = line["end"] - line["start"]; out = []
    for w, wt in zip(words, wts):
        d = span * wt / total
        out.append({"w": w, "s": t, "e": t + d}); t += d
    return out

chunks = []
for sc in data["scenes"]:
    for line in sc["lines"]:
        cur = []
        for wd in words_with_times(line):
            cur.append(wd)
            text = " ".join(x["w"] for x in cur)
            if len(cur) >= a.max_words or len(text) >= a.max_chars or wd["w"][-1] in ".!?,;:":
                chunks.append(cur); cur = []
        if cur: chunks.append(cur)

# keep each chunk up until the next one starts (when the gap is short)
for i, c in enumerate(chunks):
    nxt = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else None
    c[-1]["hold"] = min(nxt, c[-1]["e"] + 0.45) if nxt and nxt - c[-1]["e"] < 0.6 else c[-1]["e"] + 0.25

clean = lambda w: w.upper().replace("{", "(").replace("}", ")")
HL = "&H0035D6FF&"   # highlighted word: warm yellow (ASS colours are BGR)
BASE = "&H00FFFFFF&"
events = []
for c in chunks:
    end_all = c[-1]["hold"]
    for k, wd in enumerate(c):
        s = wd["s"]; e = c[k + 1]["s"] if k + 1 < len(c) else end_all
        parts = []
        for j, x in enumerate(c):
            if j == k: parts.append(r"{\c" + HL + r"\fscx108\fscy108}" + clean(x["w"]) + r"{\c" + BASE + r"\fscx100\fscy100}")
            else: parts.append(clean(x["w"]))
        pop = r"{\fad(60,0)\t(0,120,\fscx104\fscy104)\t(120,220,\fscx100\fscy100)}" if k == 0 else ""
        events.append(f"Dialogue: 0,{ts(s)},{ts(e)},Cap,,0,0,0,,{pop}" + " ".join(parts))

header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Display Black,{fs},{BASE},{BASE},&H00000000&,&H96000000&,0,0,0,0,100,100,1.5,0,1,{round(fs*0.09)},{round(fs*0.06)},2,80,80,{round(H*0.075)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(a.out, "w").write(header + "\n".join(events) + "\n")
print(f"{len(chunks)} caption chunks, {len(events)} events")
