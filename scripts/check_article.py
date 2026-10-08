"""Site-side checks for new blog articles, run by the article-writing agent
(../writer_agent) before it opens a Pull Request.

Contract (shared by every site the agent writes for):

    python scripts/check_article.py content/vi/articles/<slug>.json [...]

Run from the repository root, with the article files already in content/.
Prints {"problems": [...]} as JSON on stdout. An empty list means the
articles render and pass the same SEO audit as the test suite
(app/seo_audit.py). A non-zero exit means the checker itself failed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.seo_audit import audit  # noqa: E402

BASE = "https://www.crosstechedu.com"


def _blog_path(locale: str, slug: str = "") -> str:
    prefix = "" if locale == Config.DEFAULT_LOCALE else f"/{locale}"
    return f"{prefix}/blog/{slug + '/' if slug else ''}"


def check(article_files: list[str], content_dir: Path) -> list[str]:
    class SiteConfig(Config):
        TESTING = True
        SITE_URL = BASE
        CONTENT_DIR = content_dir

    client = create_app(SiteConfig).test_client()
    problems: list[str] = []
    for name in article_files:
        path = Path(name)
        locale = path.parent.parent.name
        tag = f"[{locale}]"
        if path.parent.name != "articles" or locale not in Config.LOCALES:
            problems.append(f"{name}: not an article file (expected content/<locale>/articles/<slug>.json)")
            continue
        try:
            slug = json.loads((content_dir.parent / path).read_text(encoding="utf-8"))["slug"]
        except (OSError, ValueError, KeyError) as e:
            problems.append(f"{name}: unreadable article file ({e})")
            continue
        if slug != path.stem:
            problems.append(f"{tag} slug '{slug}' does not match the file name {path.name}")

        for url in (_blog_path(locale, slug), _blog_path(locale)):
            r = client.get(url)
            if r.status_code != 200:
                problems.append(f"{tag} {url} returned HTTP {r.status_code}")
                continue
            page = r.get_data(as_text=True)
            problems += [f"{tag} {url}: {p}" for p in audit(page, BASE + url, locale)]
            title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
            if not 30 <= len(title) <= 65:
                problems.append(f"{tag} {url}: <title> '{title}' is {len(title)} characters (needs 30-65)")
            desc = re.search(r'<meta name="description" content="(.*?)">', page).group(1)
            if not 70 <= len(desc) <= 160:
                problems.append(f"{tag} {url}: description is {len(desc)} characters (needs 70-160)")

        page = client.get(_blog_path(locale, slug)).get_data(as_text=True)
        start, end = page.find('<div class="prose">'), page.find('<aside class="article__cta"')
        if start < 0 or end < 0:
            problems.append(f"{tag} the article body did not render; check the Markdown for unclosed HTML")
            continue
        for href in re.findall(r'href="(/[^"#]*)', page[start:end]):
            if client.get(href).status_code != 200:
                problems.append(f"{tag} internal link {href} does not exist on the site")
    return problems


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print(json.dumps({"problems": check(sys.argv[1:], ROOT / "content")}, ensure_ascii=False))
