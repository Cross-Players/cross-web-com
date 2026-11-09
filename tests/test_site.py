import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.seo_audit import audit

BASE = "https://example.test"
PRODUCT_PATH = "/san-pham/tro-ly-bds-43/"
PRIVACY_PATH = "/san-pham/tro-ly-bds-43/privacy-policy/"
GPLX_PATH = "/projects/gplx/"
GPLX_POLICY_PATH = "/projects/gplx/policy/"
GPLX_SUPPORT_PATH = "/projects/gplx/support/"
PROJECTS_PATH = "/projects/"
EN_PROJECTS_PATH = "/en/projects/"
FAMHUB_POLICY_PATH = "/projects/fam-hub/privacy/"
GPLX_STORE = "https://apps.apple.com/vn/app/driver-license-e-learning/id6751185396"
FAMHUB_PATH = "/projects/fam-hub/"
KIGO_PATH = "/projects/kigo/"
KIGO_POLICY_PATH = "/projects/kigo/privacy/"
TRONG_CAY_PATH = "/projects/plant-trees/"
TRONG_CAY_POLICY_PATH = "/projects/plant-trees/privacy/"
TRONG_CAY_SUPPORT_PATH = "/projects/plant-trees/support/"
FAST_NOTES_PATH = "/projects/fast-notes/"
FAST_NOTES_SUPPORT_PATH = "/projects/fast-notes/support/"
FAST_NOTES_PRIVACY_PATH = "/projects/fast-notes/privacy/"
FAST_NOTES_PRIVACY_VI_PATH = "/projects/fast-notes/chinh-sach-bao-mat/"
FAST_NOTES_TERMS_PATH = "/projects/fast-notes/terms/"
FAST_NOTES_TERMS_VI_PATH = "/projects/fast-notes/dieu-khoan/"
FAST_NOTES_PATHS = (FAST_NOTES_PATH, FAST_NOTES_SUPPORT_PATH, FAST_NOTES_PRIVACY_PATH, FAST_NOTES_PRIVACY_VI_PATH, FAST_NOTES_TERMS_PATH, FAST_NOTES_TERMS_VI_PATH)

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
    for path in ("/", "/en/", PRODUCT_PATH, GPLX_PATH, TRONG_CAY_PATH, PROJECTS_PATH, EN_PROJECTS_PATH):
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
    assert BASE + GPLX_PATH in locs
    assert BASE + GPLX_POLICY_PATH in locs
    assert BASE + FAMHUB_POLICY_PATH in locs
    repo = client.application.extensions["content"]
    extra_pages = sum(
        1 for loc in ("vi", "en")
        for p in repo.list_pages(loc)
        if p.slug
    )
    assert len(locs) == 2 + len(BLOG_PATHS) + extra_pages


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
    graph = {n["@type"]: n for n in _jsonld(html)["@graph"]}
    # product features are not company services: no OfferCatalog in JSON-LD
    assert "hasOfferCatalog" not in graph["ProfessionalService"]
    app = graph["WebApplication"]
    assert app["url"] == web and app["sameAs"] == [fanpage]
    assert graph["WebPage"]["about"] == {"@id": app["@id"]}
    crumbs = [(i["name"], i["item"]) for i in graph["BreadcrumbList"]["itemListElement"]]
    assert crumbs == [("Cross Tech Edu", f"{BASE}/"), ("Trợ lý AI bất động sản Đà Nẵng", BASE + PRODUCT_PATH)]


def test_product_page_is_linked(client):
    """Not an orphan: the VI footer links to it, and the privacy policy links back."""
    for path in ("/", "/blog/", PRIVACY_PATH):
        assert f'href="{PRODUCT_PATH}"' in client.get(path).get_data(as_text=True), path
    # /san-pham/ has no page, so the privacy breadcrumb skips it
    graph = _jsonld(client.get(PRIVACY_PATH).get_data(as_text=True))["@graph"]
    crumbs = next(n for n in graph if n["@type"] == "BreadcrumbList")["itemListElement"]
    assert [i["item"] for i in crumbs] == [f"{BASE}/", BASE + PRODUCT_PATH, BASE + PRIVACY_PATH]


def test_gplx_policy_page(client):
    """The App Store listing of Driver License E-learning links to this URL."""
    html = client.get(GPLX_POLICY_PATH).get_data(as_text=True)
    assert html.count("<h1") == 1
    # Vietnamese first, then the English version marked as such
    assert "không thu thập dữ liệu cá nhân" in html
    assert '<div lang="en">' in html and "does not collect personal data" in html
    assert "crosstechedu@gmail.com" in html


