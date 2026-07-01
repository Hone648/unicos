from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("new/", views.communication_create, name="create"),
]
