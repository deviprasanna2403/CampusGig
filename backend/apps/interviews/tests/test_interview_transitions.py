"""
Phase 6 follow-up (wired to the Phase F4 UI): InterviewDetailView accepted any
PATCH but silently ignored `status` (read-only field), so Confirm/Decline/
Cancel/Complete from the frontend could never work. Status is now writable
with role-aware transition validation.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.interviews.models import Interview
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Campus, StudentProfile

User = get_user_model()


def in_one_day(hour: int, minute: int = 0):
    start = (timezone.now() + timedelta(days=1)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return start, start + timedelta(minutes=45)


class InterviewTransitionTests(APITestCase):
    def setUp(self):
        self.business_user = User.objects.create_user(
            email="int-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="int-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.campus = Campus.objects.create(
            name="Interview Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.business = BusinessProfile.objects.create(
            user=self.business_user, business_name="Interview Co", campus=self.campus
        )
        self.category = JobCategory.objects.create(name="Interview Cat")
        self.job = Job.objects.create(
            business=self.business,
            title="Interview Job",
            category=self.category,
            location=Point(77.5946, 12.9716, srid=4326),
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=7),
            start_time=__import__("datetime").time(9, 0),
            end_time=__import__("datetime").time(17, 0),
            payment_amount="500",
            payment_type="DAILY",
            workers_required=1,
            application_deadline=timezone.localdate(),
            status=Job.Status.PUBLISHED,
        )
        self.student, _ = StudentProfile.objects.get_or_create(user=self.student_user)
        self.application = Application.objects.create(
            job=self.job, student=self.student, status=Application.Status.INTERVIEW
        )
        starts, ends = in_one_day(10)
        self.interview = Interview.objects.create(
            application=self.application,
            proposed_by=self.business_user,
            starts_at=starts,
            ends_at=ends,
        )

    def _url(self):
        return reverse("interviews:detail", kwargs={"pk": self.interview.id})

    def test_student_can_confirm_scheduled_interview(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(self._url(), {"status": "CONFIRMED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.Status.CONFIRMED)

    def test_student_can_decline_scheduled_interview(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(self._url(), {"status": "DECLINED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.Status.DECLINED)

    def test_student_cannot_cancel_scheduled_interview(self):
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(self._url(), {"status": "CANCELLED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_business_can_cancel_scheduled_interview(self):
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(self._url(), {"status": "CANCELLED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, Interview.Status.CANCELLED)

    def test_business_cannot_confirm_interview(self):
        self.client.force_authenticate(self.business_user)
        response = self.client.patch(self._url(), {"status": "CONFIRMED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirmed_interview_can_be_completed_by_either_party(self):
        self.interview.status = Interview.Status.CONFIRMED
        self.interview.save(update_fields=["status"])

        for user in (self.student_user, self.business_user):
            self.interview.status = Interview.Status.CONFIRMED
            self.interview.save(update_fields=["status"])
            self.client.force_authenticate(user)
            response = self.client.patch(self._url(), {"status": "COMPLETED"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_terminal_status_is_immutable(self):
        self.interview.status = Interview.Status.DECLINED
        self.interview.save(update_fields=["status"])
        self.client.force_authenticate(self.student_user)
        response = self.client.patch(self._url(), {"status": "CONFIRMED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_participant_cannot_update(self):
        outsider = User.objects.create_user(
            email="int-outsider@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.client.force_authenticate(outsider)
        response = self.client.patch(self._url(), {"status": "CONFIRMED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_is_ignored_on_create(self):
        """status stays a create-ignored field; interviews always start SCHEDULED."""
        self.client.force_authenticate(self.business_user)
        starts, ends = in_one_day(14)
        response = self.client.post(
            reverse("interviews:list"),
            {
                "application_id": self.application.id,
                "starts_at": starts.isoformat(),
                "ends_at": ends.isoformat(),
                "status": "COMPLETED",  # must be ignored
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], Interview.Status.SCHEDULED)

    def test_participants_receive_notification_on_transition(self):
        self.client.force_authenticate(self.student_user)
        self.client.patch(self._url(), {"status": "CONFIRMED"}, format="json")
        from apps.notifications.models import Notification

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.business_user, event=Notification.Event.INTERVIEW_UPDATED
            ).exists()
        )
