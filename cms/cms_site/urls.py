from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

admin.site.site_header = "Cross Tech Edu — Blog CMS"
admin.site.site_title = "Cross Blog CMS"
admin.site.index_title = "Write and publish articles"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/blog/article/", permanent=False)),
    path("admin/", admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