def test_famhub_policy_page(client):
    """The App Store listing and the app's Settings screen link to this URL."""
    html = client.get(FAMHUB_POLICY_PATH).get_data(as_text=True)
    assert html.count("<h1") == 1
    assert '<div lang="en">' in html and "<table>" in html
    assert "FamHub Privacy Policy" in html and "Kids Care" not in html
    assert "Cross Tech &amp; Edu" in html
    assert 'href="mailto:crosstechedu@gmail.com"' in html
    assert "not end-to-end encrypted" in html


def test_trong_cay_store_pages(client):
    """App Store Connect and Google Play link to these URLs."""
    policy = client.get(TRONG_CAY_POLICY_PATH).get_data(as_text=True)
    assert policy.count("<h1") == 1 and '<html lang="vi">' in policy
    assert "Google AdMob" in policy and "OpenTopoMap" in policy
    assert 'href="mailto:crosstechedu@gmail.com"' in policy
    support = client.get(TRONG_CAY_SUPPORT_PATH).get_data(as_text=True)
    assert support.count("<h1") == 1
    assert 'href="mailto:crosstechedu@gmail.com"' in support
    assert f'href="{TRONG_CAY_POLICY_PATH}"' in support


def test_fast_notes_store_pages(client):
    """App Store Connect and Google Play link to these URLs."""
    for path in FAST_NOTES_PATHS:
        html = client.get(path).get_data(as_text=True)
        assert html.count("<h1") == 1, path
        assert 'href="mailto:crosstechedu@gmail.com"' in html, path
    en = client.get(FAST_NOTES_PRIVACY_PATH).get_data(as_text=True)
    assert "Apple Intelligence" in en and "Gemini Nano" in en and "<table>" in en
    assert f'href="{FAST_NOTES_PRIVACY_VI_PATH}"' in en
    vi = client.get(FAST_NOTES_PRIVACY_VI_PATH).get_data(as_text=True)
    assert '<html lang="vi">' in vi and f'href="{FAST_NOTES_PRIVACY_PATH}"' in vi
    terms = client.get(FAST_NOTES_TERMS_PATH).get_data(as_text=True)
    assert "stdeula" in terms and "3 months" in terms
    assert f'href="{FAST_NOTES_PRIVACY_VI_PATH}"' in client.get(FAST_NOTES_PATH).get_data(as_text=True)
    assert f'href="{FAST_NOTES_PRIVACY_PATH}"' in client.get(FAST_NOTES_SUPPORT_PATH).get_data(as_text=True)


def test_trong_cay_landing_page(client):
    html = client.get(TRONG_CAY_PATH).get_data(as_text=True)
    assert html.count("<h1") == 1 and '<html lang="vi">' in html
    assert html.count('class="shot"') == 5
    assert f'href="{TRONG_CAY_POLICY_PATH}"' in html and f'href="{TRONG_CAY_SUPPORT_PATH}"' in html
    # no real trees yet, and not on the stores yet
    assert "chưa có cây thật nào được trồng" in html
    assert "apps.apple.com" not in html and "play.google.com" not in html
    graph = {n["@type"]: n for n in _jsonld(html)["@graph"]}
    assert graph["MobileApplication"]["alternateName"] == "Plant Trees"
    assert "offers" not in graph["MobileApplication"]
    crumbs = [i["item"] for i in graph["BreadcrumbList"]["itemListElement"]]
    assert crumbs == [f"{BASE}/", BASE + PROJECTS_PATH, BASE + TRONG_CAY_PATH]


def test_kigo_policy_page(client):
    """Vietnamese version of the FamHub policy, under the app's Vietnamese name."""
    html = client.get(KIGO_POLICY_PATH).get_data(as_text=True)
    assert html.count("<h1") == 1
    assert '<html lang="vi">' in html and '<div lang="en">' not in html
    assert "Chính sách quyền riêng tư ứng dụng Kigo" in html and "Kids Care" not in html
    assert "<table>" in html and "Vị trí chính xác của trẻ" in html
    assert "không được mã hoá đầu cuối" in html
    assert "Singapore (asia-southeast1)" in html and "60 phút" in html
    assert f'href="{FAMHUB_POLICY_PATH}"' in html
    assert 'href="mailto:crosstechedu@gmail.com"' in html
    assert client.get("/projects/fam-hub/privacy/vi/").status_code == 404


