from django.urls import path

from . import views

app_name = "attachments"

urlpatterns = [
    path(
        "repair-orders/<int:repair_order_pk>/upload/",
        views.attachment_upload,
        name="upload_for_repair_order",
    ),
    path("<int:pk>/download/", views.attachment_download, name="download"),
    path("<int:pk>/delete/", views.attachment_delete, name="delete"),
]
