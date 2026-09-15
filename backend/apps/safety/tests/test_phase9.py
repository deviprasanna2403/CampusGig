"""
Phase 9: business verification integration & lifecycle.

Covers the approved Phase 9 scope:
- No fast-track: SUBMITTED must reach UNDER_REVIEW before VERIFIED/REJECTED.
- VERIFIED -> REVOKED is the only exit from verified; notes mandatory.
- Every transition writes VerificationHistory (audit trail) and syncs the
  business user's User.is_verified flag; decision events notify the business.
- Resubmission is only possible from REJECTED (via the business endpoint).
- Admin form edits cannot bypass the service (status is readonly in admin),
  and VerificationHistory is immutable via the admin.
- The Phase 5 publish gate opens only through this real workflow.
"""

from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.jobs.models import Job, JobCategory
from apps.notifications.models import Notification
from apps.profiles.models import BusinessProfile, Campus, StudentProfile
from apps.safety.models import BusinessVerification, VerificationHistory

User = get_user_model()


class VerificationFlowTests(APITestCase):
    def setUp(self):
        self.business_user = User.objects.create_user(
            email="phase9-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
        )
        self.student_user = User.objects.create_user(
            email="phase9-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.admin_user = User.objects.create_user(
            email="phase9-admin@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.ADMIN,
        )
        self.campus = Campus.objects.create(
            name="Phase9 Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user,
            business_name="Phase9 Business",
            campus=self.campus,
        )
        # The business-owned GET lazily creates the verification row.
        self.client.force_authenticate(self.business_user)
        self.client.get(reverse("safety:verification"))
        self.verification = BusinessVerification.objects.get(business=self.business_profile)
        self.client.force_authenticate(None)

    # ------------------------------------------------------------ helpers

    def admin_review(self, verification, payload):
        self.client.force_authenticate(self.admin_user)
        return self.client.patch(
            reverse("safety:verification-admin-review", kwargs={"pk": verification.id}),
            payload,
            format="json",
        )

    # ------------------------------------------------------- transitions

    def test_submission_starts_as_submitted(self):
        self.assertEqual(self.verification.status, BusinessVerification.Status.SUBMITTED)
        self.assertFalse(self.business_user.is_verified)

    def test_no_fast_track_from_submitted_to_verified_or_rejected(self):
        for target in ("VERIFIED", "REJECTED"):
            response = self.admin_review(self.verification, {"status": target})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.verification.refresh_from_db()
            self.assertEqual(self.verification.status, BusinessVerification.Status.SUBMITTED)

    def test_full_two_step_approval_syncs_is_verified_and_notifies(self):
        response = self.admin_review(self.verification, {"status": "UNDER_REVIEW"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.admin_review(self.verification, {"status": "VERIFIED", "review_notes": "Docs check out"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.verification.refresh_from_db()
        self.business_user.refresh_from_db()
        self.assertEqual(self.verification.status, BusinessVerification.Status.VERIFIED)
        self.assertTrue(self.verification.reviewed_at is not None)
        self.assertTrue(self.business_user.is_verified)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.business_user,
                event=Notification.Event.VERIFICATION_VERIFIED,
            ).exists()
        )
        # One history row per transition (UNDER_REVIEW, VERIFIED).
        self.assertEqual(VerificationHistory.objects.filter(verification=self.verification).count(), 2)

    def test_rejection_clears_flag_and_notifies(self):
        self.admin_review(self.verification, {"status": "UNDER_REVIEW"})
        response = self.admin_review(self.verification, {"status": "REJECTED", "review_notes": "Legible copy missing"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.verification.refresh_from_db()
        self.business_user.refresh_from_db()
        self.assertEqual(self.verification.status, BusinessVerification.Status.REJECTED)
        self.assertFalse(self.business_user.is_verified)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.business_user,
                event=Notification.Event.VERIFICATION_REJECTED,
            ).exists()
        )

    def test_resubmission_locks_and_rejected_path(self):
        # While SUBMITTED, the PATCH *is* the initial submission act —
        # details must stay editable and the row stays SUBMITTED.
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(
            reverse("safety:verification"),
            {"legal_name": "Phase9 Business", "evidence": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, BusinessVerification.Status.SUBMITTED)

        # Once under review the business is locked out.
        self.admin_review(self.verification, {"status": "UNDER_REVIEW"})
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(
            reverse("safety:verification"),
            {"legal_name": "Phase9 Business", "evidence": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # After a rejection, resubmission works and returns to SUBMITTED.
        self.admin_review(self.verification, {"status": "REJECTED", "review_notes": "Fix address"})
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(
            reverse("safety:verification"),
            {"legal_name": "Phase9 Business", "evidence": {"registration": "NEW-REF"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.verification.refresh_from_db()
        self.assertEqual(self.verification.status, BusinessVerification.Status.SUBMITTED)
        self.assertFalse(self.business_user.is_verified)

    # ---------------------------------------------------------- revocation

    def test_revoke_requires_notes_and_only_from_verified(self):
        self.admin_review(self.verification, {"status": "UNDER_REVIEW"})
        self.admin_review(self.verification, {"status": "VERIFIED"})
        self.business_user.refresh_from_db()
        self.assertTrue(self.business_user.is_verified)

        url = reverse("safety:verification-admin-revoke", kwargs={"pk": self.verification.id})
        self.client.force_authenticate(self.admin_user)

        # Notes are mandatory.
        response = self.client.patch(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.patch(url, {"review_notes": "Fake business report upheld"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.verification.refresh_from_db()
        self.business_user.refresh_from_db()
        self.assertEqual(self.verification.status, BusinessVerification.Status.REVOKED)
        self.assertFalse(self.business_user.is_verified)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.business_user,
                event=Notification.Event.VERIFICATION_REVOKED,
            ).exists()
        )

    # ------------------------------------------------------- permissions

    def test_non_admin_cannot_review_or_revoke(self):
        review_url = reverse(
            "safety:verification-admin-review", kwargs={"pk": self.verification.id}
        )
        revoke_url = reverse(
            "safety:verification-admin-revoke", kwargs={"pk": self.verification.id}
        )
        for user in (self.business_user, self.student_user):
            self.client.force_authenticate(user)
            self.assertEqual(
                self.client.patch(review_url, {"status": "UNDER_REVIEW"}, format="json").status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(
                self.client.patch(revoke_url, {"review_notes": "x"}, format="json").status_code,
                status.HTTP_403_FORBIDDEN,
            )

    # ------------------------------------------------------------- admin

    def test_admin_form_cannot_change_status(self):
        """Status is readonly in the admin change form: a POST to the admin
        change page must not be able to flip the status behind the
        service's back."""
        self.admin_user.is_staff = True
        self.admin_user.save()
        self.client.force_authenticate(self.admin_user)

        from django.contrib import admin as django_admin

        from apps.safety.admin import BusinessVerificationAdmin

        model_admin = BusinessVerificationAdmin(BusinessVerification, django_admin.site)
        self.assertIn("status", model_admin.readonly_fields)
        self.assertIn("reviewed_by", model_admin.readonly_fields)

        # The audit trail is fully immutable through the admin.
        from apps.safety.admin import VerificationHistoryAdmin

        history_admin = VerificationHistoryAdmin(VerificationHistory, django_admin.site)
        self.assertFalse(history_admin.has_add_permission(self.client))
        self.assertFalse(history_admin.has_change_permission(self.client, None))
        self.assertFalse(history_admin.has_delete_permission(self.client, None))

    # ------------------------------------------------- Phase 5 bridge E2E

    def test_verified_business_can_publish_job_end_to_end(self):
        """The bridge test: approval through the real admin flow must open
        the Phase 5 publish gate (IsVerified), with no fixture shortcuts."""
        category = JobCategory.objects.get(name__iexact="events")
        payload = {
            "title": "Bridge Gig",
            "description": "Created before verification.",
            "category": "events",
            "job_type": "ONE_DAY_GIG",
            "payment_type": "HOURLY",
            "payment_amount": "300.00",
            "location_latitude": 12.9716,
            "location_longitude": 77.5946,
            "start_date": str(date(2026, 11, 1)),
            "end_date": str(date(2026, 11, 1)),
            "start_time": str(time(9, 0)),
            "end_time": str(time(17, 0)),
            "workers_required": 1,
            "application_deadline": str(date(2026, 10, 30)),
            "eligibility_notes": "Students only.",
        }

        # Pre-verification: publish is blocked by the IsVerified gate.
        self.client.force_authenticate(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        blocked = self.client.post(
            reverse("jobs:job-publish", kwargs={"pk": created.data["id"]}), format="json"
        )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)

        # Real approval flow: SUBMITTED -> UNDER_REVIEW -> VERIFIED.
        self.admin_review(self.verification, {"status": "UNDER_REVIEW"})
        self.admin_review(self.verification, {"status": "VERIFIED"})
        self.business_user.refresh_from_db()
        self.assertTrue(self.business_user.is_verified)

        # Now the gate opens.
        self.client.force_authenticate(self.business_user)
        published = self.client.post(
            reverse("jobs:job-publish", kwargs={"pk": created.data["id"]}), format="json"
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertEqual(published.data["status"], "PUBLISHED")
