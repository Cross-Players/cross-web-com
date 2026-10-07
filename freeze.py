"""Export the whole site to static HTML in ./build (deploy to any CDN:
Cloudflare Pages, Netlify, Vercel, GitHub Pages, S3...).

    SITE_URL=https://crossplayers.com .venv/bin/python freeze.py
"""

from flask_frozen import Freezer

from app import create_app

app = create_app()
freezer = Freezer(app, with_no_argument_rules=True, log_url_for=True)


@freezer.register_generator
def all_pages():
    repo = app.extensions["content"]
    default = app.config["DEFAULT_LOCALE"]
    for locale in app.config["LOCALES"]:
        for page in repo.list_pages(locale):
            if locale == default:
                yield "site.page_default", {"slug": page.slug}
            else:
                yield "site.page_localized", {"locale": locale, "slug": page.slug}



@freezer.register_generator
def blog():
    repo = app.extensions["content"]
    default = app.config["DEFAULT_LOCALE"]
    for locale in app.config["LOCALES"]:
        loc = None if locale == default else locale
        yield "site.blog_index", {"locale": loc}
        for article in repo.list_articles(locale):
            yield "site.blog_article", {"locale": loc, "slug": article.slug}


if __name__ == "__main__":
    freezer.freeze()
    print(f"Static site written to {app.config['FREEZER_DESTINATION']}")
