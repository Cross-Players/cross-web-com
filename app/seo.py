"""SEO helpers: locale-aware URLs, hreflang alternates and schema.org JSON-LD."""

from __future__ import annotations

import json
from typing import Any

from markupsafe import Markup

from .content import Article, ContentRepository, Page

OG_LOCALES = {"vi": "vi_VN", "en": "en_US"}


def page_path(locale: str, slug: str, default_locale: str) -> str:
    """'/' for the default-locale home, '/en/' for English home, '/en/about/'..."""
    parts = [] if locale == default_locale else [locale]
    if slug:
        parts.append(slug.strip("/"))
    return "/" + "".join(f"{p}/" for p in parts)


def blog_path(locale: str, default_locale: str, slug: str = "") -> str:
    """'/blog/', '/blog/<slug>/', '/en/blog/', '/en/blog/<slug>/'."""
    return page_path(locale, "blog/" + slug if slug else "blog", default_locale)


def article_alternates(
    repo: ContentRepository, article: Article, locales: tuple[str, ...], default_locale: str
) -> dict[str, str]:
    """{locale: path} for every locale with an article sharing the translation_key."""
    out: dict[str, str] = {}
    for loc in locales:
        match = next(
            (a for a in repo.list_articles(loc) if a.translation_key == article.translation_key),
            None,
        )
        if match is not None:
            out[loc] = blog_path(loc, default_locale, match.slug)
    return out


def alternates(
    repo: ContentRepository, page: Page, locales: tuple[str, ...], default_locale: str
) -> dict[str, str]:
    """{locale: path} for every locale that has a page with the same translation_key."""
    out: dict[str, str] = {}
    for loc in locales:
        match = next(
            (p for p in repo.list_pages(loc) if p.translation_key == page.translation_key),
            None,
        )
        if match is not None:
            out[loc] = page_path(loc, match.slug, default_locale)
    return out


def _offers(page: Page, site_url: str, page_url: str) -> list[dict[str, Any]]:
    """Turn the pricing block into schema.org Offers (only items that carry a `schema`)."""
    pricing = page.block("pricing")
    if pricing is None:
        return []
    offers = []
    for group in pricing.data.get("groups", []):
        for item in group.get("items", []):
            s = item.get("schema")
            if not s:
                continue
            spec: dict[str, Any] = {"@type": "UnitPriceSpecification", "priceCurrency": s["currency"]}
            if "min_price" in s:
                spec["minPrice"] = s["min_price"]
            else:
                spec["price"] = s["price"]
            if s.get("unit"):
                spec["unitText"] = s["unit"]
            offers.append(
                {
                    "@type": "Offer",
                    "name": f'{group["title"]}: {item["label"]}',
                    "description": item.get("note", ""),
                    "priceSpecification": spec,
                    "url": page_url + "#pricing",
                    "seller": {"@id": site_url + "/#organization"},
                }
            )
    return offers


def _organization(site: dict[str, Any], site_url: str, description: str) -> dict[str, Any]:
    contact = site["contact"]
    address = site["address"]
    organization = {
        "@type": "ProfessionalService",
        "@id": site_url + "/#organization",
        "name": site["brand"]["name"],
        "legalName": site["brand"].get("legal_name", site["brand"]["name"]),
        "url": site_url + "/",
        "logo": site_url + "/static/" + site["brand"].get("logo_png", site["brand"]["logo"]),
        "image": site_url + "/static/img/og-image.png",
        "description": site.get("organization_description", description),
        "email": contact["email"],
        "telephone": contact["phone_e164"],
        "priceRange": site.get("price_range", "$"),
        "address": {
            "@type": "PostalAddress",
            "addressLocality": address["locality"],
            "addressCountry": address["country"],
        },
        "areaServed": site.get("area_served", []),
        "knowsLanguage": site.get("languages", []),
        "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "sales",
            "email": contact["email"],
            "telephone": contact["phone_e164"],
            "availableLanguage": site.get("languages", []),
        },
    }
    if site.get("same_as"):
        organization["sameAs"] = site["same_as"]
    return organization


