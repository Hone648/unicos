from django.urls import path

from vehicles import views as vehicle_views

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("new/", views.customer_create, name="create"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/edit/", views.customer_edit, name="edit"),
    path("<int:pk>/vehicles/new/", vehicle_views.vehicle_create_for_customer, name="vehicle_create"),
]
