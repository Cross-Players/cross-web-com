import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.seo_audit import audit

BASE = "https://example.test"
PRODUCT_PATH = "/san-pham/tro-ly-bds-43/"
PRIVACY_PATH = "/san-pham/tro-ly-bds-43/privacy-policy/"

VI_TOOLS = "/blog/cong-cu-ai-mien-phi-cho-doanh-nghiep-nho/"
VI_GUIDE = "/blog/huong-dan-dung-chatgpt-cho-chu-doanh-nghiep/"
EN_TOOLS = "/en/blog/free-ai-tools-for-small-business/"
EN_GUIDE = "/en/blog/chatgpt-guide-for-small-business-owners/"


def _article_paths() -> tuple[str, ...]:
    """Every article in content/, so new posts (e.g. from the writing agent)
    automatically go through the SEO, rendering and link checks."""
    content = Path(__file__).resolve().parent.parent / "content"
    paths = []
    for f in sorted(content.glob("*/articles/*.json")):
        locale = f.parent.parent.name
        paths.append(("" if locale == "vi" else f"/{locale}") + f"/blog/{f.stem}/")
    return tuple(paths)


ARTICLE_PATHS = _article_paths()
BLOG_PATHS = ("/blog/", "/en/blog/", *ARTICLE_PATHS)


def _jsonld(html: str) -> dict:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert m, "JSON-LD missing"
    return json.loads(m.group(1))


@pytest.mark.parametrize(
    "path,lang,h1",
    [
        ("/", "vi", "Đội ngũ kỹ thuật của bạn, đặt tại Việt Nam."),
        ("/en/", "en", "Your engineering team, based in Vietnam."),
    ],
)
def test_home_pages(client, path, lang, h1):
    r = client.get(path)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f'<html lang="{lang}">' in html
    assert html.count("<h1") == 1 and h1 in html
    assert f'<link rel="canonical" href="{BASE}{path}">' in html
    assert f'hreflang="vi" href="{BASE}/"' in html
    assert f'hreflang="en" href="{BASE}/en/"' in html
    assert f'hreflang="x-default" href="{BASE}/"' in html
    assert '<meta name="description"' in html
    assert 'property="og:image"' in html
    for section in ("services", "pricing", "work", "process", "contact"):
        assert f'id="{section}"' in html
    # no client-side JS needed at all
    assert "<script src" not in html


def test_titles_and_descriptions_are_seo_sized(client):
    for path in ("/", "/en/", PRODUCT_PATH):
        html = client.get(path).get_data(as_text=True)
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        desc = re.search(r'<meta name="description" content="(.*?)">', html).group(1)
        assert 30 <= len(title) <= 65, title
        assert 70 <= len(desc) <= 160, desc


def test_jsonld(client):
    data = _jsonld(client.get("/").get_data(as_text=True))
    types = {n["@type"] for n in data["@graph"]}
    assert {"ProfessionalService", "WebSite", "WebPage"} <= types
    org = next(n for n in data["@graph"] if n["@type"] == "ProfessionalService")
    assert len(org["hasOfferCatalog"]["itemListElement"]) == 9
    specs = [o["priceSpecification"] for o in org["makesOffer"]]
    assert {"@type": "UnitPriceSpecification", "priceCurrency": "VND", "minPrice": 6000000, "unitText": "developer / month"} in specs
    assert any(s.get("minPrice") == 6000000 for s in specs)


def test_sitemap(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and r.mimetype == "application/xml"
    root = ET.fromstring(r.data)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in root.findall("s:url/s:loc", ns)]
    assert locs[0] == f"{BASE}/" and f"{BASE}/en/" in locs
    for path in BLOG_PATHS:
        assert BASE + path in locs, path
    assert BASE + PRODUCT_PATH in locs
    assert BASE + PRIVACY_PATH in locs
    assert len(locs) == 2 + len(BLOG_PATHS) + 2


def test_product_landing_page(client):
    r = client.get(PRODUCT_PATH)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count("<h1") == 1 and "Trợ lý AI bất động sản Đà Nẵng" in html
    web = "https://www.danangluxuryhomes.vn/chatbot/project/camellia"
    fanpage = "https://www.facebook.com/profile.php?id=61594769476959"
    for url in (web, fanpage):
        # hero CTA + channel card, both opening in a new tab
        assert html.count(f'href="{url}" target="_blank" rel="noopener"') == 2, url
    assert f'href="{PRIVACY_PATH}"' in html
    # product features are not company services: no OfferCatalog in JSON-LD
    org = next(n for n in _jsonld(html)["@graph"] if n["@type"] == "ProfessionalService")
    assert "hasOfferCatalog" not in org