@pytest.mark.parametrize(
    "path,lang,other,name,other_name,policy",
    [
        (FAMHUB_PATH, "en", KIGO_PATH, "FamHub", "Kigo", FAMHUB_POLICY_PATH),
        (KIGO_PATH, "vi", FAMHUB_PATH, "Kigo", "FamHub", KIGO_POLICY_PATH),
    ],
)
def test_app_marketing_pages(client, path, lang, other, name, other_name, policy):
    """One app, two market names: each page is the other's language version."""
    html = client.get(path).get_data(as_text=True)
    assert f'<html lang="{lang}">' in html
    assert html.count("<h1") == 1 and name in html
    assert html.count('class="shot"') == 6
    assert "img/products/famhub/01_parent-home.webp" in html
    assert f'href="{policy}"' in html
    assert f'hreflang="{"vi" if lang == "en" else "en"}" href="{BASE}{other}"' in html
    # not on the stores yet: no download link, no price claim, no old name
    assert "apps.apple.com" not in html and "play.google.com" not in html
    assert "Kids Care" not in html
    graph = {n["@type"]: n for n in _jsonld(html)["@graph"]}
    assert graph["MobileApplication"]["name"] == name
    assert graph["MobileApplication"]["alternateName"] == other_name
    assert "offers" not in graph["MobileApplication"]


def test_famhub_pages_use_english_chrome(client):
    """They live at root URLs but must not show the Vietnamese menu and footer."""
    for path in (FAMHUB_PATH, FAMHUB_POLICY_PATH):
        html = client.get(path).get_data(as_text=True)
        assert '<html lang="en">' in html and 'property="og:locale" content="en_US"' in html
        assert "Bảo lưu mọi quyền" not in html
        assert 'href="/en/#contact"' in html
    assert f'href="{KIGO_POLICY_PATH}"' in client.get(FAMHUB_POLICY_PATH).get_data(as_text=True)


def test_old_kids_care_pages_are_gone(client):
    for path in ("/kids-care/", "/kids-care/policy/"):
        assert client.get(path).status_code == 404
    redirects = json.loads((Path(__file__).resolve().parent.parent / "vercel.json").read_text())["redirects"]
    assert {"source": "/kids-care/", "destination": KIGO_PATH, "permanent": True} in redirects


@pytest.mark.parametrize(
    "old,new",
    [
        ("/gplx/", GPLX_PATH),
        ("/gplx/policy/", GPLX_POLICY_PATH),
        ("/gplx/support/", GPLX_SUPPORT_PATH),
        ("/gplx/apps/gplx/", GPLX_PATH),
    ],
)
def test_old_gplx_urls_redirect(client, old, new):
    """The App Store listing still points at the old policy and support URLs."""
    assert client.get(old).status_code == 404
    assert client.get(new).status_code == 200
    redirects = json.loads((Path(__file__).resolve().parent.parent / "vercel.json").read_text())["redirects"]
    assert {"source": old, "destination": new, "permanent": True} in redirects


@pytest.mark.parametrize(
    "path,lang,other,app_path,app_name,hidden_name,hidden_path",
    [
        (PROJECTS_PATH, "vi", EN_PROJECTS_PATH, KIGO_PATH, "Kigo", "FamHub", FAMHUB_PATH),
        (EN_PROJECTS_PATH, "en", PROJECTS_PATH, FAMHUB_PATH, "FamHub", "Kigo", KIGO_PATH),
    ],
)
def test_projects_hub(client, path, lang, other, app_path, app_name, hidden_name, hidden_path):
    """One hub per language: the family app appears under that market's name."""
    html = client.get(path).get_data(as_text=True)
    assert f'<html lang="{lang}">' in html and html.count("<h1") == 1
    assert f'hreflang="{"en" if lang == "vi" else "vi"}" href="{BASE}{other}"' in html
    for product in (GPLX_PATH, app_path, "/projects/face-find/", TRONG_CAY_PATH):
        assert f'<a class="product__link" href="{product}">' in html, product
    assert html.count('class="product__link"') == 4
    assert f'<h3 class="product__title">{app_name}</h3>' in html
    assert hidden_name not in html and f'class="product__link" href="{hidden_path}"' not in html


def test_projects_hub_is_linked_from_the_footer(client):
    assert f'href="{PROJECTS_PATH}"' in client.get("/").get_data(as_text=True)
    assert f'href="{EN_PROJECTS_PATH}"' in client.get("/en/").get_data(as_text=True)


@pytest.mark.parametrize(
    "path,hub_name,hub_path",
    [
        (FAMHUB_PATH, "Products", EN_PROJECTS_PATH),
        (KIGO_PATH, "Sản phẩm", PROJECTS_PATH),
    ],
)
def test_app_breadcrumb_uses_the_hub_in_its_language(client, path, hub_name, hub_path):
    graph = _jsonld(client.get(path).get_data(as_text=True))["@graph"]
    crumbs = next(n for n in graph if n["@type"] == "BreadcrumbList")["itemListElement"]
    assert (crumbs[1]["name"], crumbs[1]["item"]) == (hub_name, BASE + hub_path)


