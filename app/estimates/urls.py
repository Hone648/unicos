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
    path("estimates/<int:pk>/edit/", views.estimate_edit, name="edit"),
]
