from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.profiles.models import BusinessProfile
from apps.profiles.tests.helpers import BENGALURU_CAMPUS_A, bearer_header, make_campus

User = get_user_model()
STRONG_PASSWORD = "C@mpusGig-Str0ng!"


class BusinessProfileMeViewTests(APITestCase):
    def setUp(self):
        self.business = User.objects.create_user(
            email="business@example.com", password=STRONG_PASSWORD, role=User.Role.BUSINESS
        )
        self.student = User.objects.create_user(
            email="student@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.campus = make_campus(**BENGALURU_CAMPUS_A)
        self.url = reverse("profiles:business-me")

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_role_forbidden(self):
        self._auth_as(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_creates_profile_on_first_access(self):
        self.assertFalse(BusinessProfile.objects.filter(user=self.business).exists())
        self._auth_as(self.business)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(BusinessProfile.objects.filter(user=self.business).exists())

    def test_patch_updates_business_name_and_campus(self):
        self._auth_as(self.business)
        response = self.client.patch(
            self.url,
            {
                "business_name": "Acme Tutoring",
                "campus_id": str(self.campus.id),
                "description": "We hire student tutors.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["business_name"], "Acme Tutoring")
        self.assertEqual(response.data["campus"]["id"], str(self.campus.id))
        self.assertTrue(response.data["is_complete"])
