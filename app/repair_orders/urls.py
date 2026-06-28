from django.urls import path

from . import views

app_name = "repair_orders"

urlpatterns = [
    path("", views.repair_order_list, name="list"),
    path("<int:pk>/", views.repair_order_detail, name="detail"),
    path("<int:pk>/status/", views.repair_order_status_update, name="status_update"),
]
