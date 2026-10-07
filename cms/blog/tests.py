import json
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from .models import Article, vn_slugify


class ExportTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.content = Path(self.tmp.name)
        override = override_settings(CONTENT_DIR=self.content)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(self.tmp.cleanup)

    def file(self, locale, slug):
        return self.content / locale / "articles" / f"{slug}.json"

    def make(self, **kw):
        fields = dict(
            title="Công cụ AI đơn giản",
            description="Mô tả bài viết",
            body="## Mở đầu\r\n\r\nNội dung.",
            status=Article.Status.PUBLISHED,
            published_at=date(2026, 10, 6),
        )
        fields.update(kw)
        return Article.objects.create(**fields)

    def test_vietnamese_slug_keeps_d(self):
        self.assertEqual(vn_slugify("Công cụ AI đơn giản cho Đà Nẵng"), "cong-cu-ai-don-gian-cho-da-nang")

    def test_published_article_is_exported(self):
        a = self.make()
        data = json.loads(self.file("vi", "cong-cu-ai-don-gian").read_text(encoding="utf-8"))
        self.assertEqual(data["slug"], a.slug)
        self.assertEqual(data["translation_key"], "cong-cu-ai-don-gian")
        self.assertEqual(data["published"], "2026-10-06")
        self.assertEqual(data["updated"], "2026-10-06")
        self.assertEqual(data["body"], "## Mở đầu\n\nNội dung.\n")  # CRLF normalised
        self.assertIsNone(data["cover"])

    def test_draft_is_not_exported_and_unpublish_removes_file(self):
        a = self.make(status=Article.Status.DRAFT)
        self.assertFalse(self.file("vi", a.slug).exists())
        a.status = Article.Status.PUBLISHED
        a.save()
        self.assertTrue(self.file("vi", a.slug).exists())
        a.status = Article.Status.DRAFT
        a.save()
        self.assertFalse(self.file("vi", a.slug).exists())

    def test_rename_and_language_change_remove_old_file(self):
        a = self.make()
        a.slug = "moi"
        a.save()
        self.assertFalse(self.file("vi", "cong-cu-ai-don-gian").exists())
        self.assertTrue(self.file("vi", "moi").exists())
        a.locale = "en"
        a.save()
        self.assertFalse(self.file("vi", "moi").exists())
        self.assertTrue(self.file("en", "moi").exists())

    def test_delete_removes_file(self):
        a = self.make()
        a.delete()
        self.assertFalse(self.file("vi", "cong-cu-ai-don-gian").exists())

    def test_import_round_trip(self):
        self.make(cover="img/articles/x.webp", cover_alt="Ảnh")
        before = self.file("vi", "cong-cu-ai-don-gian").read_text(encoding="utf-8")
        Article.objects.all().delete()
        # delete removed the file; put it back as if it came from git
        self.file("vi", "cong-cu-ai-don-gian").write_text(before, encoding="utf-8")
        call_command("import_articles", verbosity=0, stdout=open("/dev/null", "w"))
        a = Article.objects.get()
        self.assertEqual(a.cover.name, "img/articles/x.webp")
        self.assertTrue(a.is_published)
        self.assertEqual(self.file("vi", a.slug).read_text(encoding="utf-8"), before)

    def test_admin_add_and_edit_bumps_updated_date(self):
        User.objects.create_superuser("admin", "a@example.com", "pw")
        self.client.login(username="admin", password="pw")
        r = self.client.get("/admin/blog/article/add/")
        self.assertEqual(r.status_code, 200)
        a = self.make(published_at=date(2026, 1, 1))
        r = self.client.post(
            f"/admin/blog/article/{a.pk}/change/",
            {
                "title": a.title, "description": a.description, "body": "## Mới\n\nSửa.",
                "status": "published", "cover_alt": "", "locale": "vi", "slug": a.slug,
                "translation_key": a.translation_key, "author": a.author, "published_at": "2026-01-01",
            },
        )
        self.assertEqual(r.status_code, 302, r.content[:2000])
        a.refresh_from_db()
        self.assertGreater(a.updated_at, date(2026, 1, 1))
        self.assertIn("Sửa.", self.file("vi", a.slug).read_text(encoding="utf-8"))
        # the change page renders the Markdown preview
        r = self.client.get(f"/admin/blog/article/{a.pk}/change/")
        self.assertContains(r, "<h2>Mới</h2>")
