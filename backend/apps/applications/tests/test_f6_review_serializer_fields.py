"""
Phase F6 review-UI serializer fields.

The frontend gates the "Leave review" action and builds review URLs from
data the API did not expose before F6:

- ApplicationSerializer / BusinessApplicationSerializer: `job_status`
  (reviews require a completed job), `counterparty_id` (the other party's
  user id -> POST /safety/reviews/<user_id>/) and `my_review_rating`
  (what the caller already rated on this application, so the UI shows
  "you rated X" instead of offering a duplicate).
- JobSerializer: `business_user_id` (links a job page to the business's
  reviews page).
- ReviewSerializer: `reviewer_email` / `reviewee_email` display emails
  alongside the raw id fields (ids unchanged for API stability).
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Campus, StudentProfile
from apps.safety.models import Review

User = get_user_model()


class F6ReviewFieldTests(APITestCase):
    def setUp(self):
        self.business_user = User.objects.create_user(
            email="f6-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
        )
        self.student_user = User.objects.create_user(
            email="f6-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.other_student_user = User.objects.create_user(
            email="f6-other@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.campus = Campus.objects.create(
            name="F6 Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.profile = BusinessProfile.objects.create(
            user=self.business_user, business_name="F6 Co", campus=self.campus
        )
        self.category = JobCategory.objects.create(name="F6 Cat")
        self.student, _ = StudentProfile.objects.get_or_create(user=self.student_user)
        self.other_student, _ = StudentProfile.objects.get_or_create(user=self.other_student_user)
        self.job = Job.objects.create(
            business=self.profile,
            title="F6 Job",
            category=self.category,
            location=Point(77.5946, 12.9716, srid=4326),
            start_date=date.today(),
            end_date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            payment_amount=Decimal("500"),
            payment_type=Job.PaymentType.HOURLY,
            workers_required=1,
            application_deadline=date.today(),
            status=Job.Status.CLOSED,
        )
        self.application = Application.objects.create(
            job=self.job, student=self.student, status=Application.Status.SELECTED
        )

    # --- student-facing application serializer --------------------------------

    def test_student_application_exposes_f6_fields(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("applications:student-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["results"][0]
        self.assertEqual(row["job_status"], Job.Status.CLOSED)
        self.assertEqual(row["counterparty_id"], str(self.business_user.id))
        self.assertIsNone(row["my_review_rating"])

    def test_my_review_rating_reflects_existing_review(self):
        Review.objects.create(
            application=self.application,
            reviewer=self.student_user,
            reviewee=self.business_user,
            rating=4,
        )
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("applications:student-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["results"][0]
        self.assertEqual(row["my_review_rating"], 4)

    # --- business-facing application serializer -------------------------------

    def test_business_application_exposes_f6_fields(self):
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("applications:business-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["results"][0]
        self.assertEqual(row["job_status"], Job.Status.CLOSED)
        self.assertEqual(row["counterparty_id"], str(self.student_user.id))

    def test_my_review_rating_is_per_caller_not_per_application(self):
        # The student rated the business; the business's own view of the same
        # application must still show my_review_rating=None (they haven't
        # reviewed yet) — the field is caller-scoped, not application-scoped.
        Review.objects.create(
            application=self.application,
            reviewer=self.student_user,
            reviewee=self.business_user,
            rating=5,
        )
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("applications:business-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["results"][0]["my_review_rating"])

    # --- job serializer ---------------------------------------------------------

    def test_job_detail_exposes_business_user_id(self):
        # The owner sees their own CLOSED job through the detail endpoint
        # (students only see PUBLISHED/OPEN jobs — discovery rules).
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("jobs:job-detail", kwargs={"pk": self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["business_user_id"], str(self.business_user.id))

    # --- review serializer display emails ----------------------------------------

    def test_review_list_includes_display_emails(self):
        Review.objects.create(
            application=self.application,
            reviewer=self.student_user,
            reviewee=self.business_user,
            rating=5,
            comment="Solid work",
        )
        self.client.force_authenticate(self.business_user)
        response = self.client.get(
            reverse("safety:review-list", kwargs={"user_id": self.business_user.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["results"][0]
        self.assertEqual(str(row["reviewer"]), str(self.student_user.id))  # id field unchanged
        self.assertEqual(row["reviewer_email"], self.student_user.email)
        self.assertEqual(row["reviewee_email"], self.business_user.email)

    def test_completed_engagement_review_still_accepted(self):
        # Guard: the F6 display fields did not disturb the Phase 8 write path.
        self.client.force_authenticate(self.student_user)
        response = self.client.post(
            reverse("safety:review-list", kwargs={"user_id": self.business_user.id}),
            {"application": str(self.application.id), "rating": 5, "comment": "Great"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reviewer_email"], self.student_user.email)
