# Cross — IT Outsourcing website

A bilingual (VI / EN) landing page built from the Claude Design template
`CrossOutsourcing.dc.html`. It is written in Python (Flask + Jinja2), rendered
on the server, uses no JavaScript and is set up for Google SEO. The content is
already modelled as CMS blocks.

```
/        → Tiếng Việt (default)
/en/     → English
/blog/, /blog/<slug>/, /en/blog/, /en/blog/<slug>/  → blog
/sitemap.xml, /robots.txt, /404.html
```

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/flask --app wsgi --debug run          # http://127.0.0.1:5000
.venv/bin/pytest -q                              # tests
```

## Blog CMS (Django admin)

Articles are written in a Django admin (`cms/`) that runs **on your machine**.
The live site stays a static export on Vercel, so there is no server or
database to host or pay for.

```bash
.venv/bin/pip install -r requirements-cms.txt        # once
cd cms
../.venv/bin/python manage.py migrate                # once: creates cms/db.sqlite3
../.venv/bin/python manage.py createsuperuser        # once: your admin login
../.venv/bin/python manage.py import_articles        # once per clone: loads existing articles
../.venv/bin/python manage.py runserver 8001         # http://127.0.0.1:8001/admin/
```

**Posting an article:**

1. In the admin, open **Articles → Add**. Write the title, a 70–160 character
   description and the body in Markdown. The *Preview* section renders the body
   after you save. A cover image is optional.
2. Set **Status = Published** and save. The article is written to
   `content/<vi|en>/articles/<slug>.json` (and its cover to
   `app/static/img/articles/`). Drafts get no file. Unpublishing or deleting an
   article removes its file.
3. To check it locally, run the site (`flask --app wsgi --debug run`) and use
   **View on site** in the admin.
4. Publish: `git add content/*/articles/ app/static/img/articles/ && git commit -m "New article" && git push`.
   Vercel rebuilds and the article is live at `/blog/<slug>/`, in the sitemap,
   with `BlogPosting` JSON-LD.

**Two languages:** write the English version as a separate article with
language *English* and the **same translation key** as the Vietnamese one. The
language switch and hreflang tags then link the two versions.

The JSON files in git are the source of truth. `cms/db.sqlite3` is only a local
working copy (gitignored). `import_articles` rebuilds it, and
`export_articles` rewrites every file from it. Hand-editing the JSON files
works too. Run `import_articles` afterwards so the admin sees the edits.

CMS tests: `cd cms && ../.venv/bin/python manage.py test blog`.

## Article-writing agent

`agent/` uses Claude (`claude-opus-5-5`) to research a topic on the web and
write a Vietnamese and an English article. It then opens a **Pull Request**
for you to review. Nothing goes live until you merge it.

```bash
.venv/bin/pip install -r requirements-agent.txt      # once
export ANTHROPIC_API_KEY=sk-ant-...                  # or: ant auth login
.venv/bin/python -m agent "Hướng dẫn tạo Zalo OA cho cửa hàng"
.venv/bin/python -m agent "Chatbot trả lời khách trên Facebook" --notes "Chỉ công cụ miễn phí"
.venv/bin/python -m agent "..." --local              # only write into content/ for a local preview
```

What happens on each run:

1. **Preflight.** It checks that `origin/main` already has the blog, before
   spending anything on the API.
2. **Research and writing.** Claude uses web search and web fetch to check
   prices, free plans and availability in Vietnam. It writes both versions
   following the style and SEO rules in `agent/prompts.py`. It is given the
   existing articles, so it doesn't repeat them and can link to them.
3. **Checks** (`agent/checks.py`). Both versions are rendered by the real Flask
   app and run through the same SEO audit as the test suite
   (`app/seo_audit.py`): title and description length, a single H1, unique
   headings and link texts, and internal links that resolve. Slugs and keys
   must also be new, and each version needs a minimum length. Any problems
   go back to Claude to fix, up to 4 attempts.
4. **Saved run.** The accepted article is saved to `.agent-runs/` (gitignored),
   so a paid run is never lost.
   `python -m agent --from-run .agent-runs/<file>.json` publishes it again
   without calling the API.
5. **Pull Request** (`agent/publish.py`). It creates a branch
   `article/<slug>` from the latest `origin/main` in a temporary git worktree,
   so your working copy and uncommitted changes are never touched. It writes
   only the two article files, runs the full test suite, and pushes. With the
   GitHub CLI (`gh`) installed, the PR is opened for you. Otherwise the agent
   prints the link to open it and saves the PR description, which includes
   the sources and the facts to double-check.
6. **Review and merge.** GitHub Actions runs the tests and Vercel builds a
   preview. Read the article there, fix anything in the PR, then merge. Vercel
   publishes it to www.crosstechedu.com.

**Cost:** every run is billed to your Anthropic account (tokens plus web
searches) and prints its usage with an estimated price. To edit an agent article in the
Django admin, run `manage.py import_articles` after merging.

## Deploy

**Vercel (current setup).** The Vercel project `crosstechedus-projects/cross-web-com`
is linked to this GitHub repo: every push to `main` runs `vercel.json`
(Python install → `freeze.py` → serve `build/` as static files, with
long-cache headers for `/static/`). Without a `SITE_URL` env var the
site uses the Vercel production domain for canonical/sitemap URLs; once a
custom domain is added, set `SITE_URL=https://<domain>` in the Vercel project
settings and redeploy.


**Option A: static export (recommended, fastest).** Push the `build/` folder to
Cloudflare Pages, Netlify, Vercel, GitHub Pages or S3 + CloudFront:

```bash
SITE_URL=https://www.crosstechedu.com .venv/bin/python freeze.py   # → build/
```

**Option B: Python server.** Use this once you need forms, previews or a CMS webhook:

```bash
SITE_URL=https://www.crosstechedu.com gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

Always set `SITE_URL` to the real domain. Canonical URLs, hreflang, the sitemap,
Open Graph and JSON-LD are all built from it.

## Architecture

```
app/
  __init__.py      app factory, asset fingerprinting, inlined critical CSS
  config.py        env-driven settings (SITE_URL, CONTENT_BACKEND, CONTENT_DIR)
  content.py       ContentRepository protocol + JsonFileRepository  ← CMS seam
  seo.py           URLs per locale, hreflang alternates, schema.org JSON-LD
  views.py         generic page route, blog routes, sitemap, robots, 404
  templates/
    base.html, page.html, blog_index.html, article.html, 404.html, sitemap.xml
    partials/      header, footer, meta (SEO <head> tags shared by every page)
    blocks/        one template per block type (hero, services, pricing, ...)
  static/
    css/tokens.css design-system tokens (colours, type, spacing): retune the look here
    css/site.css   page layout (values copied 1:1 from the design)
    css/fonts.css  self-hosted Archivo variable font, split by unicode-range
content/
  site.json                  brand, contact, address, clients + client_logos (shared)
  vi/site.json, en/site.json nav, footer, UI strings per language
  vi/pages/home.json         page = meta + ordered list of blocks
  en/pages/home.json
  vi/articles/*.json         blog articles (Markdown body), written by the CMS
  en/articles/*.json
cms/                         Django admin for writing articles (runs locally)
agent/                       Claude agent that researches, writes and opens a PR for an article
.github/workflows/tests.yml  pytest, CMS tests and the static build on every PR
scripts/build_assets.py      regenerates og-image*.png and apple-touch-icon.png
scripts/fetch_store_assets.py crawls App Store listings → product icons + cover banners
freeze.py                    static export
```

### Content model (ready for a CMS)

A page is an ordered list of typed blocks:

```json
{ "slug": "", "translation_key": "home",
  "meta": { "title": "...", "description": "...", "updated": "2026-09-27" },
  "blocks": [ { "type": "hero", "data": { ... } }, { "type": "pricing", "data": { ... } } ] }
```

This has the same shape as a **Strapi dynamic zone**, a **Wagtail StreamField**,
a **Directus M2A builder** or **Sanity portable blocks**, so moving to a CMS
doesn't require touching templates:

1. In the CMS, create one component per block type (`hero`, `clients`,
   `services`, `pricing`, `cases`, `process`, `contact`) with the fields used in
   `content/vi/pages/home.json`, plus a `Page` collection (slug,
   translation_key, meta, blocks) with i18n turned on.
2. Add a class in `app/content.py` (for example `StrapiRepository`) that
   implements `get_site`, `get_page` and `list_pages` and maps the API response
   into `Page` / `Block`.
3. Register it in `make_repository()` and set `CONTENT_BACKEND=strapi`.
4. Static hosting: add a CMS webhook that runs `freeze.py` and redeploys.
   Server hosting: add a small cache (for example `cachetools.TTLCache`)
   around the repository.

New pages need **no new routes**. Add `content/vi/pages/about.json` with
`"slug": "about"` and it is served at `/about/`, gets `/en/about/` as its
hreflang alternate when an EN page shares the same `translation_key`, and
appears in the sitemap. A new block type only needs
`templates/blocks/<type>.html`.

## SEO checklist (implemented)

- Server-rendered semantic HTML: one `<h1>`, `<main>`, `<nav>`, `<address>`,
  `<section aria-labelledby>`, and lists for grids.
- Title and meta description per language (tests check their length).
- `<link rel="canonical">`, `hreflang` vi / en / x-default, and a sitemap with
  `xhtml:link` alternates.
- Open Graph and Twitter card, with a 1200×630 share image.
- JSON-LD `@graph`: `ProfessionalService` (address, contact point, languages,
  area served), `WebSite`, `WebPage`, an `OfferCatalog` of the 9 services and
  `Offer`s with real prices (`minPrice` for "from ...").
- `robots.txt` pointing to the sitemap, a `noindex` 404 page, and
  `lang` attributes on mixed-language text.
- Performance: no JavaScript, critical CSS inlined (about 3.5 KB gzipped),
  self-hosted woff2 with only the needed subsets preloaded, `font-display: swap`,
  explicit image dimensions, lazy loading, fingerprinted static URLs
  (`?v=<hash>`), and gzip/brotli via Flask-Compress. When Flask serves the files
  (option B) they are cached for one year. With the static export (option A),
  set cache headers in your host's config instead: long cache for `/static/*`
  and short for HTML.

## Before going live: things to fill in

| What | Where |
|---|---|
| Detailed pricing page: the design links to `CrossPricing.dc.html`, which was not exported; the button currently goes to `#contact` | add `content/vi/pages/bang-gia.json` + EN, then point `pricing.cta.href` at it |
| Add or remove a client logo (name, logo file, website URL; `fill: true` for square logos) | `content/site.json` → `client_logos`, files in `app/static/img/clients/` |
| Social profiles (LinkedIn, Facebook, GitHub...) | `content/site.json` → `same_as` |
| Add a product card: add its App Store id to `PRODUCTS` and run the crawler, then add the item (with `icon`/`cover`) to `products` in both `pages/home.json` | `.venv/bin/python scripts/fetch_store_assets.py` |
| Share images print the domain and headline: re-run after changing them | `.venv/bin/python scripts/build_assets.py` |
| Google Search Console | verify the domain, then submit `/sitemap.xml` |
