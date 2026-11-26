from django.contrib import admin
from django.urls import include, path

from crm.views import healthz

admin.site.site_header = "Resort CRM — ผู้ดูแลระบบ"
admin.site.site_title = "Resort CRM"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("crm.urls")),
]
