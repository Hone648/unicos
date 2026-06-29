from django.urls import path

from . import views

app_name = "estimates"

urlpatterns = [
    path(
        "repair-orders/<int:repair_order_pk>/estimates/new/",
        views.estimate_create,
        name="create",
    ),
    path("estimates/<int:pk>/", views.estimate_detail, name="detail"),
    path("estimates/<int:pk>/print/", views.estimate_print, name="print"),
    path("estimates/<int:pk>/edit/", views.estimate_edit, name="edit"),
    path("estimates/<int:pk>/status/", views.estimate_status_update, name="status_update"),
    path(
        "estimates/<int:pk>/supplements/new/",
        views.supplement_create,
        name="supplement_create",
    ),
    path(
        "estimates/<int:estimate_pk>/line-items/new/",
        views.line_item_create,
        name="line_item_create",
    ),
    path(
        "estimates/line-items/<int:pk>/edit/",
        views.line_item_edit,
        name="line_item_edit",
    ),
    path(
        "estimates/line-items/<int:pk>/delete/",
        views.line_item_delete,
        name="line_item_delete",
    ),
]
