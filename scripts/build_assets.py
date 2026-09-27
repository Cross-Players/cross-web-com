"""Generate raster brand assets from the design: OG/Twitter share image and
apple-touch-icon. Re-run after changing the logo or the headline.

    .venv/bin/python scripts/build_assets.py
"""

from __future__ import annotations

import io
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
LOGO = ROOT / "scripts" / "src" / "logo-x@hi.png"  # the X mark, cropped from the 1024px source

BG = (243, 242, 242)        # --color-bg
TEXT = (32, 30, 29)         # --color-text
ACCENT = (236, 48, 19)      # --color-accent
MUTED = (125, 121, 121)     # --color-neutral-600
RULE = (166, 165, 164)      # --color-divider flattened on --color-bg

# The web font is split into unicode-range subsets; draw each character with
# the first subset that contains it.
SUBSETS = ["archivo-latin.woff2", "archivo-latin-ext.woff2", "archivo-vietnamese.woff2"]


class FallbackFont:
    def __init__(self, size: int, weight: int):
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


OG_TEXT = {
    "vi": {
        "file": "og-image.png",
        "kicker": "SOFTWARE OUTSOURCING · HÀ NỘI, VIỆT NAM",
        "title": "Đội ngũ kỹ thuật của bạn, đặt tại Việt Nam.",
        "rate_label": "GIÁ THUÊ DEV",
        "rate_amount": "6",
        "rate_unit": "triệu đ / dev / tháng",
    },
    "en": {
        "file": "og-image-en.png",
        "kicker": "SOFTWARE OUTSOURCING · HANOI, VIETNAM",
        "title": "Your engineering team, based in Vietnam.",
        "rate_label": "DEVELOPER RATE",
        "rate_amount": "300",
        "rate_unit": "USD / dev / month",
    },
}
DOMAIN = "crossplayers.com"  # printed on the image: re-run this script if the domain changes


def og_image(t: dict[str, str]) -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 64

    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((10_000, 64))
    img.paste(logo, (pad, pad - 6), logo)
    word = FallbackFont(34, 800)
    x = word.draw(d, (pad + logo.width + 16, pad + 44), "CROSS TECH EDU", TEXT)
    word.draw(d, (x, pad + 44), ".", ACCENT)

    kicker = FallbackFont(20, 800)
    kicker.draw(d, (pad, 190), t["kicker"], ACCENT)

    title = FallbackFont(64, 800)
    y = 270
    for line in wrap(title, t["title"], 700):
        title.draw(d, (pad, y), line, TEXT)
        y += 72

    # right column: the price, as in the hero
    d.line([(820, 150), (820, H - 150)], fill=RULE, width=2)
    label = FallbackFont(18, 800)
    label.draw(d, (860, 250), t["rate_label"], MUTED)
    big = FallbackFont(140, 800)
    big.draw(d, (852, 390), t["rate_amount"], ACCENT)
    unit = FallbackFont(26, 800)
    unit.draw(d, (860, 436), t["rate_unit"], TEXT)

    d.rectangle([(0, H - 72), (W, H)], fill=ACCENT)
    foot = FallbackFont(22, 800)
    foot.draw(d, (pad, H - 28), "Web · Mobile · Backend · Cloud · AI", BG)
    foot.draw(d, (W - pad - foot.width(DOMAIN), H - 28), DOMAIN, BG)

    out = STATIC / "img" / t["file"]
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    out.write_bytes(buf.getvalue())
    print(f"wrote {out.relative_to(ROOT)} ({len(buf.getvalue()) // 1024} KB)")


def touch_icon() -> None:
    size = 180
    img = Image.new("RGB", (size, size), BG)
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((size - 36, size - 36))
    img.paste(logo, ((size - logo.width) // 2, (size - logo.height) // 2), logo)
    out = STATIC / "img" / "apple-touch-icon.png"
    img.save(out, "PNG", optimize=True)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    for texts in OG_TEXT.values():
        og_image(texts)
    touch_icon()
