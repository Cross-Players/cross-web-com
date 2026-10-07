from django.apps import AppConfig


class BlogConfig(AppConfig):
    name = "blog"
    verbose_name = "Blog"

    def ready(self):
        from . import signals  # noqa: F401
