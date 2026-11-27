#!/usr/bin/env python3
"""Make a print-ready Roman-numeral anniversary design (transparent PNG, 300 DPI).

Usage examples:
  python3 make_design.py --initials J A --date 2020-02-14
  python3 make_design.py --initials J A --date 2020-02-14 --color white
  python3 make_design.py --initials J A --date 2020-02-14 --format dmy

Output: 3600 x 2400 px (12 x 8 in at 300 DPI), transparent background.
"""
import argparse
import datetime as dt
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_FONT = os.path.join(HERE, "fonts", "GreatVibes-Regular.ttf")
SERIF_FONT = os.path.join(HERE, "fonts", "CormorantGaramond[wght].ttf")

W, H = 3600, 2400
COLORS = {
    "black": (25, 25, 25, 255),    # for light sweatshirts (white, sand, pink)
    "white": (250, 248, 245, 255),  # for dark sweatshirts (black, navy, maroon)
    "red": (150, 20, 40, 255),      # for white / light pink
}


def to_roman(n: int) -> str:
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def roman_date(d: dt.date, fmt: str) -> str:
    parts = {"m": d.month, "d": d.day, "y": d.year}
    return " · ".join(to_roman(parts[c]) for c in fmt)


def serif(size: int, weight: int = 600) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(SERIF_FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def draw_spaced(draw, text, font, cy, fill, tracking):
    """Draw text centered horizontally at vertical center cy, with letter spacing."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (W - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, cy), ch, font=font, fill=fill, anchor="lm")
        x += w + tracking


def heart_polygon(cx, cy, size):
    pts = []
    for i in range(200):
        t = 2 * math.pi * i / 200
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 32, cy - y * size / 32))
    return pts


def make(initials, date, fmt, color, out_path):
    fill = COLORS[color]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1) Initials in script: "J & A"
    text = f"{initials[0]} & {initials[1]}"
    ssize = 900
    while True:
        script = ImageFont.truetype(SCRIPT_FONT, ssize)
        l, t, r, b = d.textbbox((W / 2, 820), text, font=script, anchor="mm")
        if (r - l) <= W * 0.80 and (b - t) <= 1150 or ssize <= 300:
            break
        ssize -= 20
    # center the actual ink (script glyphs have big swashes) inside the top area
    l, t, r, b = d.textbbox((0, 0), text, font=script, anchor="lt")
    d.text(((W - (r - l)) / 2 - l, (1300 - (b - t)) / 2 - t + 60), text,
           font=script, fill=fill, anchor="lt")

    # 2) Divider line with heart
    line_y, heart_size, gap, half = 1420, 150, 140, 900
    d.line([(W / 2 - half, line_y), (W / 2 - gap, line_y)], fill=fill, width=12)
    d.line([(W / 2 + gap, line_y), (W / 2 + half, line_y)], fill=fill, width=12)
    d.polygon(heart_polygon(W / 2, line_y, heart_size), fill=fill)

    # 3) Roman-numeral date, letter-spaced serif caps
    rd = roman_date(date, fmt)
    size = 300
    font = serif(size)
    # shrink if a long date would overflow the canvas
    while True:
        widths = sum(d.textlength(ch, font=font) for ch in rd) + 40 * (len(rd) - 1)
        if widths <= W * 0.85 or size <= 120:
            break
        size -= 10
        font = serif(size)
    draw_spaced(d, rd, font, 1830, fill, tracking=40)

    img.save(out_path, dpi=(300, 300))
    return rd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--initials", nargs=2, required=True, metavar=("FIRST", "SECOND"))
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--format", default="mdy", choices=["mdy", "dmy", "ymd"],
                   help="order of the Roman numerals (default month-day-year, US style)")
    p.add_argument("--color", default="black", choices=list(COLORS))
    p.add_argument("--out", default=None)
    a = p.parse_args()

    date = dt.date.fromisoformat(a.date)
    initials = [s.strip().upper()[:1] for s in a.initials]
    out = a.out or os.path.join(
        HERE, "output", f"{initials[0]}{initials[1]}_{a.date}_{a.color}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rd = make(initials, date, a.format, a.color, out)
    print(f"Saved {out}  ({rd})")


if __name__ == "__main__":
    main()
