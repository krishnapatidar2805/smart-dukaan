from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", lambda request: redirect("dashboard:home" if request.user.is_authenticated else "accounts:login")),
    path("accounts/", include("accounts.urls")),
    path("inventory/", include("inventory.urls")),
    path("billing/", include("billing.urls")),
    path("purchases/", include("purchases.urls")),
    path("udhaar/", include("udhaar.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("store/", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

