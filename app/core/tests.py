from unittest.mock import patch

from django.test import SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    def test_healthz_returns_ok_when_database_is_available(self):
        with patch("core.views.connections") as connections:
            cursor = connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)

            response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "database": "ok",
            },
        )

    def test_healthz_returns_service_unavailable_when_database_fails(self):
        with patch("core.views.connections") as connections:
            connections.__getitem__.side_effect = RuntimeError("database unavailable")

            response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(response.json()["database"], "error")
        self.assertIn("database unavailable", response.json()["error"])
