from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

STRONG_PASSWORD = "C@mpusGig-Str0ng!"


class RegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:register")

    def _payload(self, **overrides):
        payload = {
            "email": "newstudent@example.com",
            "phone": "+919876543210",
            "role": "student",
            "password": STRONG_PASSWORD,
            "password_confirm": STRONG_PASSWORD,
        }
        payload.update(overrides)
        return payload

    def test_register_student_returns_user_and_tokens(self):
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["email"], "newstudent@example.com")
        self.assertEqual(response.data["user"]["role"], "student")
        self.assertNotIn("password", response.data["user"])
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email="newstudent@example.com")
        self.assertTrue(user.check_password(STRONG_PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_verified)

    def test_register_business_role(self):
        response = self.client.post(
            self.url, self._payload(email="newbiz@example.com", role="business"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], "business")

    def test_register_rejects_admin_role(self):
        response = self.client.post(
            self.url, self._payload(email="sneaky@example.com", role="admin"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="sneaky@example.com").exists())

    def test_register_password_mismatch_returns_error_envelope(self):
        response = self.client.post(
            self.url,
            self._payload(email="mismatch@example.com", password_confirm="Different!23"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("password_confirm", response.data["error"]["details"])

    def test_register_duplicate_email_rejected(self):
        User.objects.create_user(email="dup@example.com", password=STRONG_PASSWORD)
        response = self.client.post(
            self.url, self._payload(email="dup@example.com"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password_rejected(self):
        response = self.client.post(
            self.url,
            self._payload(email="weak@example.com", password="12345678", password_confirm="12345678"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_invalid_phone_rejected(self):
        response = self.client.post(
            self.url, self._payload(email="badphone@example.com", phone="not-a-phone"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_without_phone_succeeds(self):
        payload = self._payload(email="nophone@example.com")
        payload.pop("phone")
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LoginTests(APITestCase):
    def setUp(self):
        self.url = reverse("accounts:login")
        self.user = User.objects.create_user(
            email="login@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )

    def test_login_success_returns_tokens_and_user(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "login@example.com")
        self.assertEqual(response.data["user"]["role"], "student")

    def test_login_wrong_password_fails(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "WrongPass!23"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unknown_email_fails(self):
        response = self.client.post(
            self.url, {"email": "nobody@example.com", "password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user_fails(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RefreshTests(APITestCase):
    def setUp(self):
        User.objects.create_user(email="refresh@example.com", password=STRONG_PASSWORD)
        login = self.client.post(
            reverse("accounts:login"),
            {"email": "refresh@example.com", "password": STRONG_PASSWORD},
            format="json",
        )
        self.refresh_token = login.data["refresh"]

    def test_refresh_returns_new_access_and_refresh_token(self):
        response = self.client.post(
            reverse("accounts:token-refresh"), {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        # ROTATE_REFRESH_TOKENS=True -> a new refresh token is also issued.
        self.assertIn("refresh", response.data)
        self.assertNotEqual(response.data["refresh"], self.refresh_token)

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        self.client.post(
            reverse("accounts:token-refresh"), {"refresh": self.refresh_token}, format="json"
        )
        # Reusing the same (now-rotated-away) refresh token must fail.
        retry = self.client.post(
            reverse("accounts:token-refresh"), {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(retry.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_with_garbage_token_fails(self):
        response = self.client.post(
            reverse("accounts:token-refresh"), {"refresh": "not-a-real-token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTests(APITestCase):
    def setUp(self):
        User.objects.create_user(email="logout@example.com", password=STRONG_PASSWORD)
        login = self.client.post(
            reverse("accounts:login"),
            {"email": "logout@example.com", "password": STRONG_PASSWORD},
            format="json",
        )
        self.access_token = login.data["access"]
        self.refresh_token = login.data["refresh"]

    def test_logout_blacklists_refresh_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(
            reverse("accounts:logout"), {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)

        retry = self.client.post(
            reverse("accounts:token-refresh"), {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(retry.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        response = self.client.post(
            reverse("accounts:logout"), {"refresh": self.refresh_token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_garbage_refresh_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        response = self.client.post(
            reverse("accounts:logout"), {"refresh": "not-a-real-token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MeEndpointTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="me@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        login = self.client.post(
            reverse("accounts:login"),
            {"email": "me@example.com", "password": STRONG_PASSWORD},
            format="json",
        )
        self.access_token = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_get_me_returns_current_user(self):
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")
        self.assertEqual(response.data["role"], "student")

    def test_patch_me_updates_phone(self):
        response = self.client.patch(
            reverse("accounts:me"), {"phone": "+919876543210"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+919876543210")

    def test_patch_me_rejects_invalid_phone(self):
        response = self.client.patch(reverse("accounts:me"), {"phone": "abc"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_me_ignores_role_change_attempt(self):
        response = self.client.patch(reverse("accounts:me"), {"role": "admin"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.STUDENT)

    def test_me_requires_authentication(self):
        self.client.credentials()  # clear auth header
        response = self.client.get(reverse("accounts:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class APIDocsTests(APITestCase):
    def test_schema_endpoint_is_publicly_accessible(self):
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_swagger_ui_is_publicly_accessible(self):
        response = self.client.get(reverse("swagger-ui"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
