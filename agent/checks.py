"""Checks a submitted article the way the site and its test suite will:
static rules first, then both versions are rendered by the real Flask app
(on a copy of content/) and run through the shared SEO audit."""

from __future__ import annotations

import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from app import create_app
from app.config import Config
from app.seo_audit import audit

from .files import existing_articles, write_articles
from .schema import Submission

BASE = "https://www.crosstechedu.com"
MIN_WORDS = {"vi": 800, "en": 700}
MAX_TITLE = 60  # Google cuts titles at ~60 characters


def _path(locale: str, slug: str = "") -> str:
    prefix = "" if locale == "vi" else f"/{locale}"
    return f"{prefix}/blog/{slug + '/' if slug else ''}"


def static_problems(sub: Submission, content_dir: Path) -> list[str]:
    problems: list[str] = []
    existing = existing_articles(content_dir)
    if any(a["translation_key"] == sub.translation_key for a in existing):
        problems.append(f"translation_key '{sub.translation_key}' is already used by another article")
    if sub.vi.slug == sub.en.slug:
        problems.append("the Vietnamese and English slugs must be different")

    for locale, d in sub.drafts().items():
        tag = f"[{locale}]"
        if any(a["locale"] == locale and a["slug"] == d.slug for a in existing):
            problems.append(f"{tag} slug '{d.slug}' already exists")
        if len(d.title) > MAX_TITLE:
            problems.append(f"{tag} title is {len(d.title)} characters; keep it under {MAX_TITLE} (ideally 48)")
        if not 70 <= len(d.description) <= 160:
            problems.append(f"{tag} description is {len(d.description)} characters; it must be 70-160 (aim for 120-155)")
        if re.search(r"^#\s", d.body, re.M):
            problems.append(f"{tag} body contains a '# ' H1 line; the title is already the H1, start sections at '## '")
        if len(re.findall(r"^##\s", d.body, re.M)) < 3:
            problems.append(f"{tag} body needs at least 3 '## ' sections")
        words = len(d.body.split())
        if words < MIN_WORDS[locale]:
            problems.append(f"{tag} body has {words} words; write at least {MIN_WORDS[locale]}")
        if re.search(r"<script|<iframe|<style", d.body, re.I):
            problems.append(f"{tag} body must not contain <script>, <iframe> or <style>")
        for href in re.findall(r"\]\(([^)\s]+)", d.body):
            if href.startswith("http://"):
                problems.append(f"{tag} use https:// links, not {href}")
            if locale == "en" and href.startswith("/blog/"):
                problems.append(f"{tag} link {href} points to the Vietnamese blog; use /en{href}")
            if locale == "vi" and href.startswith("/en/"):
                problems.append(f"{tag} link {href} points to the English site from the Vietnamese article")
    return problems


def render_problems(sub: Submission, content_dir: Path) -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "content"
        shutil.copytree(content_dir, root)
        write_articles(sub, root, date.today())

        class DraftConfig(Config):
            TESTING = True
            SITE_URL = BASE
            CONTENT_DIR = root

        client = create_app(DraftConfig).test_client()
        for locale, d in sub.drafts().items():
            tag = f"[{locale}]"
            for path in (_path(locale, d.slug), _path(locale)):
                r = client.get(path)
                if r.status_code != 200:
                    problems.append(f"{tag} {path} returned HTTP {r.status_code}")
                    continue
                page = r.get_data(as_text=True)
                for p in audit(page, BASE + path, locale):
                    problems.append(f"{tag} {path}: {p}")
                title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
                if not 30 <= len(title) <= 65:
                    problems.append(f"{tag} {path}: <title> '{title}' is {len(title)} characters (needs 30-65)")

            page = client.get(_path(locale, d.slug)).get_data(as_text=True)
            start, end = page.find('<div class="prose">'), page.find('<aside class="article__cta"')
            if start < 0 or end < 0:
                problems.append(f"{tag} the article body did not render; check the Markdown for unclosed HTML")
                continue
            prose = page[start:end]
            for href in re.findall(r'href="(/[^"#]*)', prose):
                if client.get(href).status_code != 200:
                    problems.append(f"{tag} internal link {href} does not exist on the site")
    return problems


def check(sub: Submission, content_dir: Path) -> list[str]:
    problems = static_problems(sub, content_dir)
    # Rendering with a duplicate slug would just overwrite the existing article.
    if any("already" in p for p in problems):
        return problems
    return problems + render_problems(sub, content_dir)
