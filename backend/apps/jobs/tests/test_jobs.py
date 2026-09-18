from datetime import date, time

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.profiles.models import BusinessProfile, Campus

User = get_user_model()


class JobPhase5Tests(APITestCase):
    def setUp(self):
        # is_verified=True: publishing requires a verified business
        # (Phase 5 rule wired via IsVerified). The unverified case has its
        # own dedicated test below.
        self.business_user = User.objects.create_user(
            email="biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.ADMIN,
        )

        self.campus = Campus.objects.create(
            name="Campus A",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user,
            business_name="CampusGig Hiring",
            campus=self.campus,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def payload(self, **overrides):
        data = {
            "title": "Campus Event Helper",
            "description": "Help manage event operations.",
            "category": "events",
            "job_type": "ONE_DAY_GIG",
            "payment_type": "HOURLY",
            "payment_amount": "500.00",
            "location_latitude": 12.9716,
            "location_longitude": 77.5946,
            "start_date": str(date(2026, 9, 20)),
            "end_date": str(date(2026, 9, 20)),
            "start_time": str(time(9, 0)),
            "end_time": str(time(17, 0)),
            "workers_required": 3,
            "application_deadline": str(date(2026, 9, 18)),
            "eligibility_notes": "Must be enrolled in college.",
            "status": "DRAFT",
        }
        data.update(overrides)
        return data

    def test_business_can_create_valid_job(self):
        self.auth(self.business_user)
        response = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Campus Event Helper")

    def test_student_cannot_create_job(self):
        self.auth(self.student_user)
        response = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_required_field_validation(self):
        self.auth(self.business_user)
        response = self.client.post(
            reverse("jobs:job-list"),
            {"title": "Missing fields"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("description", response.data["error"]["details"])

    def test_invalid_payment_validation(self):
        self.auth(self.business_user)
        response = self.client.post(
            reverse("jobs:job-list"),
            self.payload(payment_amount="-10"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_worker_count(self):
        self.auth(self.business_user)
        response = self.client.post(
            reverse("jobs:job-list"),
            self.payload(workers_required=0),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_valid_job(self):
        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        job_id = created.data["id"]
        response = self.client.post(reverse("jobs:job-publish", kwargs={"pk": job_id}), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PUBLISHED")

    def test_publishing_incomplete_job_fails(self):
        self.auth(self.business_user)
        created = self.client.post(
            reverse("jobs:job-list"),
            self.payload(title="Draft incomplete", description="", payment_amount="500.00"),
            format="json",
        )
        response = self.client.post(
            reverse("jobs:job-publish", kwargs={"pk": created.data["id"]}),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_close_and_reopen_job(self):
        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        self.client.post(reverse("jobs:job-publish", kwargs={"pk": created.data["id"]}), format="json")

        close = self.client.post(reverse("jobs:job-close", kwargs={"pk": created.data["id"]}), format="json")
        self.assertEqual(close.status_code, status.HTTP_200_OK)
        self.assertEqual(close.data["status"], "CLOSED")

        reopen = self.client.post(reverse("jobs:job-reopen", kwargs={"pk": created.data["id"]}), format="json")
        self.assertEqual(reopen.status_code, status.HTTP_200_OK)
        self.assertEqual(reopen.data["status"], "OPEN")

    def test_student_can_view_nearby_jobs(self):
        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(title="Nearby Gig"), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        published = self.client.post(
            reverse("jobs:job-publish", kwargs={"pk": created.data["id"]}), format="json"
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK)

        self.auth(self.student_user)
        # The student has no campus on their profile, so the reference
        # campus must come from the explicit campus_id query param.
        response = self.client.get(
            reverse("jobs:job-nearby"),
            {"campus_id": str(self.campus.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The job sits at the campus coordinates, so it must be found.
        self.assertGreaterEqual(response.data["count"], 1)

    def test_business_cannot_edit_another_business_job(self):
        other_business = User.objects.create_user(
            email="otherbiz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
        )
        other_business_profile = BusinessProfile.objects.create(
            user=other_business,
            business_name="Other Company",
            campus=self.campus,
        )
        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(title="Owned"), format="json")
        self.auth(other_business)
        response = self.client.patch(
            reverse("jobs:job-detail", kwargs={"pk": created.data["id"]}),
            {"title": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------- Phase 5 gap fixes

    def test_nearby_without_any_campus_returns_400(self):
        """Neither campus_id nor a campus on the student profile must be a
        clean 400 — not a silently unfiltered list of every open job."""
        self.auth(self.student_user)
        response = self.client.get(reverse("jobs:job-nearby"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campus", response.data["error"]["message"])

    def test_nearby_rejects_invalid_radius_km(self):
        """radius_km must be a positive number within the configured ceiling —
        non-numeric, <=0, and above MAX_DISCOVERY_RADIUS_KM are 400s, never a
        500 from an unhandled ValueError or an unbounded proximity scan."""
        self.auth(self.student_user)
        response = self.client.get(
            reverse("jobs:job-nearby"), {"radius_km": "abc"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(
            reverse("jobs:job-nearby"), {"radius_km": "0"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nearby_rejects_radius_km_above_ceiling(self):
        """radius_km beyond MAX_DISCOVERY_RADIUS_KM is a clean 400 naming the
        limit; a value at the ceiling is accepted."""
        from django.conf import settings as dj_settings

        self.auth(self.student_user)
        campus_id = self.campus.id
        response = self.client.get(
            reverse("jobs:job-nearby"),
            {"campus_id": str(campus_id), "radius_km": dj_settings.MAX_DISCOVERY_RADIUS_KM + 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(str(dj_settings.MAX_DISCOVERY_RADIUS_KM), response.data["error"]["message"])

        response = self.client.get(
            reverse("jobs:job-nearby"),
            {"campus_id": str(campus_id), "radius_km": dj_settings.MAX_DISCOVERY_RADIUS_KM},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sort_distance_without_campus_returns_400(self):
        """?sort=distance with no resolvable campus (no campus_id param,
        no campus on any profile) is a clean 400, not a 500."""
        self.auth(self.admin_user)  # admin has no student/business profile
        response = self.client.get(
            reverse("jobs:job-list"), {"sort": "distance"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campus", response.data["error"]["message"])

    def test_unverified_business_cannot_publish(self):
        """Only verified businesses can publish (IsVerified gate)."""
        unverified = User.objects.create_user(
            email="unverified@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
        )
        BusinessProfile.objects.create(
            user=unverified,
            business_name="Unverified Co",
            campus=self.campus,
        )
        self.auth(unverified)
        created = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            reverse("jobs:job-publish", kwargs={"pk": created.data["id"]}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("verified", response.data["error"]["message"])

    def test_job_response_echoes_coordinates(self):
        """The stored location must be readable from responses via
        location_latitude/location_longitude (previously write-only)."""
        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["location_latitude"], 12.9716)
        self.assertEqual(created.data["location_longitude"], 77.5946)

    def test_delete_in_use_category_returns_409(self):
        """Deleting a category referenced by a job must return a clean 409,
        not a 500 from the escaped ProtectedError."""
        self.auth(self.admin_user)
        self.admin_user.is_staff = True
        self.admin_user.save()

        created = self.client.post(
            reverse("jobs:category-list"), {"name": "Temp Cat"}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        self.auth(self.business_user)
        job = self.client.post(
            reverse("jobs:job-list"),
            self.payload(category="Temp Cat"),
            format="json",
        )
        self.assertEqual(job.status_code, status.HTTP_201_CREATED)

        self.auth(self.admin_user)
        response = self.client.delete(
            reverse("jobs:category-detail", kwargs={"pk": created.data["id"]}),
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("referenced", response.data["error"]["message"])

    def test_unchanged_protected_fields_patch_ok_changed_rejected(self):
        """PATCHing a published job with an unchanged protected value is
        allowed (value-based check); a genuinely changed one is a 400."""
        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        job_id = created.data["id"]
        self.client.post(reverse("jobs:job-publish", kwargs={"pk": job_id}), format="json")

        # Unchanged protected fields resubmitted alongside an allowed edit.
        ok = self.client.patch(
            reverse("jobs:job-detail", kwargs={"pk": job_id}),
            {
                "title": created.data["title"],
                "payment_amount": created.data["payment_amount"],
                "description": "Updated description",
            },
            format="json",
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.data["description"], "Updated description")

        # Actually changing a protected field is still rejected.
        bad = self.client.patch(
            reverse("jobs:job-detail", kwargs={"pk": job_id}),
            {"title": "New Title"},
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("protected", bad.data["error"]["details"]["title"][0])

    def test_cancel_notifies_applicants(self):
        """Cancelling a job must create a JOB_CANCELLED notification for
        every student with an application on it."""
        from apps.applications.models import Application
        from apps.notifications.models import Notification
        from apps.profiles.models import StudentProfile

        self.auth(self.business_user)
        created = self.client.post(reverse("jobs:job-list"), self.payload(), format="json")
        job_id = created.data["id"]
        self.client.post(reverse("jobs:job-publish", kwargs={"pk": job_id}), format="json")

        student_profile = StudentProfile.objects.create(user=self.student_user)
        Application.objects.create(job_id=job_id, student=student_profile)

        self.auth(self.business_user)
        response = self.client.post(
            reverse("jobs:job-cancel", kwargs={"pk": job_id}), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student_user,
                event=Notification.Event.JOB_CANCELLED,
            ).exists()
        )

    def test_job_list_is_paginated(self):
        """The list endpoint must use the project pagination envelope."""
        self.auth(self.business_user)
        for i in range(3):
            self.client.post(
                reverse("jobs:job-list"), self.payload(title=f"Gig {i}"), format="json"
            )
        response = self.client.get(reverse("jobs:job-list"), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
