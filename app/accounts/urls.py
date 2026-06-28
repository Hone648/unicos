from django.contrib.auth import views as auth_views
from django.urls import path

# Only login/logout for this slice. Password reset, 2FA, SSO, and third-party
# auth are intentionally out of scope (see docs/DECISIONS/0005-custom-user-model.md),
# so django.contrib.auth.urls is not included wholesale.
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
