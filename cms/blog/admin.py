import markdown
from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Article

CONTENT_FIELDS = {"title", "description", "body", "cover", "cover_alt"}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "locale", "status", "published_at", "updated_at", "url")
    list_filter = ("status", "locale")
    search_fields = ("title", "description", "body")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("updated_at", "preview")
    actions = ("publish", "unpublish")
    save_on_top = True
    fieldsets = (
        (None, {"fields": ("title", "description", "body", "status")}),
        ("Cover image", {"fields": ("cover", "cover_alt")}),
        (
            "Settings",
            {"fields": ("locale", "slug", "translation_key", "author", "published_at", "updated_at")},
        ),
        ("Preview", {"fields": ("preview",), "classes": ("collapse",)}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "body":
            kwargs["widget"] = forms.Textarea(
                attrs={"rows": 32, "style": "width:100%;max-width:60em;font:14px/1.6 ui-monospace,Menlo,monospace"}
            )
        if db_field.name == "description":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 2, "style": "width:100%;max-width:60em"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="Address on the website")
    def url(self, obj):
        return obj.site_path() if obj.is_published else "— (draft)"

    @admin.display(description="How the article body will look (after saving)")
    def preview(self, obj):
        if not obj or not obj.body:
            return "Save the article to see a preview."
        html = markdown.markdown(obj.body, extensions=["extra", "sane_lists"])
        return format_html(
            '<div style="max-width:44rem;font-size:15px;line-height:1.6;background:#fff;color:#201e1d;'
            'padding:16px 24px;border:1px solid #ddd">{}</div>',
            mark_safe(html),
        )

    def save_model(self, request, obj, form, change):
        if change and CONTENT_FIELDS & set(form.changed_data):
            obj.updated_at = timezone.localdate()
        super().save_model(request, obj, form, change)
        if obj.is_published:
            self.message_user(
                request,
                f"Saved to content/{obj.locale}/articles/{obj.slug}.json. "
                "Commit and push to put it on www.crosstechedu.com.",
            )
        else:
            self.message_user(
                request,
                "Saved as a DRAFT: no JSON file is written and it won't appear on the website. "
                "Set Status to Published when it's ready.",
                level=messages.WARNING,
            )

    @admin.action(description="Publish selected articles")
    def publish(self, request, queryset):
        for article in queryset:  # save() one by one so each file gets exported
            article.status = Article.Status.PUBLISHED
            article.save()

    @admin.action(description="Unpublish selected articles (back to draft)")
    def unpublish(self, request, queryset):
        for article in queryset:
            article.status = Article.Status.DRAFT
            article.save()
