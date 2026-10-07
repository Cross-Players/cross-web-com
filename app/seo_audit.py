"""On-page SEO audit, mirroring the external SEO audit the site was checked
against. Used by the test suite and by the article-writing agent (``agent/``),
so a new article must pass exactly the same rules as the existing pages."""

from __future__ import annotations

import collections
import html as H
import re


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def audit(page: str, url: str, locale: str) -> list[str]:
    """Problems found on a rendered page (empty list = passes).

    ``url`` is the page's absolute canonical URL, ``locale`` its language."""
    problems: list[str] = []

    m = re.search(r'rel="canonical" href="([^"]+)"', page)
    if not m or m.group(1) != url:
        problems.append(f"canonical should be {url}, found {m.group(1) if m else 'none'}")
    if f'hreflang="{locale}" href="{url}"' not in page:
        problems.append(f"missing self-referencing hreflang={locale}")

    imgs = re.findall(r"<img[^>]*>", page)
    no_alt = [i for i in imgs if not re.search(r'alt="[^"]+"', i)]
    if no_alt:
        problems.append(f"images without alt text: {no_alt}")

    heads = [_text(t) for _, t in re.findall(r"<h([1-6])[^>]*>(.*?)</h\1>", page, re.S)]
    dupes = [h for h, n in collections.Counter(heads).items() if n > 1]
    if dupes:
        problems.append(f"duplicate headings: {dupes}")
    if len(heads) > 30:
        problems.append(f"{len(heads)} headings on the page (max 30)")

    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    if len(h1s) != 1:
        problems.append(f"page has {len(h1s)} <h1> elements (needs exactly 1)")
    else:
        h1 = _text(h1s[0])
        body = _text(page.split("</h1>", 1)[1]).lower()
        words = re.findall(r"\w{4,}", h1.lower())
        missing = [w for w in words if w not in body]
        if len(missing) > 1:
            problems.append(f"words of the H1 missing from the body text: {missing}")

    links = re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
    anchors = []
    for href, inner in links:
        alt = re.search(r'alt="([^"]*)"', inner)
        anchors.append(_text(inner) or (alt.group(1) if alt else ""))
    empty = [href for (href, _), a in zip(links, anchors) if not a]
    if empty:
        problems.append(f"links without anchor text: {empty}")
    dupes = [a for a, n in collections.Counter(anchors).items() if n > 1 and a]
    if dupes:
        problems.append(f"the same link text is used more than once on the page: {dupes}")
    external = [h for h, _ in links if h.startswith("http")]
    if len(external) > 20:
        problems.append(f"{len(external)} external links on the page (max 20)")

    return problems