def test_kigo_is_linked_from_the_vi_home_page(client):
    html = client.get("/").get_data(as_text=True)
    assert "Kids Care" not in html
    assert html.count(f'href="{KIGO_PATH}"') == 2  # product card + footer
    assert f'href="{FAMHUB_PATH}"' in client.get("/en/").get_data(as_text=True)


def test_gplx_landing_page(client):
    html = client.get(GPLX_PATH).get_data(as_text=True)
    assert html.count("<h1") == 1 and "Ôn thi GPLX" in html
    # hero CTA + download card, both opening in a new tab
    assert html.count(f'href="{GPLX_STORE}" target="_blank" rel="noopener"') == 2
    assert f'href="{GPLX_POLICY_PATH}"' in html
    assert html.count('class="shot"') == 6
    assert "img/products/gplx/og.jpg" in html
    graph = {n["@type"]: n for n in _jsonld(html)["@graph"]}
    app = graph["MobileApplication"]
    assert app["operatingSystem"] == "iOS" and app["downloadUrl"] == GPLX_STORE
    assert app["offers"] == {"@type": "Offer", "price": 0, "priceCurrency": "VND"}
    assert graph["WebPage"]["about"] == {"@id": app["@id"]}
    # the policy page now sits under the landing page
    policy = _jsonld(client.get(GPLX_POLICY_PATH).get_data(as_text=True))["@graph"]
    crumbs = next(n for n in policy if n["@type"] == "BreadcrumbList")["itemListElement"]
    assert [i["item"] for i in crumbs] == [f"{BASE}/", BASE + PROJECTS_PATH, BASE + GPLX_PATH, BASE + GPLX_POLICY_PATH]
    for path in ("/", "/blog/", GPLX_POLICY_PATH):
        assert f'href="{GPLX_PATH}"' in client.get(path).get_data(as_text=True), path


@pytest.mark.parametrize("path", ["/", "/en/", "/blog/", PRODUCT_PATH, GPLX_PATH])
def test_links_to_company_site(client, path):
    """Backlink to the sister site www.crosstechedu.site (it links back to the blog)."""
    html = client.get(path).get_data(as_text=True)
    assert html.count('href="https://www.crosstechedu.site/about"') == 1
    org = next(n for n in _jsonld(html)["@graph"] if n["@type"] in ("ProfessionalService",))
    assert "https://www.crosstechedu.site/" in org["sameAs"]


def test_robots(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    assert f"Sitemap: {BASE}/sitemap.xml" in body


def test_app_ads_txt(client):
    r = client.get("/app-ads.txt")
    assert r.status_code == 200
    assert r.mimetype == "text/plain"
    assert "google.com, pub-5980752937442315, DIRECT, f08c47fec0942fa0" in r.get_data(as_text=True)


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
    # each card on the stores: front face -> App Store, back face -> Google Play
    fronts = re.findall(r'product__face--front">\s*<a class="product__link" href="([^"]+)"', section)
    if path == "/":  # Kigo is not on the stores yet: a single face, linking to its page
        assert fronts.pop() == KIGO_PATH
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


@pytest.mark.parametrize("path", ["/", "/en/", PRODUCT_PATH, PRIVACY_PATH, PROJECTS_PATH, EN_PROJECTS_PATH, GPLX_PATH, GPLX_POLICY_PATH, GPLX_SUPPORT_PATH, FAMHUB_PATH, FAMHUB_POLICY_PATH, KIGO_PATH, KIGO_POLICY_PATH, TRONG_CAY_PATH, TRONG_CAY_POLICY_PATH, TRONG_CAY_SUPPORT_PATH, *FAST_NOTES_PATHS, *BLOG_PATHS])
def test_on_page_seo_audit(client, path):
    """Mirrors the checks of the external SEO audit (rules live in app/seo_audit.py)."""
    page = client.get(path).get_data(as_text=True)
    lang = re.search(r'<html lang="(\w+)"', page).group(1)
    assert audit(page, BASE + path, lang) == []

    # social profiles + share buttons
    for url in ("facebook.com/profile.php?id=61578180279419", "x.com/CrossTechEdu", "linkedin.com/company/cross-tech-edu"):
        assert url in page
    assert page.count('class="share-btn"') == (0 if path in ("/", "/en/") else 3)
