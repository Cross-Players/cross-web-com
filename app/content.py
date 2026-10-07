"""Content layer.

Views never read files directly: they ask a ``ContentRepository``. Today the
content lives in JSON files under ``content/``; moving to a headless CMS
(Strapi, Directus, Wagtail, Sanity...) means writing one more class that
implements the same three methods and returns the same shapes.

Page shape (identical to a Strapi "dynamic zone" or a Wagtail StreamField)::

    {
      "slug": "",                      # "" = home, otherwise "about", "blog/x"...
      "translation_key": "home",       # links a page to its other-language versions
      "meta": {"title": ..., "description": ..., "og_image": ...},
      "blocks": [{"type": "hero", "data": {...}}, ...]
    }

Every block ``type`` has a matching template in ``templates/blocks/<type>.html``.

Blog articles live next to the pages, one JSON file each, in
``content/<locale>/articles/<slug>.json``. They are written by the Django
admin in ``cms/`` (or by hand) and have this shape::

    {
      "slug": "cong-cu-ai-mien-phi",
      "translation_key": "free-ai-tools",   # same value on the VI and EN version
      "title": ..., "description": ...,
      "published": "2026-10-06", "updated": "2026-10-06",
      "author": "Cross Tech Edu",
      "cover": "img/articles/x.webp" | null, "cover_alt": "...",
      "body": "Markdown text"
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Block:
    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class Page:
    locale: str
    slug: str
    translation_key: str
    meta: dict[str, Any]
    blocks: list[Block] = field(default_factory=list)

    def block(self, type_: str) -> Block | None:
        return next((b for b in self.blocks if b.type == type_), None)


@dataclass(frozen=True)
class Article:
    locale: str
    slug: str
    translation_key: str
    title: str
    description: str
    body: str  # Markdown
    published: str  # ISO date
    updated: str
    author: str = ""
    cover: str | None = None
    cover_alt: str = ""

    @property
    def reading_minutes(self) -> int:
        return max(1, round(len(self.body.split()) / 200))


class ContentRepository(Protocol):
    def get_site(self, locale: str) -> dict[str, Any]:
        """Global settings (brand, contact) merged with per-locale chrome (nav, footer)."""

    def get_page(self, locale: str, slug: str) -> Page | None:
        """A single page, or None when it does not exist in that locale."""

    def list_pages(self, locale: str) -> list[Page]:
        """Every published page in a locale (feeds the sitemap and static export)."""

    def list_articles(self, locale: str) -> list[Article]:
        """Every published blog article in a locale, newest first."""

    def get_article(self, locale: str, slug: str) -> Article | None:
        """A single article, or None when it does not exist in that locale."""


class JsonFileRepository:
    """Reads ``content/site.json``, ``content/<locale>/site.json`` and
    ``content/<locale>/pages/*.json`` and ``content/<locale>/articles/*.json``."""

    def __init__(self, root: Path, cache: bool = True):
        self.root = Path(root)
        self._load = lru_cache(maxsize=None)(self._read) if cache else self._read

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def get_site(self, locale: str) -> dict[str, Any]:
        site = dict(self._load(self.root / "site.json"))
        site.update(self._load(self.root / locale / "site.json"))
        return site

    def _page_files(self, locale: str) -> list[Path]:
        return sorted((self.root / locale / "pages").glob("*.json"))

    def _to_page(self, locale: str, raw: dict[str, Any]) -> Page:
        return Page(
            locale=locale,
            slug=raw.get("slug", ""),
            translation_key=raw["translation_key"],
            meta=raw.get("meta", {}),
            blocks=[Block(b["type"], b.get("data", {})) for b in raw.get("blocks", [])],
        )

    def list_pages(self, locale: str) -> list[Page]:
        return [self._to_page(locale, self._load(p)) for p in self._page_files(locale)]

    def get_page(self, locale: str, slug: str) -> Page | None:
        slug = slug.strip("/")
        return next((p for p in self.list_pages(locale) if p.slug == slug), None)


    def list_articles(self, locale: str) -> list[Article]:
        files = sorted((self.root / locale / "articles").glob("*.json"))
        articles = [self._to_article(locale, self._load(p)) for p in files]
        return sorted(articles, key=lambda a: (a.published, a.slug), reverse=True)

    def get_article(self, locale: str, slug: str) -> Article | None:
        return next((a for a in self.list_articles(locale) if a.slug == slug), None)

    @staticmethod
    def _to_article(locale: str, raw: dict[str, Any]) -> Article:
        return Article(
            locale=locale,
            slug=raw["slug"],
            translation_key=raw.get("translation_key") or raw["slug"],
            title=raw["title"],
            description=raw.get("description", ""),
            body=raw.get("body", ""),
            published=raw["published"],
            updated=raw.get("updated") or raw["published"],
            author=raw.get("author", ""),
            cover=raw.get("cover") or None,
            cover_alt=raw.get("cover_alt", ""),
        )


def make_repository(config: dict[str, Any]) -> ContentRepository:
    backend = config["CONTENT_BACKEND"]
    if backend == "json":
        return JsonFileRepository(config["CONTENT_DIR"], cache=not config.get("DEBUG"))
    # e.g. elif backend == "strapi": return StrapiRepository(config["STRAPI_URL"], ...)
    raise ValueError(f"Unknown CONTENT_BACKEND: {backend!r}")
