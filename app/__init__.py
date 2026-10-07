"""Cross Outsourcing website — Flask application factory."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import markdown as md
from flask import Flask, url_for
from flask.helpers import get_debug_flag
from flask_compress import Compress
from markupsafe import Markup, escape

from .config import Config
from .content import make_repository

compress = Compress()


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    app.extensions["content"] = make_repository(app.config)
    compress.init_app(app)

    _register_template_helpers(app)

    from .views import bp

    app.register_blueprint(bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return resp

    return app


def _register_template_helpers(app: Flask) -> None:
    static_dir = Path(app.static_folder)

    @lru_cache(maxsize=None)
    def _fingerprint(filename: str) -> str:
        return hashlib.sha1((static_dir / filename).read_bytes()).hexdigest()[:10]

    @lru_cache(maxsize=None)
    def _inline_css(*filenames: str) -> str:
        """Concatenate + lightly minify CSS so it can be inlined in <head>.

        The whole stylesheet is ~10 KB (before gzip), so inlining it removes a
        render-blocking request and improves LCP / Core Web Vitals.
        """
        css = "\n".join((static_dir / "css" / f).read_text(encoding="utf-8") for f in filenames)
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        css = re.sub(r"\s+", " ", css)
        css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
        # Only strip *after* ":" — a space before it is a descendant combinator
        # (".contact :focus-visible" != ".contact:focus-visible").
        css = re.sub(r":\s+", ":", css)
        # font URLs are relative to /static/css/; make them absolute.
        css = css.replace("url('../", "url('" + app.static_url_path + "/")
        return css.replace(";}", "}").strip()

    # In debug mode, re-read files on every request so CSS edits show up live.
    if app.debug or get_debug_flag():
        fingerprint, inline_css = _fingerprint.__wrapped__, _inline_css.__wrapped__
    else:
        fingerprint, inline_css = _fingerprint, _inline_css

    @app.template_global()
    def asset(filename: str, _external: bool = False) -> str:
        """Cache-busted static URL: /static/img/logo-x.webp?v=1a2b3c4d5e"""
        return url_for("static", filename=filename, v=fingerprint(filename), _external=_external)

    @app.template_global()
    def critical_css() -> Markup:
        return Markup(inline_css("fonts.css", "tokens.css", "site.css"))

    @app.template_global()
    def home_url(locale: str) -> str:
        from .seo import page_path

        return page_path(locale, "", app.config["DEFAULT_LOCALE"])

    @app.template_global()
    def section_link(href: str, locale: str, on_home: bool) -> str:
        """In-page anchors (#pricing) only work on the home page; elsewhere
        point them back to the home page of the same language."""
        if href.startswith("#") and not on_home:
            return home_url(locale) + href
        return href

    @app.template_filter("markdown")
    def markdown_filter(text: str) -> Markup:
        """Article bodies are Markdown written by the site owner in the CMS
        (trusted input), so raw HTML inside them is allowed."""
        return Markup(md.markdown(text, extensions=["extra", "sane_lists"], output_format="html"))

    @app.template_filter("date_label")
    def date_label(iso: str, locale: str) -> str:
        """'2026-10-06' → '06/10/2026' (vi) or '6 October 2026' (en)."""
        d = date.fromisoformat(iso)
        if locale == "vi":
            return d.strftime("%d/%m/%Y")
        return f"{d.day} {d.strftime('%B %Y')}"

    @app.template_filter("nl2br")
    def nl2br(value: str) -> Markup:
        return Markup("<br>").join(escape(value).split("\n"))
