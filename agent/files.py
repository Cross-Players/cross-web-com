"""Article JSON files, byte-for-byte in the format the CMS exporter writes
(cms/blog/exporter.py), so `manage.py import_articles` round-trips them."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .schema import Draft, Submission

AUTHOR = "Cross Tech Edu"


def article_json(draft: Draft, translation_key: str, published: date) -> str:
    data = {
        "slug": draft.slug,
        "translation_key": translation_key,
        "title": draft.title.strip(),
        "description": draft.description.strip(),
        "published": published.isoformat(),
        "updated": published.isoformat(),
        "author": AUTHOR,
        "cover": None,
        "cover_alt": "",
        "body": draft.body.replace("\r\n", "\n").strip() + "\n",
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def article_path(content_dir: Path, locale: str, slug: str) -> Path:
    return Path(content_dir) / locale / "articles" / f"{slug}.json"


def write_articles(submission: Submission, content_dir: Path, published: date) -> list[Path]:
    paths = []
    for locale, draft in submission.drafts().items():
        path = article_path(content_dir, locale, draft.slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(article_json(draft, submission.translation_key, published), encoding="utf-8")
        paths.append(path)
    return paths


def existing_articles(content_dir: Path) -> list[dict]:
    """[{locale, slug, translation_key, title, description}] for every article."""
    out = []
    for f in sorted(Path(content_dir).glob("*/articles/*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        out.append(
            {
                "locale": f.parent.parent.name,
                "slug": raw["slug"],
                "translation_key": raw.get("translation_key") or raw["slug"],
                "title": raw["title"],
                "description": raw.get("description", ""),
            }
        )
    return out
