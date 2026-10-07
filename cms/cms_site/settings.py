"""Settings for the blog CMS.

The CMS is an authoring tool that runs on your machine. The public website
stays a static export on Vercel. Every time an article is saved here, it is
written to ``content/<locale>/articles/<slug>.json``, and those JSON files (in
git) are the source of truth the Flask site renders. The SQLite database is
just a local working copy: ``manage.py import_articles`` rebuilds it from the
JSON files on a fresh clone.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # cms/
REPO_DIR = BASE_DIR.parent

SECRET_KEY = os.environ.get("CMS_SECRET_KEY", "dev-only-cms-key-change-me-if-you-ever-host-this")
DEBUG = os.environ.get("CMS_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("CMS_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cms_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cms_site.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Where articles are exported (the Flask site reads the same folder).
CONTENT_DIR = Path(os.environ.get("CONTENT_DIR", REPO_DIR / "content"))

# Cover images are saved straight into the website's static folder, so the
# path stored on the article ("img/articles/x.webp") works in Flask's asset().
MEDIA_ROOT = REPO_DIR / "app" / "static"
MEDIA_URL = "/media/"

# "View on site" in the admin opens the article on the local Flask dev server.
SITE_PREVIEW_URL = os.environ.get("SITE_PREVIEW_URL", "http://127.0.0.1:5000").rstrip("/")
DEFAULT_LOCALE = "vi"
