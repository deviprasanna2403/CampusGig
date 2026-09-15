from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.profiles.models import Skill, StudentProfile
from apps.profiles.tests.helpers import BENGALURU_CAMPUS_A, bearer_header, make_campus

User = get_user_model()
STRONG_PASSWORD = "C@mpusGig-Str0ng!"


class StudentProfileMeViewTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.business = User.objects.create_user(
            email="business@example.com", password=STRONG_PASSWORD, role=User.Role.BUSINESS
        )
        self.campus = make_campus(**BENGALURU_CAMPUS_A)
        self.url = reverse("profiles:student-me")

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_business_role_forbidden(self):
        self._auth_as(self.business)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_creates_profile_on_first_access(self):
        self.assertFalse(StudentProfile.objects.filter(user=self.student).exists())
        self._auth_as(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(StudentProfile.objects.filter(user=self.student).exists())
        self.assertEqual(response.data["completion_percentage"], 0)
        self.assertEqual(response.data["email"], "student@example.com")

    def test_patch_updates_full_name_and_campus(self):
        self._auth_as(self.student)
        response = self.client.patch(
            self.url,
            {"full_name": "Asha Rao", "campus_id": str(self.campus.id), "year_of_study": 2},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "Asha Rao")
        self.assertEqual(response.data["campus"]["id"], str(self.campus.id))
        self.assertEqual(response.data["completion_percentage"], 50)

    def test_get_does_not_duplicate_profile_on_repeated_calls(self):
        self._auth_as(self.student)
        self.client.get(self.url)
        self.client.get(self.url)
        self.assertEqual(StudentProfile.objects.filter(user=self.student).count(), 1)

    def test_email_and_id_are_read_only(self):
        self._auth_as(self.student)
        response = self.client.patch(
            self.url, {"email": "hacked@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "student@example.com")


class StudentSkillEndpointTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="skilled@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.other_student = User.objects.create_user(
            email="other@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.skill = Skill.objects.create(name="Python")
        self.list_url = reverse("profiles:student-skill-list")

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_add_skill(self):
        self._auth_as(self.student)
        response = self.client.post(
            self.list_url,
            {"skill_id": str(self.skill.id), "proficiency": "intermediate", "years_of_experience": 2},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["skill"]["name"], "Python")

    def test_cannot_add_same_skill_twice(self):
        self._auth_as(self.student)
        self.client.post(self.list_url, {"skill_id": str(self.skill.id)}, format="json")
        response = self.client.post(self.list_url, {"skill_id": str(self.skill.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_only_shows_own_skills(self):
        self._auth_as(self.student)
        self.client.post(self.list_url, {"skill_id": str(self.skill.id)}, format="json")

        self._auth_as(self.other_student)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_cannot_delete_another_students_skill(self):
        self._auth_as(self.student)
        add_response = self.client.post(self.list_url, {"skill_id": str(self.skill.id)}, format="json")
        skill_row_id = add_response.data["id"]

        self._auth_as(self.other_student)
        response = self.client.delete(
            reverse("profiles:student-skill-detail", args=[skill_row_id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_delete_own_skill(self):
        self._auth_as(self.student)
        add_response = self.client.post(self.list_url, {"skill_id": str(self.skill.id)}, format="json")
        skill_row_id = add_response.data["id"]

        response = self.client.delete(
            reverse("profiles:student-skill-detail", args=[skill_row_id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class AvailabilityEndpointTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="avail@example.com", password=STRONG_PASSWORD, role=User.Role.STUDENT
        )
        self.list_url = reverse("profiles:availability-list")

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_add_availability_slot(self):
        self._auth_as(self.student)
        response = self.client.post(
            self.list_url,
            {"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_end_before_start_rejected(self):
        self._auth_as(self.student)
        response = self.client.post(
            self.list_url,
            {"day_of_week": 0, "start_time": "12:00:00", "end_time": "09:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_overlapping_slot_rejected(self):
        self._auth_as(self.student)
        self.client.post(
            self.list_url,
            {"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
            format="json",
        )
        response = self.client.post(
            self.list_url,
            {"day_of_week": 1, "start_time": "11:00:00", "end_time": "13:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_own_slot(self):
        self._auth_as(self.student)
        create_response = self.client.post(
            self.list_url,
            {"day_of_week": 2, "start_time": "09:00:00", "end_time": "12:00:00"},
            format="json",
        )
        slot_id = create_response.data["id"]
        response = self.client.patch(
            reverse("profiles:availability-detail", args=[slot_id]),
            {"end_time": "13:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["end_time"], "13:00:00")
