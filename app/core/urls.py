from django.urls import path

from .views import dashboard, healthz, reports

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("reports/", reports, name="reports"),
    path("healthz/", healthz, name="healthz"),
]
