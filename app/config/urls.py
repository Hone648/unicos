from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("repair-orders/", include("repair_orders.urls")),
    path("", include("core.urls")),
]
