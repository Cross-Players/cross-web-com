"""Writes articles to ``content/<locale>/articles/<slug>.json`` for the Flask
site (see ``app/content.py`` for the format). Only published articles get a
file; drafts and deleted articles have theirs removed."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from django.conf import settings


def article_path(locale: str, slug: str) -> Path:
    return Path(settings.CONTENT_DIR) / locale / "articles" / f"{slug}.json"


def to_dict(article) -> dict:
    return {
        "slug": article.slug,
        "translation_key": article.translation_key,
        "title": article.title,
        "description": article.description,
        "published": article.published_at.isoformat(),
        "updated": (article.updated_at or article.published_at).isoformat(),
        "author": article.author,
        "cover": article.cover.name or None,
        "cover_alt": article.cover_alt,
        "body": article.body,
    }


def export(article) -> None:
    path = article_path(article.locale, article.slug)
    if not article.is_published:
        remove(article.locale, article.slug)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(to_dict(article), ensure_ascii=False, indent=2) + "\n"
    # Write to a temp file and rename, so the site never reads half a file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def remove(locale: str, slug: str) -> None:
    article_path(locale, slug).unlink(missing_ok=True)