def _website(site: dict[str, Any], site_url: str) -> dict[str, Any]:
    return {
        "@type": "WebSite",
        "@id": site_url + "/#website",
        "url": site_url + "/",
        "name": site["brand"]["name"],
        "publisher": {"@id": site_url + "/#organization"},
        "inLanguage": list(OG_LOCALES.keys()),
    }


def _dump(payload: dict[str, Any]) -> Markup:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Prevent "</script>" injection from content.
    return Markup(text.replace("</", "<\\/"))


def jsonld(site: dict[str, Any], page: Page, site_url: str, page_url: str, locale: str) -> Markup:
    org_id = site_url + "/#organization"
    organization = _organization(site, site_url, page.meta.get("description", ""))

    graph: list[dict[str, Any]] = [
        organization,
        _website(site, site_url),
        {
            "@type": "WebPage",
            "@id": page_url + "#webpage",
            "url": page_url,
            "name": page.meta.get("title", ""),
            "description": page.meta.get("description", ""),
            "inLanguage": locale,
            "isPartOf": {"@id": site_url + "/#website"},
            "about": {"@id": org_id},
        },
    ]

    services = page.block("services")
    offers = _offers(page, site_url, page_url)
    if services or offers:
        catalog: dict[str, Any] = {
            "@type": "OfferCatalog",
            "name": (services.data.get("title") if services else page.meta.get("title", "")),
        }
        if services:
            catalog["itemListElement"] = [
                {
                    "@type": "Offer",
                    "itemOffered": {
                        "@type": "Service",
                        "name": s["title"],
                        "description": s["body"],
                        "provider": {"@id": org_id},
                    },
                }
                for s in services.data.get("items", [])
            ]
        organization["hasOfferCatalog"] = catalog
        if offers:
            organization["makesOffer"] = offers

    return _dump({"@context": "https://schema.org", "@graph": graph})


def blog_jsonld(
    site: dict[str, Any],
    site_url: str,
    blog_url: str,
    locale: str,
    title: str,
    description: str,
    articles: list[tuple[Article, str]],
) -> Markup:
    """Blog index: the organization plus a schema.org Blog listing every post.
    ``articles`` is a list of (article, absolute url)."""
    org_id = site_url + "/#organization"
    blog = {
        "@type": "Blog",
        "@id": blog_url + "#blog",
        "url": blog_url,
        "name": title,
        "description": description,
        "inLanguage": locale,
        "publisher": {"@id": org_id},
        "isPartOf": {"@id": site_url + "/#website"},
        "blogPost": [
            {
                "@type": "BlogPosting",
                "headline": a.title,
                "url": url,
                "datePublished": a.published,
                "dateModified": a.updated,
            }
            for a, url in articles
        ],
    }
    graph = [_organization(site, site_url, description), _website(site, site_url), blog]
    return _dump({"@context": "https://schema.org", "@graph": graph})


def article_jsonld(
    site: dict[str, Any],
    article: Article,
    site_url: str,
    page_url: str,
    blog_url: str,
    image_url: str,
) -> Markup:
    org_id = site_url + "/#organization"
    author: dict[str, Any] = (
        {"@type": "Person", "name": article.author}
        if article.author and article.author != site["brand"]["name"]
        else {"@id": org_id}
    )
    posting = {
        "@type": "BlogPosting",
        "@id": page_url + "#article",
        "mainEntityOfPage": page_url,
        "url": page_url,
        "headline": article.title,
        "description": article.description,
        "image": image_url,
        "datePublished": article.published,
        "dateModified": article.updated,
        "inLanguage": article.locale,
        "author": author,
        "publisher": {"@id": org_id},
        "isPartOf": {"@id": blog_url + "#blog"},
        "wordCount": len(article.body.split()),
    }
    graph = [_organization(site, site_url, article.description), _website(site, site_url), posting]
    return _dump({"@context": "https://schema.org", "@graph": graph})
