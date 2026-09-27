"""Runtime configuration, read from environment variables.

Every value here can be overridden per deployment without touching code:

    SITE_URL=https://crossplayers.com CONTENT_DIR=/srv/content flask run
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    # Absolute public origin, used for canonical URLs, hreflang, sitemap and
    # JSON-LD. Must NOT end with a slash.
    # On Vercel, falls back to the project's production domain
    # (VERCEL_PROJECT_PRODUCTION_URL, e.g. "cross-web-com.vercel.app") until a
    # custom domain is configured through SITE_URL.
    SITE_URL = (
        os.environ.get("SITE_URL")
        or (
            "https://" + os.environ["VERCEL_PROJECT_PRODUCTION_URL"]
            if os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
            else "https://crossplayers.com"
        )
    ).rstrip("/")

    # Where the JSON content lives. Swap CONTENT_BACKEND to plug in a CMS.
    CONTENT_BACKEND = os.environ.get("CONTENT_BACKEND", "json")
    CONTENT_DIR = Path(os.environ.get("CONTENT_DIR", BASE_DIR / "content"))

    DEFAULT_LOCALE = "vi"
    LOCALES = ("vi", "en")

    # Static assets are fingerprinted (?v=<hash>), so they can be cached forever.
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60 * 24 * 365

    # Flask-Compress: gzip/brotli for HTML, CSS, SVG, XML.
    COMPRESS_MIMETYPES = [
        "text/html",
        "text/css",
        "text/xml",
        "application/xml",
        "application/json",
        "application/ld+json",
        "image/svg+xml",
        "text/plain",
    ]

    # Frozen-Flask (static export, see freeze.py)
    FREEZER_DESTINATION = str(BASE_DIR / "build")
    FREEZER_RELATIVE_URLS = False
    FREEZER_REMOVE_EXTRA_FILES = True


class TestConfig(Config):
    TESTING = True
    SITE_URL = "https://example.test"
