"""Routes. Pages are resolved from the content repository, so new pages added
in ``content/`` (or later in a CMS) are served without new routes."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, abort, current_app, render_template, request

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

