from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.profiles.models import Campus, Skill
from apps.profiles.tests.helpers import BENGALURU_CAMPUS_A, bearer_header, make_campus

User = get_user_model()
STRONG_PASSWORD = "C@mpusGig-Str0ng!"


class CampusViewSetTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.com", password=STRONG_PASSWORD
        )
        self.list_url = reverse("profiles:campus-list")

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_list_requires_authentication(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_student_can_list(self):
        make_campus(**BENGALURU_CAMPUS_A)
        self._auth_as(self.student)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_create_campus(self):
        self._auth_as(self.student)
        response = self.client.post(
            self.list_url,
            {"name": "New Campus", "city": "Delhi", "latitude": 28.6139, "longitude": 77.2090},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Campus.objects.filter(name="New Campus").exists())

    def test_admin_can_create_campus(self):
        self._auth_as(self.admin)
        response = self.client.post(
            self.list_url,
            {"name": "New Campus", "city": "Delhi", "latitude": 28.6139, "longitude": 77.2090},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Campus.objects.filter(name="New Campus").exists())

    def test_admin_create_rejects_invalid_latitude(self):
        self._auth_as(self.admin)
        response = self.client.post(
            self.list_url,
            {"name": "Bad Campus", "city": "X", "latitude": 999, "longitude": 0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_city(self):
        make_campus(**BENGALURU_CAMPUS_A)
        make_campus(name="Delhi Tech", city="Delhi", latitude=28.6139, longitude=77.2090)
        self._auth_as(self.student)
        response = self.client.get(self.list_url, {"city": "delhi"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["city"], "Delhi")

    def test_admin_delete_soft_deactivates_instead_of_hard_delete(self):
        campus = make_campus(**BENGALURU_CAMPUS_A)
        self._auth_as(self.admin)
        response = self.client.delete(reverse("profiles:campus-detail", args=[campus.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        campus.refresh_from_db()
        self.assertFalse(campus.is_active)
        self.assertTrue(Campus.objects.filter(pk=campus.pk).exists())


class SkillViewSetTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student2@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.admin = User.objects.create_superuser(
            email="admin2@example.com", password=STRONG_PASSWORD
        )
        self.list_url = reverse("profiles:skill-list")

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_authenticated_user_can_list_skills(self):
        Skill.objects.create(name="Python")
        self._auth_as(self.student)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_create_skill(self):
        self._auth_as(self.student)
        response = self.client.post(self.list_url, {"name": "Python"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_and_reject_duplicate_skill(self):
        self._auth_as(self.admin)
        first = self.client.post(self.list_url, {"name": "Python"}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        duplicate = self.client.post(self.list_url, {"name": "python"}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
