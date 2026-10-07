"""Rebuild the local database from content/<locale>/articles/*.json.

Run it once after cloning the repo (or after pulling articles written on
another machine). Existing articles are updated, matched by language + slug.
"""

import json
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from blog.models import Article


class Command(BaseCommand):
    help = "Import published articles from content/<locale>/articles/*.json into the CMS database."

    def handle(self, *args, **options):
        count = 0
        for path in sorted(settings.CONTENT_DIR.glob("*/articles/*.json")):
            locale = path.parent.parent.name
            raw = json.loads(path.read_text(encoding="utf-8"))
            Article.objects.update_or_create(
                locale=locale,
                slug=raw["slug"],
                defaults={
                    "translation_key": raw.get("translation_key") or raw["slug"],
                    "title": raw["title"],
                    "description": raw.get("description", ""),
                    "body": raw.get("body", ""),
                    "cover": raw.get("cover") or "",
                    "cover_alt": raw.get("cover_alt", ""),
                    "author": raw.get("author", ""),
                    "status": Article.Status.PUBLISHED,
                    "published_at": date.fromisoformat(raw["published"]),
                    "updated_at": date.fromisoformat(raw.get("updated") or raw["published"]),
                },
            )
            count += 1
            self.stdout.write(f"  {locale}/{raw['slug']}")
        self.stdout.write(self.style.SUCCESS(f"Imported {count} article(s)."))
