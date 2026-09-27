import json
import re
import xml.etree.ElementTree as ET

import pytest

BASE = "https://example.test"


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
    for path in ("/", "/en/"):
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
    assert locs == [f"{BASE}/", f"{BASE}/en/"]


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


@pytest.mark.parametrize("path", ["/", "/en/"])
def test_on_page_seo_audit(client, path):
    """Mirrors the checks of the external SEO audit."""
    import collections
    import html as H

    page = client.get(path).get_data(as_text=True)
    text = lambda t: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", t))).strip()

    # canonical + self-referencing hreflang
    canonical = re.search(r'rel="canonical" href="([^"]+)"', page).group(1)
    assert canonical == BASE + path
    assert f'hreflang="{"vi" if path == "/" else "en"}" href="{canonical}"' in page

    # every image has a non-empty alt
    imgs = re.findall(r"<img[^>]*>", page)
    assert imgs and not [i for i in imgs if not re.search(r'alt="[^"]+"', i)]

    # headings: no duplicates, sensible count
    heads = [text(t) for _, t in re.findall(r"<h([1-6])[^>]*>(.*?)</h\1>", page, re.S)]
    assert not [h for h, n in collections.Counter(heads).items() if n > 1], heads
    assert len(heads) <= 30

    # H1 words appear in the body copy
    h1 = text(re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S).group(1))
    body = text(page.split("</h1>", 1)[1])
    words = [w for w in re.findall(r"\w{4,}", h1.lower())]
    assert sum(w in body.lower() for w in words) >= len(words) - 1, words

    # links: unique anchor texts, no empty anchors, limited external links
    links = re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
    anchors = [text(t) or re.search(r'alt="([^"]*)"', t).group(1) for _, t in links]
    assert all(anchors)
    assert not [a for a, n in collections.Counter(anchors).items() if n > 1]
    external = [h for h, _ in links if h.startswith("http")]
    assert len(external) <= 20, len(external)

    # social profiles + share buttons
    for url in ("facebook.com/profile.php?id=61578180279419", "x.com/CrossTechEdu", "linkedin.com/company/cross-tech-edu"):
        assert url in page
    assert page.count('class="share-btn"') == 3
