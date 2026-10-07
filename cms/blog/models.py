from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

LOCALES = [("vi", "Tiếng Việt"), ("en", "English")]

BODY_HELP = """Written in Markdown. Start sections at <code>## Heading</code> (the title is already the page's H1).
<code>**bold**</code> · <code>*italic*</code> · <code>- list item</code> · <code>1. numbered</code> ·
<code>[link text](https://...)</code> · <code>&gt; quote / tip box</code> · a blank line starts a new paragraph."""


def vn_slugify(text: str) -> str:
    """slugify() turns accented letters into ASCII but simply drops "đ"
    ("đơn giản" → "on-gian"), so map it first."""
    return slugify(text.replace("đ", "d").replace("Đ", "D"))


def today():
    return timezone.localdate()


class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft (not on the website)"
        PUBLISHED = "published", "Published"

    locale = models.CharField("language", max_length=2, choices=LOCALES, default="vi")
    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=120,
        blank=True,
        help_text="The URL: /blog/<slug>/. Filled in from the title; changing it later breaks old links.",
    )
    translation_key = models.SlugField(
        max_length=120,
        blank=True,
        help_text="Links the Vietnamese and English versions of the same article: give both the same value. "
        "Defaults to the slug.",
    )
    description = models.CharField(
        max_length=160,
        help_text="One or two sentences (ideally 70–160 characters). Shown in Google results, "
        "on the blog list and when the link is shared.",
    )
    body = models.TextField(help_text=BODY_HELP)
    cover = models.ImageField(
        upload_to="img/articles/",
        blank=True,
        help_text="Optional. A wide image (about 1200×630) also becomes the Facebook/Zalo share picture.",
    )
    cover_alt = models.CharField(
        "cover description",
        max_length=200,
        blank=True,
        help_text="Describe the image in a few words, for Google and screen readers.",
    )
    author = models.CharField(max_length=100, default="Cross Tech Edu")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateField("publish date", default=today)
    updated_at = models.DateField("last updated", blank=True, null=True)

    class Meta:
        ordering = ["-published_at", "title"]
        constraints = [
            models.UniqueConstraint(fields=["locale", "slug"], name="unique_slug_per_locale"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = vn_slugify(self.title)[:120]
        if not self.translation_key:
            self.translation_key = self.slug
        # The admin textarea posts Windows line endings.
        self.body = self.body.replace("\r\n", "\n").strip() + "\n"
        if self.updated_at is None or self.updated_at < self.published_at:
            self.updated_at = self.published_at
        super().save(*args, **kwargs)

    def site_path(self) -> str:
        prefix = "" if self.locale == settings.DEFAULT_LOCALE else f"/{self.locale}"
        return f"{prefix}/blog/{self.slug}/"

    def get_absolute_url(self):
        return settings.SITE_PREVIEW_URL + self.site_path()
