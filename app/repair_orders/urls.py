from django.urls import path

from . import views

app_name = "repair_orders"

urlpatterns = [
    path("", views.repair_order_list, name="list"),
    path("new/", views.repair_order_create, name="create"),
    path("new/customer/<int:customer_pk>/", views.repair_order_create, name="create_for_customer"),
    path("new/vehicle/<int:vehicle_pk>/", views.repair_order_create, name="create_for_vehicle"),
    path("vehicle-field/", views.repair_order_vehicle_field, name="vehicle_field"),
    path("<int:pk>/", views.repair_order_detail, name="detail"),
    path("<int:pk>/edit/", views.repair_order_edit, name="edit"),
    path("<int:pk>/status/", views.repair_order_status_update, name="status_update"),
]
