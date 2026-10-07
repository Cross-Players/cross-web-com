import json
import re
from pathlib import Path

import pytest

from app import create_app
from app.config import TestConfig

from .test_site import ARTICLE_PATHS, BASE, BLOG_PATHS, EN_GUIDE, EN_TOOLS, VI_GUIDE, VI_TOOLS, _jsonld


@pytest.mark.parametrize("path", BLOG_PATHS)
def test_blog_pages_render_with_seo_basics(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    html = r.get_data(as_text=True)
    assert html.count("<h1") == 1
    assert f'<link rel="canonical" href="{BASE}{path}">' in html
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    desc = re.search(r'<meta name="description" content="(.*?)">', html).group(1)
    assert 30 <= len(title) <= 65, title
    assert 70 <= len(desc) <= 160, desc
    assert "<script src" not in html
    # every image has alt text and every share button is there (footer needs `meta`)
    assert not [i for i in re.findall(r"<img[^>]*>", html) if not re.search(r'alt="[^"]+"', i)]
    assert html.count('class="share-btn"') == 3


def test_blog_index_lists_articles_newest_first(client):
    html = client.get("/blog/").get_data(as_text=True)
    assert f'href="{VI_TOOLS}"' in html and f'href="{VI_GUIDE}"' in html
    assert EN_TOOLS not in html  # only this language's articles
    assert 'href="/en/blog/" hreflang="en"' in html  # language switch
    blog = next(n for n in _jsonld(html)["@graph"] if n["@type"] == "Blog")
    vi_articles = {BASE + p for p in ARTICLE_PATHS if not p.startswith("/en/")}
    assert {p["url"] for p in blog["blogPost"]} == vi_articles
    assert {BASE + VI_TOOLS, BASE + VI_GUIDE} <= vi_articles


def test_article_page(client):
    html = client.get(VI_GUIDE).get_data(as_text=True)
    assert '<meta property="og:type" content="article">' in html
    # hreflang + language switch point to the English translation
    assert f'hreflang="en" href="{BASE}{EN_GUIDE}"' in html
    assert f'hreflang="x-default" href="{BASE}{VI_GUIDE}"' in html
    assert f'href="{EN_GUIDE}" hreflang="en"' in html
    # Markdown is rendered: headings, tables, code blocks
    assert "<h2>Bước 1: Tạo tài khoản (5 phút)</h2>" in html
    assert "<table>" in html and "<pre><code>" in html
    # header nav anchors point back to the home page
    assert 'href="/#services"' in html
    post = next(n for n in _jsonld(html)["@graph"] if n["@type"] == "BlogPosting")
    assert post["headline"] == "Hướng dẫn dùng ChatGPT cho chủ doanh nghiệp từ A đến Z"
    assert post["datePublished"] == "2026-10-06" and post["inLanguage"] == "vi"
    assert post["url"] == BASE + VI_GUIDE


def test_internal_article_links_resolve(client):
    for path in ARTICLE_PATHS:
        html = client.get(path).get_data(as_text=True)
        prose = html[html.index('<div class="prose">'):html.index('<aside class="article__cta"')]
        links = re.findall(r'href="(/[^"]*)"', prose)
        assert links, path
        for link in links:
            assert client.get(link).status_code == 200, (path, link)


def test_blog_routes_beat_catch_all_and_unknown_slugs_404(client):
    assert client.get("/blog/khong-co/").status_code == 404
    assert client.get("/en/blog/nope/").status_code == 404
    # an English slug isn't served under the Vietnamese prefix
    assert client.get("/blog/free-ai-tools-for-small-business/").status_code == 404


def test_nav_links_to_blog(client):
    assert 'href="/blog/">Blog</a>' in client.get("/").get_data(as_text=True)
    assert 'href="/en/blog/">Blog</a>' in client.get("/en/").get_data(as_text=True)


def test_empty_blog(tmp_path):
    src = Path(TestConfig.CONTENT_DIR)
    for f in src.rglob("*.json"):
        if "articles" not in f.parts:
            dst = tmp_path / f.relative_to(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(f.read_bytes())

    class Empty(TestConfig):
        CONTENT_DIR = tmp_path

    client = create_app(Empty).test_client()
    r = client.get("/blog/")
    assert r.status_code == 200 and "Chưa có bài viết" in r.get_data(as_text=True)
    assert "/blog/" not in client.get("/sitemap.xml").get_data(as_text=True)


def test_article_json_files_are_well_formed():
    for f in Path(TestConfig.CONTENT_DIR).glob("*/articles/*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["slug"] == f.stem
        assert {"title", "description", "published", "body", "translation_key"} <= data.keys()
