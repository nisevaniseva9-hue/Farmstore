"""
URL configuration for the farmstore project.

Kept flat and simple. Each app's URLs will be included with its own
namespace as it is built out in later phases.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from config import views as core_views

urlpatterns = [
    path("", core_views.home, name="home"),
    path("health/", core_views.health_check, name="health_check"),

    path("admin/", admin.site.urls),
    path("account/", include("apps.accounts.urls")),

    path("", include("apps.catalog.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.payments.urls")),
    path("farmer/", include("apps.orders.farmer_urls")),
    path("farmer/", include("apps.catalog.farmer_urls")),
    path("farmer/payments/", include("apps.payments.farmer_urls")),
    path("farmer/notifications/", include("apps.notifications.urls")),
    path("farmer/inventory/", include("apps.inventory.urls")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
