"""
Regression test (Phase 9B): StudentApplicationDetailView.perform_update used
to raise `serializers.ValidationError` while never importing `serializers`,
so every PATCH against a terminal (SELECTED/REJECTED/WITHDRAWN) application
crashed with a NameError -> HTTP 500. It must be a clean 400 instead.
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Campus, StudentProfile

User = get_user_model()


class TerminalApplicationUpdateRegressionTests(APITestCase):
    def setUp(self):
        self.business_user = User.objects.create_user(
            email="regr-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="regr-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.campus = Campus.objects.create(
            name="Regression Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.profile = BusinessProfile.objects.create(
            user=self.business_user, business_name="Regression Co", campus=self.campus
        )
        self.category = JobCategory.objects.create(name="Regression Cat")
        self.job = Job.objects.create(
            business=self.profile,
            title="Regression Job",
            category=self.category,
            location=Point(77.5946, 12.9716, srid=4326),
            start_date=date.today(),
            end_date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            payment_amount="500",
            payment_type="DAILY",
            workers_required=1,
            application_deadline=date.today(),
            status=Job.Status.PUBLISHED,
        )
        self.student, _ = StudentProfile.objects.get_or_create(user=self.student_user)
        self.application = Application.objects.create(job=self.job, student=self.student)

    def test_patch_on_terminal_application_returns_400_not_500(self):
        self.application.status = Application.Status.SELECTED
        self.application.save(update_fields=["status"])

        self.client.force_authenticate(self.student_user)
        response = self.client.patch(
            reverse("applications:student-detail", kwargs={"pk": self.application.id}),
            {"cover_note": "updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no longer be changed", str(response.data))

    def test_patch_on_active_application_still_succeeds(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(
            reverse("applications:student-detail", kwargs={"pk": self.application.id}),
            {"cover_note": "updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.application.refresh_from_db()
        self.assertEqual(self.application.cover_note, "updated")
