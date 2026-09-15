from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Campus, StudentProfile
from apps.safety.models import BusinessVerification, Report, Review
from apps.safety.services import RiskService, SafetyScoreService

User = get_user_model()


class SafetyFixtureMixin:
    def make_fixture(self):
        self.business_user = User.objects.create_user(email="safe-business@example.com", password="C@mpusGig-Str0ng!", role=User.Role.BUSINESS)
        self.student_user = User.objects.create_user(email="safe-student@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT)
        self.admin_user = User.objects.create_user(email="safe-admin@example.com", password="C@mpusGig-Str0ng!", role=User.Role.ADMIN)
        campus = Campus.objects.create(name="Safety Campus", city="Bengaluru", location=Point(77.5946, 12.9716, srid=4326))
        BusinessProfile.objects.create(user=self.business_user, business_name="Safe Business", campus=campus)
        self.student = StudentProfile.objects.create(user=self.student_user, full_name="Safe Student", campus=campus)
        self.category = JobCategory.objects.get(name__iexact="events")
        self.job = Job.objects.create(
            business=self.business_user.business_profile, title="Safety gig", description="Valid job", category=self.category,
            location=Point(77.5946, 12.9716, srid=4326), start_date=date(2026, 10, 20), end_date=date(2026, 10, 20),
            start_time=time(9), end_time=time(17), payment_amount=Decimal("500"), payment_type=Job.PaymentType.HOURLY,
            workers_required=1, application_deadline=date(2026, 10, 18), eligibility_notes="Welcome", status=Job.Status.CLOSED,
        )
        self.application = Application.objects.create(job=self.job, student=self.student, status=Application.Status.SELECTED)


class SafetyModelTests(SafetyFixtureMixin, TestCase):
    def setUp(self):
        self.make_fixture()

    def test_business_score_is_explainable_and_verification_increases_it(self):
        before = SafetyScoreService().calculate(self.business_user)
        verification = BusinessVerification.objects.create(business=self.business_user.business_profile, legal_name="Safe Business", status=BusinessVerification.Status.VERIFIED)
        after = SafetyScoreService().calculate(self.business_user)
        self.assertGreater(after.score, before.score)
        self.assertIn("verification", after.explanation)
        self.assertTrue(verification.is_verified)

    def test_student_score_uses_completed_gig(self):
        score = SafetyScoreService().calculate(self.student_user)
        self.assertGreaterEqual(score.score, Decimal("12"))
        self.assertEqual(score.strategy, "rule_based_reputation_v1")

    def test_review_requires_completed_selected_engagement(self):
        review = Review(application=self.application, reviewer=self.student_user, reviewee=self.business_user, rating=5)
        review.full_clean()
        self.assertEqual(review.rating, 5)

    def test_risk_detects_unverified_external_payment_and_is_modular(self):
        self.job.description = "Send money outside platform by crypto"
        self.job.save(update_fields=["description", "updated_at"])
        assessment = RiskService().assess_job(self.job)
        self.assertEqual(assessment.status, assessment.Status.REVIEW)
        self.assertIn("external_payment_request", assessment.signals)
        self.assertIn("unverified_business", assessment.signals)


class SafetyAPITests(SafetyFixtureMixin, APITestCase):
    def setUp(self):
        self.make_fixture()

    def test_business_verification_submission_and_admin_review(self):
        # Phase 9 flow: no fast-track — an admin must move the submission
        # to UNDER_REVIEW before it can reach VERIFIED, and approval now
        # syncs the business user's is_verified flag.
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("safety:verification"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(reverse("safety:verification"), {"legal_name": "Safe Business", "evidence": {"registration": "ref"}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.admin_user)
        verification = BusinessVerification.objects.get()
        response = self.client.patch(reverse("safety:verification-admin-review", kwargs={"pk": verification.id}), {"status": "VERIFIED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.patch(reverse("safety:verification-admin-review", kwargs={"pk": verification.id}), {"status": "UNDER_REVIEW"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.patch(reverse("safety:verification-admin-review", kwargs={"pk": verification.id}), {"status": "VERIFIED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        verification.refresh_from_db()
        self.assertEqual(verification.status, BusinessVerification.Status.VERIFIED)
        self.business_user.refresh_from_db()
        self.assertTrue(self.business_user.is_verified)

    def test_report_is_private_and_admin_can_review(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse("safety:report-list"), {"target_type": "JOB", "target_id": str(self.job.id), "category": "FAKE_JOB", "description": "This appears to be a scam listing."}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        report = Report.objects.get()
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("safety:report-detail", kwargs={"pk": report.id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.admin_user)
        response = self.client.patch(reverse("safety:report-admin-review", kwargs={"pk": report.id}), {"status": "VALID", "resolution_notes": "Confirmed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_duplicate_review_and_non_admin_risk_access_are_rejected(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.post(reverse("safety:review-list", kwargs={"user_id": self.business_user.id}), {"application": str(self.application.id), "rating": 5, "comment": "Good"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(reverse("safety:review-list", kwargs={"user_id": self.business_user.id}), {"application": str(self.application.id), "rating": 4}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(reverse("safety:risk-job-calculate", kwargs={"job_id": self.job.id}), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
