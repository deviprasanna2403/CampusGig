"""
F6 polish tests:

1. Interview notification bodies carry a human-readable timestamp
   ("20 Sep 2026, 09:00 IST") instead of a raw ISO string.
2. Actioning a JOB report takes the offending job down (CANCELLED) once,
   with owner notification and audit metadata.
3. Admin review moderation: list every review, hide/restore with required
   notes, audited as review.moderate, public list respects status.
"""

from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.core.models import AuditLog
from apps.jobs.models import Job, JobCategory
from apps.notifications.models import Notification
from apps.notifications.services import notify_interview
from apps.profiles.models import BusinessProfile, Campus, StudentProfile
from apps.safety.models import Report, Review

User = get_user_model()


class F6PolishFixture(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="polish-admin@example.com", password="C@mpusGig-Str0ng!", role=User.Role.ADMIN
        )
        self.business_user = User.objects.create_user(
            email="polish-biz@example.com", password="C@mpusGig-Str0ng!", role=User.Role.BUSINESS
        )
        self.student_user = User.objects.create_user(
            email="polish-student@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT
        )
        self.campus = Campus.objects.create(
            name="Polish Campus", city="Bengaluru", location=Point(77.5946, 12.9716, srid=4326)
        )
        self.profile = BusinessProfile.objects.create(
            user=self.business_user, business_name="Polish Co", campus=self.campus
        )
        self.category = JobCategory.objects.create(name="Polish Cat")
        self.student, _ = StudentProfile.objects.get_or_create(user=self.student_user)
        self.job = Job.objects.create(
            business=self.profile,
            title="Polish Job",
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
            status=Job.Status.PUBLISHED,
        )
        self.application = Application.objects.create(
            job=self.job, student=self.student, status=Application.Status.SELECTED
        )


class InterviewNotificationTimeTests(F6PolishFixture):
    def test_body_uses_human_readable_time_in_interview_zone(self):
        starts = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=3)
        interview = self.application.interviews.create(
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            proposed_by=self.business_user,
            timezone_name="Asia/Kolkata",
        )
        notify_interview(interview)
        body = Notification.objects.filter(
            recipient=self.student_user, event=Notification.Event.INTERVIEW_SCHEDULED
        ).first().body
        local = starts.astimezone(ZoneInfo("Asia/Kolkata"))
        self.assertNotIn(starts.isoformat(), body)
        self.assertIn(local.strftime("%d %b %Y, %H:%M"), body)
        self.assertIn("IST", body)
        self.assertIn("scheduled for", body)

    def test_updated_event_also_humanizes(self):
        starts = timezone.now() + timedelta(days=2)
        interview = self.application.interviews.create(
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            proposed_by=self.business_user,
            timezone_name="Asia/Kolkata",
        )
        notify_interview(interview, Notification.Event.INTERVIEW_UPDATED)
        notification = Notification.objects.filter(
            recipient=self.business_user, event=Notification.Event.INTERVIEW_UPDATED
        ).first()
        self.assertNotIn(starts.isoformat(), notification.body)
        self.assertEqual(notification.title, "Interview updated")

    def test_unknown_timezone_falls_back_to_project_zone(self):
        starts = timezone.now() + timedelta(days=1)
        interview = self.application.interviews.create(
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            proposed_by=self.business_user,
            timezone_name="Mars/Olympus",  # invalid on purpose
        )
        notify_interview(interview)
        body = Notification.objects.filter(
            recipient=self.student_user, event=Notification.Event.INTERVIEW_SCHEDULED
        ).first().body
        self.assertNotIn(starts.isoformat(), body)  # still humanized, no crash


