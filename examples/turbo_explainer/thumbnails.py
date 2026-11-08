"""Make a distinct 1080x1920 cover/thumbnail for each story.

Renders a bare 3D frame (no captions/labels) from the story's own scene with
render.mjs --clean, then composes bold text on top with PIL. Each story gets
its own layout and colour scheme so the covers don't look templated.

    python thumbnails.py --build <root with one sub-dir per story> --out <dir> [--stories turbo,lag]
"""

import argparse
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_IT = "/usr/share/fonts/opentype/inter/Inter-BlackItalic.otf"
W, H = 1080, 1920


def scene_time(build, scene, frac=0.5, offset=0.0):
    tl = json.load(open(os.path.join(build, "timeline.json")))
    lines = tl["lines"]
    for i, ln in enumerate(lines):
        if ln["scene"] == scene:
            s0 = ln["s"] - 0.25
            s1 = lines[i + 1]["s"] - 0.25 if i + 1 < len(lines) else tl["duration"]
            return round(s0 + (s1 - s0) * frac + offset, 2)
    raise KeyError(scene)


def frame(build, t):
    subprocess.run(["node", os.path.join(HERE, "render.mjs"), "--build", build, "--stills", str(t), "--clean"],
                   check=True, capture_output=True)
    return Image.open(os.path.join(build, f"still_{t:.1f}.png")).convert("RGB")


def font(size, italic=False):
    return ImageFont.truetype(FONT_IT if italic else FONT, size)


def text(img, xy, s, size, fill, stroke=14, stroke_fill="black", anchor="mm", italic=False, shadow=True):
    d = ImageDraw.Draw(img)
    f = font(size, italic)
    if shadow:  # soft drop shadow for legibility on any background
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((xy[0], xy[1] + 14), s, font=f, fill=(0, 0, 0, 200), anchor=anchor,
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12))) if img.mode == "RGBA" else None
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


def fit_size(s, max_w, start, italic=False):
    size = start
    while size > 40 and font(size, italic).getbbox(s)[2] > max_w:
        size -= 4
    return size


def pill(img, cx, cy, s, size, fg, bg, pad=(44, 22)):
    d = ImageDraw.Draw(img)
    f = font(size)
    l, t, r, b = f.getbbox(s)
    w, h = r - l + pad[0] * 2, b - t + pad[1] * 2
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=h / 2, fill=bg)
    d.text((cx, cy), s, font=f, fill=fg, anchor="mm")


def vignette(img, top=0.0, bottom=0.0, color=(0, 0, 0)):
    """Darken the top/bottom so text pops."""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for y in range(H):
        a = 0
        if top and y < H * top:
            a = int(230 * (1 - y / (H * top)) ** 1.4)
        if bottom and y > H * (1 - bottom):
            a = max(a, int(230 * ((y - H * (1 - bottom)) / (H * bottom)) ** 1.4))
        if a:
            d.line([(0, y), (W, y)], fill=color + (a,))
    return Image.alpha_composite(img.convert("RGBA"), ov)


def thumb_turbo(build):
    img = vignette(frame(build, scene_time(build, "turbine", 0.75)), top=0.42, bottom=0.25)
    text(img, (W / 2, 250), "HOW A", 130, "white")
    text(img, (W / 2, 470), "TURBO", fit_size("TURBO", 1000, 330), "#ffd21f", stroke=18)
    text(img, (W / 2, 680), "WORKS", 150, "white")
    pill(img, W / 2, 1700, "EXPLAINED IN 3D", 70, "#0b0f16", "#ff8a1f")
    return img


def thumb_lag(build):
    t = scene_time(build, "antilag_cost", 0.0, 0.05 + 2 / 1.6)   # on a BANG frame
    img = vignette(frame(build, t), top=0.25, bottom=0.45, color=(20, 0, 0))
    text(img, (W / 2, 220), "WHY TURBOS", 120, "white")
    text(img, (W / 2, 1290), "LAG", 400, "#ff3b2e", stroke=20, italic=True)
    text(img, (W / 2, 1560), "+ HOW ANTI-LAG", 90, "white")
    text(img, (W / 2, 1680), "KILLS IT", 110, "#ffd21f")
    return img


def thumb_sc(build):
    top = frame(build, scene_time(build, "sc_instant", 0.7))
    bot = frame(build, scene_time(build, "turbo_pro", 0.85))
    img = Image.new("RGBA", (W, H))
    img.paste(top.crop((0, 300, W, 300 + H // 2)), (0, 0))
    img.paste(bot.crop((0, 380, W, 380 + H // 2)), (0, H // 2))
    d = ImageDraw.Draw(img)
    # diagonal split
    d.polygon([(0, H / 2 + 70), (W, H / 2 - 70), (W, H / 2 - 52), (0, H / 2 + 88)], fill="#ffffff")
    text(img, (W / 2, 150), "SUPERCHARGER", fit_size("SUPERCHARGER", 1000, 140), "#4dff88")
    text(img, (W / 2, H - 160), "TURBO", 170, "#ff8a1f")
    d.ellipse([W / 2 - 170, H / 2 - 170, W / 2 + 170, H / 2 + 170], fill="#c4161c", outline="white", width=14)
    text(img, (W / 2, H / 2 + 6), "VS", 190, "white", stroke=0, shadow=False)
    return img


def thumb_rotary(build):
    img = vignette(frame(build, scene_time(build, "r_all", 0.55)), top=0.3, bottom=0.3, color=(10, 0, 20))
    text(img, (W / 2, 210), "NO", 260, "#ff3b2e", stroke=18, italic=True)
    text(img, (W / 2, 420), "PISTONS?!", fit_size("PISTONS?!", 1000, 190), "#ffffff", stroke=16)
    text(img, (W / 2, 1560), "THE ROTARY", 140, "#b46bff", stroke=16)
    text(img, (W / 2, 1720), "ENGINE", 140, "#ffd21f", stroke=16)
    return img


def thumb_vtec(build):
    img = vignette(frame(build, scene_time(build, "v_vtec", 0.85)), top=0.35, bottom=0.3, color=(25, 0, 0))
    text(img, (W / 2, 330), "VTEC", 340, "#ffd21f", stroke=22, stroke_fill="#c4161c", italic=True)
    pill(img, W / 2, 560, "WHAT IT ACTUALLY DOES", 62, "white", "#c4161c")
    text(img, (W / 2, 1640), "MILD + WILD CAM", fit_size("MILD + WILD CAM", 1000, 110), "white")
    text(img, (W / 2, 1780), "IN ONE ENGINE", fit_size("IN ONE ENGINE", 1000, 120), "#ff3b2e")
    return img


MAKERS = {"turbo": thumb_turbo, "lag": thumb_lag, "sc": thumb_sc, "rotary": thumb_rotary, "vtec": thumb_vtec}
NAMES = {"turbo": "how_a_turbo_works", "lag": "turbo_lag_twin_scroll_anti_lag", "sc": "supercharger_vs_turbo",
         "rotary": "rotary_engine", "vtec": "camshaft_and_vtec"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True, help="root dir with one sub-dir per story (timeline.json, node_modules)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stories", default=",".join(MAKERS))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for st in args.stories.split(","):
        img = MAKERS[st](os.path.join(args.build, st)).convert("RGB")
        path = os.path.join(args.out, f"{NAMES[st]}_thumbnail.jpg")
        img.save(path, quality=92)
        print("wrote", path)


if __name__ == "__main__":
    main()
