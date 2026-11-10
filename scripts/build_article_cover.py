"""Generate a 1200x630 JPEG article cover image.

Reuses the font/palette approach from scripts/build_assets.py:
- FallbackFont across Archivo woff2 subsets (latin, latin-ext, vietnamese)
- Palette hexes from app/static/css/tokens.css

CLI: python scripts/build_article_cover.py --title "..." --kicker "..." --out out.jpg

Quality is tuned so the output stays under 120 KB.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"

BG = (243, 242, 242)        # --color-bg
TEXT = (32, 30, 29)         # --color-text
ACCENT = (236, 48, 19)      # --color-accent
MUTED = (125, 121, 121)     # --color-neutral-600

SUBSETS = ["archivo-latin.woff2", "archivo-latin-ext.woff2", "archivo-vietnamese.woff2"]


class FallbackFont:
    def __init__(self, size: int, weight: int = 400):
        self.fonts = []
        for name in SUBSETS:
            path = STATIC / "fonts" / name
            cmap = set(TTFont(path).getBestCmap())
            font = ImageFont.truetype(str(path), size)
            try:
                axes = font.get_variation_axes()
                font.set_variation_by_axes(
                    [weight if a["name"] in (b"Weight", "Weight") else a["default"] for a in axes]
                )
            except OSError:
                pass
            self.fonts.append((cmap, font))

    def _font_for(self, ch: str):
        for cmap, font in self.fonts:
            if ord(ch) in cmap:
                return font
        return self.fonts[0][1]

    def width(self, text: str) -> float:
        return sum(self._font_for(c).getlength(c) for c in text)

    def draw(self, d: ImageDraw.ImageDraw, xy, text: str, fill) -> float:
        x, y = xy
        for c in text:
            f = self._font_for(c)
            d.text((x, y), c, font=f, fill=fill, anchor="ls")
            x += f.getlength(c)
        return x


def wrap(font: FallbackFont, text: str, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.width(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur]


def build_cover(title: str, kicker: str, out: Path, quality: int = 85) -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 64

    # Accent rule at top
    d.rectangle([0, 0, W, 10], fill=ACCENT)

    # Kicker
    kicker_font = FallbackFont(22, weight=700)
    lines = wrap(kicker_font, kicker, W - 2 * pad)
    y = pad + 40
    for line in lines:
        kicker_font.draw(d, (pad, y), line, MUTED)
        y += 30

    # Title
    title_font = FallbackFont(44, weight=800)
    title_lines = wrap(title_font, title, W - 2 * pad)
    y += 20
    for line in title_lines:
        title_font.draw(d, (pad, y), line, TEXT)
        y += 62

    # Footer
    footer_font = FallbackFont(20, weight=600)
    footer = "CROSS TECH EDU · crosstechedu.com"
    footer_font.draw(d, (pad, H - pad - 10), footer, MUTED)

    # Save as JPEG, tuning quality to stay under 120 KB
    buf = __import__("io").BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    size_kb = len(buf.getvalue()) // 1024
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    print(f"wrote {out} ({size_kb} KB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a 1200x630 JPEG article cover.")
    parser.add_argument("--title", required=True, help="Main cover title")
    parser.add_argument("--kicker", required=True, help="Small kicker line above the title")
    parser.add_argument("--out", required=True, help="Output JPEG path")
    args = parser.parse_args()
    build_cover(args.title, args.kicker, Path(args.out))
