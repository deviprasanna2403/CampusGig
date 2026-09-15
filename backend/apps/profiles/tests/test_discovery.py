from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.profiles.models import BusinessProfile, Skill, StudentProfile, StudentSkill
from apps.profiles.tests.helpers import (
    BENGALURU_CAMPUS_A,
    BENGALURU_CAMPUS_B,
    TUMAKURU_CAMPUS_FAR,
    bearer_header,
    make_campus,
)

User = get_user_model()
STRONG_PASSWORD = "C@mpusGig-Str0ng!"


class StudentDiscoveryViewTests(APITestCase):
    """
    BENGALURU_CAMPUS_A and BENGALURU_CAMPUS_B are ~14 km apart (within the
    20 km default radius); TUMAKURU_CAMPUS_FAR is ~67 km away — outside
    the 20 km default, but within a 100 km widened radius.
    See apps/profiles/tests/helpers.py for the exact coordinates.
    """

    def setUp(self):
        self.campus_near_a = make_campus(**BENGALURU_CAMPUS_A)
        self.campus_near_b = make_campus(**BENGALURU_CAMPUS_B)
        self.campus_far = make_campus(**TUMAKURU_CAMPUS_FAR)

        self.business_user = User.objects.create_user(
            email="business@example.com", password=STRONG_PASSWORD, role=User.Role.BUSINESS
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user, business_name="Acme Co", campus=self.campus_near_a
        )

        self.python_skill = Skill.objects.create(name="Python")
        self.design_skill = Skill.objects.create(name="Graphic Design")

        self.near_student = self._make_student(
            "near@example.com", "Near Student", self.campus_near_a, [self.python_skill]
        )
        self.mid_student = self._make_student(
            "mid@example.com", "Mid Student", self.campus_near_b, [self.design_skill]
        )
        self.far_student = self._make_student(
            "far@example.com", "Far Student", self.campus_far, [self.python_skill]
        )

        self.url = reverse("profiles:discover-students")

    def _make_student(self, email, full_name, campus, skills):
        user = User.objects.create_user(email=email, password=STRONG_PASSWORD, role=User.Role.STUDENT)
        profile = StudentProfile.objects.create(user=user, full_name=full_name, campus=campus)
        for skill in skills:
            StudentSkill.objects.create(student=profile, skill=skill)
        return profile

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=bearer_header(user))

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_role_forbidden(self):
        self._auth_as(self.near_student.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_default_radius_uses_business_own_campus_and_excludes_far_student(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        names = {row["full_name"] for row in response.data["results"]}
        self.assertIn("Near Student", names)
        self.assertIn("Mid Student", names)
        self.assertNotIn("Far Student", names)

    def test_response_never_includes_email_phone_or_raw_coordinates(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url)
        for row in response.data["results"]:
            self.assertNotIn("email", row)
            self.assertNotIn("phone", row)
            self.assertNotIn("latitude", row)
            self.assertNotIn("longitude", row)
            self.assertNotIn("location", row)

    def test_explicit_campus_id_overrides_business_default(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"campus_id": str(self.campus_far.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["full_name"] for row in response.data["results"]}
        self.assertEqual(names, {"Far Student"})

    def test_radius_km_narrows_results(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"radius_km": "1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["full_name"] for row in response.data["results"]}
        self.assertEqual(names, {"Near Student"})

    def test_radius_km_can_be_widened_to_include_far_campus(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"radius_km": "100"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["full_name"] for row in response.data["results"]}
        self.assertIn("Far Student", names)

    def test_radius_km_out_of_bounds_rejected(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"radius_km": "500"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_skill_filter(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"skill": "Graphic Design"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["full_name"] for row in response.data["results"]}
        self.assertEqual(names, {"Mid Student"})

    def test_results_ordered_by_distance_ascending(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url)
        distances = [row["distance_km"] for row in response.data["results"]]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(response.data["results"][0]["full_name"], "Near Student")

    def test_missing_campus_id_and_no_business_campus_returns_400(self):
        other_business_user = User.objects.create_user(
            email="nobody@example.com", password=STRONG_PASSWORD, role=User.Role.BUSINESS
        )
        self._auth_as(other_business_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_campus_id_returns_400_not_500(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"campus_id": "not-a-uuid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_campus_id_returns_400(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url, {"campus_id": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_is_paginated(self):
        self._auth_as(self.business_user)
        response = self.client.get(self.url)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
