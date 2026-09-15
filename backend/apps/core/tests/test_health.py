from django.test import Client, TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_health_check_returns_200_and_expected_payload(self):
        client = Client()
        response = client.get(reverse("core:health-check"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["project"], "CampusGig")
        self.assertEqual(payload["phase"], 2)
        self.assertIn("debug", payload)
