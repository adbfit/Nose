"""Atlas-style annotation: title, leader lines with labels in the margins, source footer."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(candidates, size):
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _spread(ys, lo, hi, gap):
    """Push label y positions apart so they do not overlap, keeping order."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    placed = [0.0] * len(ys)
    cur = lo
    for i in order:
        cur = max(ys[i], cur)
        placed[i] = cur
        cur += gap
    overflow = cur - gap - hi
    if overflow > 0:
        for i in order:
            placed[i] -= overflow
    return placed


def annotate(src: Path, dst: Path, *, title: str, items: list, footer_refs: list,
             lang: str = "it", background: str = "dark"):
    img = Image.open(src).convert("RGB")
    w, h = img.size
    scale = w / 1800.0
    margin = int(0.30 * w) if items else int(0.04 * w)
    header, footer = int(110 * scale), int(95 * scale)
    bg = (238, 238, 240) if background == "light" else (10, 11, 14)
    fg = (30, 30, 34) if background == "light" else (228, 226, 220)
    muted = (110, 110, 118) if background == "light" else (140, 140, 148)
    line_c = (60, 60, 66) if background == "light" else (235, 232, 222)

    canvas = Image.new("RGB", (w + 2 * margin, h + header + footer), bg)
    canvas.paste(img, (margin, header))
    draw = ImageDraw.Draw(canvas)
    f_title = _font(BOLD_CANDIDATES, int(46 * scale))
    f_label = _font(FONT_CANDIDATES, int(30 * scale))
    f_foot = _font(FONT_CANDIDATES, int(22 * scale))

    draw.text((int(40 * scale), int(30 * scale)), title, font=f_title, fill=fg)

    left = [(n, (x + margin, y + header)) for n, (x, y, _) in items if x < w / 2]
    right = [(n, (x + margin, y + header)) for n, (x, y, _) in items if x >= w / 2]
    gap = int(64 * scale)
    for side, group in (("L", left), ("R", right)):
        if not group:
            continue
        ys = _spread([p[1] for _, p in group], header + gap, header + h - gap, gap)
        for (name, (ax, ay)), ly in zip(group, ys):
            if side == "L":
                tx = int(30 * scale)
                elbow = margin - int(20 * scale)
                text_end = tx + draw.textlength(name, font=f_label)
                draw.line([(text_end + 10 * scale, ly), (elbow, ly), (ax, ay)], fill=line_c,
                          width=max(1, int(2 * scale)))
                draw.text((tx, ly - 18 * scale), name, font=f_label, fill=fg)
            else:
                tw = draw.textlength(name, font=f_label)
                tx = canvas.width - int(30 * scale) - tw
                elbow = margin + w + int(20 * scale)
                draw.line([(ax, ay), (elbow, ly), (tx - 10 * scale, ly)], fill=line_c,
                          width=max(1, int(2 * scale)))
                draw.text((tx, ly - 18 * scale), name, font=f_label, fill=fg)
            r = max(3, int(6 * scale))
            draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=line_c)

    label = "Fonti" if lang == "it" else "Sources"
    note = ("Ricostruzione procedurale parametrica — vedi file .json per valori e livello di evidenza"
            if lang == "it" else
            "Parametric procedural reconstruction — see the .json file for values and evidence level")
    draw.text((int(40 * scale), h + header + int(14 * scale)), f"{label}: " + "; ".join(footer_refs),
              font=f_foot, fill=muted)
    draw.text((int(40 * scale), h + header + int(48 * scale)), note, font=f_foot, fill=muted)
    canvas.save(dst, optimize=True)


def photo_finish(src: Path, dst: Path, grain: float = 0.018, vignette: float = 0.28, seed: int = 0):
    """Macro-photograph finish: gentle vignette, luminance grain and unsharp mask."""
    import numpy as np
    from PIL import ImageFilter
    img = Image.open(src).convert("RGB")
    a = np.asarray(img).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    a *= (1.0 - vignette * r ** 2.2)[..., None]
    rng = np.random.default_rng(seed)
    a += rng.normal(0.0, grain, size=(h, w, 1)) * (0.4 + 0.6 * a.mean(axis=2, keepdims=True))
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    out.save(dst, optimize=True)
