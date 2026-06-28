from django.urls import path

from .views import dashboard, healthz

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("healthz/", healthz, name="healthz"),
]
