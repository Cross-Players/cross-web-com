"""Crawl each product's App Store listing (iTunes Lookup API) and build web assets:

    app/static/img/products/<key>-icon.webp    128×128 app icon
    app/static/img/products/<key>-cover.webp   960×480 banner of 3 real screenshots

Re-run whenever a product is added or its store listing changes:

    .venv/bin/python scripts/fetch_store_assets.py
"""

from __future__ import annotations

import io
import json
import re
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "img" / "products"

# key -> (App Store id, storefront). The key is referenced from content JSON.
PRODUCTS = {
    "vinwonders": ("1590471592", "vn"),
    "gmo-owner": ("1531075216", "jp"),
    "gmo-resident": ("1548615608", "jp"),
    "ezrx": ("6450109562", "vn"),
}

UA = {"User-Agent": "Mozilla/5.0 (cross-outsourcing asset builder)"}
COVER_W, COVER_H = 960, 480


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def lookup(app_id: str, country: str) -> dict:
    data = json.loads(fetch(f"https://itunes.apple.com/lookup?id={app_id}&country={country}"))
    if not data["results"]:
        raise SystemExit(f"App {app_id} not found in the {country} store")
    return data["results"][0]


def sized(url: str, spec: str) -> str:
    """mzstatic URLs end in /<w>x<h>bb.<ext>; swap in the size we want."""
    return re.sub(r"/[^/]+$", "/" + spec, url)


def image(url: str) -> Image.Image:
    return Image.open(io.BytesIO(fetch(url))).convert("RGB")


def build_cover(shots: list[Image.Image]) -> Image.Image:
    # Background = the first screenshot's own colours, blurred, so each banner
    # carries the product's brand palette.
    bg = shots[0].resize((COVER_W, int(COVER_W * shots[0].height / shots[0].width)))
    bg = bg.crop((0, 0, COVER_W, COVER_H)).filter(ImageFilter.GaussianBlur(40))
    cover = Image.new("RGB", (COVER_W, COVER_H))
    cover.paste(bg)

    phone_h = 600  # taller than the banner: phones bleed off the bottom edge
    gap = 28
    phones = [s.resize((round(s.width * phone_h / s.height), phone_h), Image.LANCZOS) for s in shots]
    total = sum(p.width for p in phones) + gap * (len(phones) - 1)
    x = (COVER_W - total) // 2
    for i, p in enumerate(phones):
        y = 48 if i == 1 else 88  # middle phone sits higher
        mask = Image.new("L", p.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, p.width - 1, p.height - 1], radius=22, fill=255)
        shadow = Image.new("L", (p.width + 40, p.height + 40), 0)
        ImageDraw.Draw(shadow).rounded_rectangle([20, 24, p.width + 20, p.height + 24], radius=22, fill=90)
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        cover.paste((0, 0, 0), (x - 20, y - 20), shadow)
        cover.paste(p, (x, y), mask)
        x += p.width + gap
    return cover


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, (app_id, country) in PRODUCTS.items():
        info = lookup(app_id, country)
        icon = image(sized(info["artworkUrl512"], "256x256bb.png")).resize((128, 128), Image.LANCZOS)
        icon.save(OUT / f"{key}-icon.webp", "WEBP", quality=90, method=6)

        shots = [image(sized(u, "450x0w.jpg")) for u in info["screenshotUrls"][:3]]
        build_cover(shots).save(OUT / f"{key}-cover.webp", "WEBP", quality=80, method=6)
        sizes = {p.name: p.stat().st_size // 1024 for p in OUT.glob(f"{key}-*.webp")}
        print(f"{key:14} {info['trackName']}  {sizes} KB")


if __name__ == "__main__":
    main()
