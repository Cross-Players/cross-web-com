"""Keep content/<locale>/articles/ in sync with the database."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from . import exporter
from .models import Article


@receiver(pre_save, sender=Article)
def remember_old_location(sender, instance, **kwargs):
    old = sender.objects.filter(pk=instance.pk).values("locale", "slug").first() if instance.pk else None
    instance._old_location = (old["locale"], old["slug"]) if old else None


@receiver(post_save, sender=Article)
def export_article(sender, instance, **kwargs):
    old = getattr(instance, "_old_location", None)
    if old and old != (instance.locale, instance.slug):
        exporter.remove(*old)  # renamed or moved to another language
    exporter.export(instance)


@receiver(post_delete, sender=Article)
def remove_article(sender, instance, **kwargs):
    exporter.remove(instance.locale, instance.slug)
