"""Re-write every article's JSON file from the database (e.g. after a bulk
edit in the shell). Saving in the admin already does this automatically."""

from django.core.management.base import BaseCommand

from blog import exporter
from blog.models import Article


class Command(BaseCommand):
    help = "Export all published articles to content/<locale>/articles/."

    def handle(self, *args, **options):
        published = 0
        for article in Article.objects.all():
            exporter.export(article)
            published += article.is_published
        self.stdout.write(self.style.SUCCESS(f"Exported {published} published article(s)."))