class ReportJobTakedownTests(F6PolishFixture):
    def report(self):
        return Report.objects.create(
            reporter=self.student_user,
            target_type=Report.TargetType.JOB,
            target_id=self.job.id,
            category=Report.Category.FAKE_JOB,
            description="This listing looks fake.",
        )

    def test_actioned_job_report_cancels_job_and_notifies_owner(self):
        report = self.report()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("safety:report-admin-review", kwargs={"pk": report.id}),
            {"status": "ACTIONED", "resolution_notes": "Confirmed fake."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.CANCELLED)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.business_user, event=Notification.Event.JOB_TAKEN_DOWN
            ).exists()
        )
        audit = AuditLog.objects.filter(action="report.review", target_id=report.id).first()
        self.assertTrue(audit.metadata["job_taken_down"])

    def test_takedown_runs_once_per_report(self):
        report = self.report()
        self.client.force_authenticate(self.admin)
        url = reverse("safety:report-admin-review", kwargs={"pk": report.id})
        self.client.patch(url, {"status": "ACTIONED"}, format="json")
        self.job.status = Job.Status.PUBLISHED  # owner reopens
        self.job.save(update_fields=["status", "updated_at"])
        # Re-review of the already-ACTIONED report must not re-cancel.
        self.client.patch(url, {"status": "ACTIONED"}, format="json")
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PUBLISHED)

    def test_dismissed_or_non_job_reports_do_not_touch_jobs(self):
        report = self.report()
        self.client.force_authenticate(self.admin)
        self.client.patch(
            reverse("safety:report-admin-review", kwargs={"pk": report.id}),
            {"status": "DISMISSED"},
            format="json",
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PUBLISHED)
        audit = AuditLog.objects.filter(action="report.review", target_id=report.id).first()
        self.assertFalse(audit.metadata["job_taken_down"])

        other = Report.objects.create(
            reporter=self.student_user,
            target_type=Report.TargetType.APPLICATION,
            target_id=self.application.id,
            category=Report.Category.INAPPROPRIATE_CONTENT,
            description="Spam application content here.",
        )
        self.client.patch(
            reverse("safety:report-admin-review", kwargs={"pk": other.id}),
            {"status": "ACTIONED"},
            format="json",
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.PUBLISHED)

    def test_actioned_report_with_dangling_job_target_is_safe(self):
        # The job may be deleted between report and review; actioning must
        # still succeed and simply record that no takedown happened.
        report = Report.objects.create(
            reporter=self.student_user,
            target_type=Report.TargetType.JOB,
            target_id=self.job.id,
            category=Report.Category.FAKE_JOB,
            description="Job looks fake.",
        )
        self.job.delete()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("safety:report-admin-review", kwargs={"pk": report.id}),
            {"status": "ACTIONED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.ACTIONED)
        audit = AuditLog.objects.filter(action="report.review", target_id=report.id).first()
        self.assertFalse(audit.metadata["job_taken_down"])

    def test_notification_failure_does_not_block_takedown(self):
        # The owner notification is best-effort: a messaging failure must
        # never roll back the review decision or the takedown itself.
        report = self.report()
        self.client.force_authenticate(self.admin)
        with patch("apps.notifications.services.notify_job_taken_down", side_effect=RuntimeError("broker down")):
            response = self.client.patch(
                reverse("safety:report-admin-review", kwargs={"pk": report.id}),
                {"status": "ACTIONED"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.CANCELLED)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.ACTIONED)


class TakenDownJobVisibilityTests(F6PolishFixture):
    """F6: a taken-down (CANCELLED) job disappears from discovery but stays
    reachable — with a history flag — for students who applied to or engaged
    with it, so the UI can explain instead of 404ing."""

    def cancel_job(self):
        self.job.status = Job.Status.CANCELLED
        self.job.save(update_fields=["status", "updated_at"])

    def test_applicant_still_sees_cancelled_job_with_history_flag(self):
        self.cancel_job()
        self.client.force_authenticate(self.student_user)  # has a SELECTED application
        response = self.client.get(reverse("jobs:job-detail", kwargs={"pk": self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Job.Status.CANCELLED)
        self.assertTrue(response.data["viewer_has_history"])

    def test_student_with_only_engagement_still_sees_cancelled_job(self):
        from apps.matching.models import StudentJobEngagement

        StudentJobEngagement.objects.create(
            student=self.student, job=self.job, kind=StudentJobEngagement.Kind.SAVED
        )
        self.cancel_job()
        self.client.force_authenticate(self.student_user)
        response = self.client.get(reverse("jobs:job-detail", kwargs={"pk": self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["viewer_has_history"])

    def test_unrelated_student_still_gets_404_on_cancelled_job(self):
        other = User.objects.create_user(
            email="polish-outsider@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT
        )
        self.cancel_job()
        self.client.force_authenticate(other)
        response = self.client.get(reverse("jobs:job-detail", kwargs={"pk": self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_history_flag_false_for_open_job_without_history(self):
        outsider = User.objects.create_user(
            email="polish-nohistory@example.com", password="C@mpusGig-Str0ng!", role=User.Role.STUDENT
        )
        self.client.force_authenticate(outsider)
        response = self.client.get(reverse("jobs:job-detail", kwargs={"pk": self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["viewer_has_history"])


class StudentReportDuplicateTests(F6PolishFixture):
    def test_second_open_report_for_same_target_is_rejected(self):
        self.client.force_authenticate(self.student_user)
        first = self.client.post(
            reverse("safety:report-list"),
            {"target_type": "JOB", "target_id": str(self.job.id), "category": "PAYMENT_ISSUE", "description": "Asks for an off-platform deposit."},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            reverse("safety:report-list"),
            {"target_type": "JOB", "target_id": str(self.job.id), "category": "FAKE_JOB", "description": "Reporting the same job again."},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_report_allowed_again_after_resolution(self):
        self.client.force_authenticate(self.student_user)
        url = reverse("safety:report-list")
        payload = {"target_type": "JOB", "target_id": str(self.job.id), "category": "OTHER", "description": "First report, since resolved."}
        first = self.client.post(url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(self.admin)
        self.client.patch(
            reverse("safety:report-admin-review", kwargs={"pk": first.data["id"]}),
            {"status": "DISMISSED"},
            format="json",
        )
        # Resolved reports don't block a fresh report about the same target.
        self.client.force_authenticate(self.student_user)
        again = self.client.post(url, {**payload, "description": "New circumstances, reporting again."}, format="json")
        self.assertEqual(again.status_code, status.HTTP_201_CREATED)


class ReviewModerationTests(F6PolishFixture):
    def make_review(self):
        return Review.objects.create(
            application=self.application,
            reviewer=self.student_user,
            reviewee=self.business_user,
            rating=1,
            comment="Abusive content here.",
        )

    def test_admin_lists_all_reviews_including_hidden(self):
        review = self.make_review()
        review.status = Review.Status.HIDDEN
        review.save(update_fields=["status", "updated_at"])
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("safety:review-admin-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_non_admin_cannot_access_moderation(self):
        self.client.force_authenticate(self.business_user)
        response = self.client.get(reverse("safety:review-admin-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hide_requires_notes_and_hides_from_public_list(self):
        review = self.make_review()
        self.client.force_authenticate(self.admin)
        url = reverse("safety:review-admin-status", kwargs={"pk": review.id})
        response = self.client.patch(url, {"status": "HIDDEN"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.patch(
            url, {"status": "HIDDEN", "review_notes": "Abusive language."}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Review.Status.HIDDEN)
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.HIDDEN)

        self.client.force_authenticate(self.business_user)
        public = self.client.get(
            reverse("safety:review-list", kwargs={"user_id": self.business_user.id})
        )
        self.assertEqual(public.data["count"], 0)

    def test_reapplying_same_status_is_silent(self):
        # Idempotency: hiding an already-hidden review changes nothing and
        # must not append a second audit row.
        review = self.make_review()
        self.client.force_authenticate(self.admin)
        url = reverse("safety:review-admin-status", kwargs={"pk": review.id})
        self.client.patch(url, {"status": "HIDDEN", "review_notes": "First."}, format="json")
        response = self.client.patch(url, {"status": "HIDDEN", "review_notes": "Second."}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AuditLog.objects.filter(action="review.moderate", target_id=review.id).count(), 1)

    def test_admin_list_filters_by_status(self):
        self.make_review()
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("safety:review-admin-list"), {"status": "PUBLISHED"})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get(reverse("safety:review-admin-list"), {"status": "HIDDEN"})
        self.assertEqual(response.data["count"], 0)

    def test_restore_is_audited(self):
        review = self.make_review()
        self.client.force_authenticate(self.admin)
        url = reverse("safety:review-admin-status", kwargs={"pk": review.id})
        self.client.patch(url, {"status": "HIDDEN", "review_notes": "Abusive."}, format="json")
        self.client.patch(url, {"status": "PUBLISHED", "review_notes": "Appeal upheld."}, format="json")
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.PUBLISHED)
        audit = AuditLog.objects.filter(action="review.moderate", target_id=review.id)
        self.assertEqual(audit.count(), 2)
        self.assertEqual(
            list(audit.order_by("created_at").values_list("metadata__to_status", flat=True)),
            ["HIDDEN", "PUBLISHED"],
        )