def test_robots(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    assert f"Sitemap: {BASE}/sitemap.xml" in body


def test_404(client):
    r = client.get("/khong-ton-tai/")
    assert r.status_code == 404
    assert 'name="robots" content="noindex"' in r.get_data(as_text=True)
    assert client.get("/en/nope/").status_code == 404


def test_static_assets_exist(client):
    html = client.get("/").get_data(as_text=True)
    urls = set(re.findall(r'(?:src|href)="(/static/[^"?]+)', html))
    urls |= set(re.findall(r"url\('(/static/[^']+)'\)", html))
    assert urls, "no static assets referenced"
    for url in urls:
        assert client.get(url).status_code == 200, url


def test_language_switch_links(client):
    vi = client.get("/").get_data(as_text=True)
    en = client.get("/en/").get_data(as_text=True)
    assert 'href="/en/" hreflang="en"' in vi
    assert 'href="/" hreflang="vi"' in en


def test_css_minifier_keeps_descendant_pseudo_classes(client):
    html = client.get("/").get_data(as_text=True)
    assert ".contact :focus-visible" in html


@pytest.mark.parametrize("path", ["/", "/en/"])
def test_client_logos_link_out(client, path):
    html = client.get(path).get_data(as_text=True)
    section = html[html.index('id="clients"'):]
    section = section[: section.index("</section>")]
    # section sits right after case studies
    assert html.index('id="work"') < html.index('id="clients"') < html.index('id="process"')
    urls = ("https://twendeesoft.com/", "https://jvb-corp.com/vi/", "https://ited.edu.vn/",
            "https://vfastsoft.com/", "https://itviec.com/companies/bfast-system")
    for url in urls:
        # exactly one real link per client; the carousel copies are not links
        assert section.count(f'<a class="logo-card') >= 1
        assert section.count(f'href="{url}" target="_blank" rel="noopener"') == 1
        assert section.count(f'data-href="{url}"') >= 1
    assert section.count('class="marquee__track" aria-hidden="true"') == 1


@pytest.mark.parametrize(
    "path,title", [("/", "Sản phẩm chúng tôi đã tham gia"), ("/en/", "Products we have worked on")]
)
def test_product_flip_cards(client, path, title):
    html = client.get(path).get_data(as_text=True)
    section = html[html.index('id="work"'):]
    section = section[: section.index("</section>")]
    assert title in section
    assert section.count('class="product__toggle" type="checkbox"') == 4
    # each card: front face -> App Store, back face -> Google Play
    fronts = re.findall(r'product__face--front">\s*<a class="product__link" href="([^"]+)"', section)
    backs = re.findall(r'product__face--back">\s*<a class="product__link" href="([^"]+)"', section)
    assert len(fronts) == len(backs) == 4
    assert all(u.startswith("https://apps.apple.com/") for u in fronts)
    assert all(u.startswith("https://play.google.com/store/apps/details?id=") for u in backs)
    assert "com.vinwonders.app" in backs[0] and "id1590471592" in fronts[0]


@pytest.mark.parametrize("path", ["/", "/en/"])
def test_contact_details(client, path):
    html = client.get(path).get_data(as_text=True)
    contact = html[html.index('id="contact"'):]
    contact = contact[: contact.index("</section>")]
    assert 'href="mailto:crosstechedu@gmail.com"' in contact
    assert 'href="tel:+84338305895"' in contact
    assert contact.count('href="https://zalo.me/3402955950888745400" target="_blank" rel="noopener"') == 1
    assert "zalo-qr.png" in contact


def test_prices_are_localized(client):
    """vi: every price in đ (rate 26,000 đ/USD). en: every price in USD."""
    vi = client.get("/").get_data(as_text=True)
    en = client.get("/en/").get_data(as_text=True)
    plus = '<sup class="tier__plus">+</sup>'
    assert f'<span class="tier__amount">999.000</span><span class="tier__currency">đ</span>' in vi
    for n in ("6", "16", "36", "30"):  # dev tiers + web/mobile packages: "6⁺ triệu đ"
        assert f'<span class="tier__amount">{n}{plus} triệu</span><span class="tier__currency">đ</span>' in vi
    assert f'<span class="tier__amount">39</span><span class="tier__currency">USD</span>' in en
    for n in ("300", "600", "1200", "230", "1,150"):
        assert f'<span class="tier__amount">{n}{plus}</span><span class="tier__currency">USD</span>' in en
    visible_vi = vi.split("</script>", 1)[1]
    visible_en = en.split("</script>", 1)[1]
    assert "USD" not in visible_vi
    assert "₫" not in visible_en and "VND" not in visible_en and "triệu" not in visible_en

    def specs(html):
        org = next(n for n in _jsonld(html)["@graph"] if n["@type"] == "ProfessionalService")
        return [o["priceSpecification"] for o in org["makesOffer"]]

    assert all(s["priceCurrency"] == "VND" for s in specs(vi))
    assert all(s["priceCurrency"] == "USD" for s in specs(en))
    assert {"@type": "UnitPriceSpecification", "priceCurrency": "VND", "price": 999000} in specs(vi)


@pytest.mark.parametrize("path", ["/", "/en/", PRODUCT_PATH, *BLOG_PATHS])
def test_on_page_seo_audit(client, path):
    """Mirrors the checks of the external SEO audit (rules live in app/seo_audit.py)."""
    page = client.get(path).get_data(as_text=True)
    assert audit(page, BASE + path, "en" if path.startswith("/en/") else "vi") == []

    # social profiles + share buttons
    for url in ("facebook.com/profile.php?id=61578180279419", "x.com/CrossTechEdu", "linkedin.com/company/cross-tech-edu"):
        assert url in page
    assert page.count('class="share-btn"') == 3
