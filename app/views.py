"""Routes. Pages are resolved from the content repository, so new pages added
in ``content/`` (or later in a CMS) are served without new routes."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, abort, current_app, render_template, request, url_for

from . import seo
from .content import ContentRepository

bp = Blueprint("site", __name__)


def _repo() -> ContentRepository:
    return current_app.extensions["content"]


def _render_page(locale: str, slug: str) -> str:
    cfg = current_app.config
    repo = _repo()
    page = repo.get_page(locale, slug)
    if page is None:
        abort(404)
    site = repo.get_site(locale)
    site_url = cfg["SITE_URL"]
    path = seo.page_path(locale, page.slug, cfg["DEFAULT_LOCALE"])
    alts = seo.alternates(repo, page, cfg["LOCALES"], cfg["DEFAULT_LOCALE"])
    return render_template(
        "page.html",
        page=page,
        meta=page.meta,
        site=site,
        locale=locale,
        site_url=site_url,
        canonical=site_url + path,
        alternates=alts,
        default_locale=cfg["DEFAULT_LOCALE"],
        og_locale=seo.OG_LOCALES[locale],
        og_locale_alternates=[seo.OG_LOCALES[loc] for loc in alts if loc != locale],
        jsonld=seo.jsonld(site, page, site_url, site_url + path, locale),
    )


def _seo_context(locale: str, path: str, alternates: dict[str, str]) -> dict:
    cfg = current_app.config
    return {
        "locale": locale,
        "site_url": cfg["SITE_URL"],
        "canonical": cfg["SITE_URL"] + path,
        "alternates": alternates,
        "default_locale": cfg["DEFAULT_LOCALE"],
        "og_locale": seo.OG_LOCALES[locale],
        "og_locale_alternates": [seo.OG_LOCALES[loc] for loc in alternates if loc != locale],
    }


def _render_blog(locale: str) -> str:
    cfg = current_app.config
    repo = _repo()
    site = repo.get_site(locale)
    default = cfg["DEFAULT_LOCALE"]
    blog = site["blog"]
    path = seo.blog_path(locale, default)
    alts = {loc: seo.blog_path(loc, default) for loc in cfg["LOCALES"]}
    articles = repo.list_articles(locale)
    links = [(a, cfg["SITE_URL"] + seo.blog_path(locale, default, a.slug)) for a in articles]
    ctx = _seo_context(locale, path, alts)
    return render_template(
        "blog_index.html",
        site=site,
        meta={"title": blog["meta_title"], "description": blog["meta_description"]},
        articles=[(a, seo.blog_path(locale, default, a.slug)) for a in articles],
        jsonld=seo.blog_jsonld(
            site, cfg["SITE_URL"], ctx["canonical"], locale,
            blog["meta_title"], blog["meta_description"], links,
        ),
        **ctx,
    )


def _render_article(locale: str, slug: str) -> str:
    cfg = current_app.config
    repo = _repo()
    article = repo.get_article(locale, slug)
    if article is None:
        abort(404)
    site = repo.get_site(locale)
    default = cfg["DEFAULT_LOCALE"]
    path = seo.blog_path(locale, default, article.slug)
    alts = seo.article_alternates(repo, article, cfg["LOCALES"], default)
    ctx = _seo_context(locale, path, alts)
    title = f'{article.title} | {site["brand"]["name"]}'
    meta = {
        # Google cuts titles at ~60 characters: drop the brand rather than the headline.
        "title": title if len(title) <= 65 else article.title,
        "og_title": article.title,
        "description": article.description,
    }
    if article.cover:
        meta["og_image_url"] = cfg["SITE_URL"] + url_for("static", filename=article.cover)
    image_url = meta.get("og_image_url") or cfg["SITE_URL"] + url_for("static", filename=site["og_image"])
    blog_url = cfg["SITE_URL"] + seo.blog_path(locale, default)
    return render_template(
        "article.html",
        site=site,
        meta=meta,
        og_type="article",
        article=article,
        blog_home=seo.blog_path(locale, default),
        jsonld=seo.article_jsonld(site, article, cfg["SITE_URL"], ctx["canonical"], blog_url, image_url),
        **ctx,
    )


# Blog: /blog/, /blog/<slug>/, /en/blog/, /en/blog/<slug>/. Werkzeug ranks these
# static-prefix rules above the catch-all page rules below.
@bp.route("/blog/", defaults={"locale": None})
@bp.route("/<any(en):locale>/blog/")
def blog_index(locale: str | None):
    return _render_blog(locale or current_app.config["DEFAULT_LOCALE"])


@bp.route("/blog/<slug>/", defaults={"locale": None})
@bp.route("/<any(en):locale>/blog/<slug>/")
def blog_article(locale: str | None, slug: str):
    return _render_article(locale or current_app.config["DEFAULT_LOCALE"], slug)


# Default locale lives at the root: /, /about/ ...
@bp.route("/", defaults={"slug": ""})
@bp.route("/<path:slug>/")
def page_default(slug: str):
    return _render_page(current_app.config["DEFAULT_LOCALE"], slug)


# Other locales are prefixed: /en/, /en/about/ ...
@bp.route("/<any(en):locale>/", defaults={"slug": ""})
@bp.route("/<any(en):locale>/<path:slug>/")
def page_localized(locale: str, slug: str):
    return _render_page(locale, slug)


@bp.route("/sitemap.xml")
def sitemap():
    cfg = current_app.config
    repo = _repo()
    default = cfg["DEFAULT_LOCALE"]
    entries = []
    for locale in cfg["LOCALES"]:
        for page in repo.list_pages(locale):
            if page.meta.get("noindex"):
                continue
            entries.append(
                {
                    "loc": cfg["SITE_URL"] + seo.page_path(locale, page.slug, cfg["DEFAULT_LOCALE"]),
                    "lastmod": page.meta.get("updated", date.today().isoformat()),
                    "alternates": seo.alternates(repo, page, cfg["LOCALES"], cfg["DEFAULT_LOCALE"]),
                    "priority": "1.0" if page.slug == "" else "0.7",
                }
            )
        articles = repo.list_articles(locale)
        if articles:
            entries.append(
                {
                    "loc": cfg["SITE_URL"] + seo.blog_path(locale, default),
                    "lastmod": max(a.updated for a in articles),
                    "alternates": {
                        loc: seo.blog_path(loc, default)
                        for loc in cfg["LOCALES"]
                        if repo.list_articles(loc)
                    },
                    "priority": "0.6",
                }
            )
        for article in articles:
            entries.append(
                {
                    "loc": cfg["SITE_URL"] + seo.blog_path(locale, default, article.slug),
                    "lastmod": article.updated,
                    "alternates": seo.article_alternates(repo, article, cfg["LOCALES"], default),
                    "priority": "0.6",
                }
            )
    xml = render_template(
        "sitemap.xml",
        entries=entries,
        site_url=cfg["SITE_URL"],
        default_locale=cfg["DEFAULT_LOCALE"],
    )
    return Response(xml, mimetype="application/xml")


@bp.route("/robots.txt")
def robots():
    body = f"User-agent: *\nAllow: /\n\nSitemap: {current_app.config['SITE_URL']}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@bp.route("/404.html")
def not_found_page():
    """Static 404 for hosts that serve build/404.html (Netlify, GitHub Pages...)."""
    return _not_found(None)


@bp.app_errorhandler(404)
def _not_found(_err):
    cfg = current_app.config
    first = request.path.strip("/").split("/", 1)[0] if request else ""
    locale = first if first in cfg["LOCALES"] else cfg["DEFAULT_LOCALE"]
    site = _repo().get_site(locale)
    home = seo.page_path(locale, "", cfg["DEFAULT_LOCALE"])
    status = 200 if request.path == "/404.html" else 404
    return render_template("404.html", site=site, locale=locale, home=home), status

