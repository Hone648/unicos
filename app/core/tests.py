from unittest.mock import patch

from accounts.authorization import ROLE_MANAGER
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


class HealthCheckTests(SimpleTestCase):
    def test_healthz_returns_ok_when_database_is_available(self):
        with (
            patch("core.views.connections") as connections,
            patch("core.views.check_media_storage") as check_media_storage,
        ):
            cursor = connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)

            response = self.client.get("/healthz/")

        check_media_storage.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "database": "ok",
                "media": "ok",
            },
        )

    def test_healthz_returns_service_unavailable_when_database_fails(self):
        with patch("core.views.connections") as connections:
            connections.__getitem__.side_effect = RuntimeError("database unavailable")

            response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(response.json()["database"], "error")
        self.assertEqual(response.json()["media"], "ok")
        self.assertIn("database unavailable", response.json()["errors"]["database"])

    def test_healthz_returns_service_unavailable_when_media_check_fails(self):
        with (
            patch("core.views.connections") as connections,
            patch("core.views.check_media_storage", side_effect=RuntimeError("media unwritable")),
        ):
            cursor = connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)

            response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(response.json()["database"], "ok")
        self.assertEqual(response.json()["media"], "error")
        self.assertIn("media unwritable", response.json()["errors"]["media"])


class HealthCheckPublicAccessTests(TestCase):
    def test_healthz_is_public(self):
        # No login; /healthz/ must not redirect to the login page.
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["media"], "ok")


class DashboardAccessTests(TestCase):
    PASSWORD = "pw-test-12345"

    def test_unauthenticated_dashboard_redirects_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/")

    def test_authenticated_user_can_access_dashboard(self):
        user = get_user_model().objects.create_user(username="tech", password=self.PASSWORD)
        assign_role(user, ROLE_MANAGER)
        self.client.login(username="tech", password=self.PASSWORD)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class LoginLogoutTests(TestCase):
    PASSWORD = "pw-test-12345"

    def test_login_page_returns_200(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)

    def test_successful_login_redirects_to_dashboard(self):
        get_user_model().objects.create_user(username="desk", password=self.PASSWORD)
        response = self.client.post(
            "/accounts/login/",
            {"username": "desk", "password": self.PASSWORD},
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_logout_via_post_redirects_to_login(self):
        get_user_model().objects.create_user(username="mgr", password=self.PASSWORD)
        self.client.login(username="mgr", password=self.PASSWORD)
        response = self.client.post("/accounts/logout/")
        self.assertRedirects(response, "/accounts/login/", fetch_redirect_response=False)
