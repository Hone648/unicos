from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.SHOP_DISPLAY_NAME} Emergency / Development Admin"
admin.site.site_title = f"{settings.SHOP_DISPLAY_NAME} Admin"
admin.site.index_title = "Emergency / Development Console"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("attachments/", include("attachments.urls")),
    path("billing/", include("billing.urls")),
    path("customers/", include("customers.urls")),
    path("repair-orders/<int:repair_order_pk>/communications/", include("communications.urls")),
    path("vehicles/", include("vehicles.urls")),
    path("", include("estimates.urls")),
    path("repair-orders/", include("repair_orders.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
