from django.urls import path

from . import views

app_name = "vehicles"

urlpatterns = [
    path("<int:pk>/", views.vehicle_detail, name="detail"),
    path("<int:pk>/edit/", views.vehicle_edit, name="edit"),
]
