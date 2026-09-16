"""
Phase 9B tests — analytics dashboards (admin / business / student).

Covers role gating, the default 30-day window, ?from/?to/?interval
validation, correct aggregation math over seeded data, and per-role data
scoping (a business/student never sees another user's numbers).
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Campus, StudentProfile
from apps.safety.models import Review

User = get_user_model()

ADMIN_URL = reverse("core:analytics-admin")
BUSINESS_URL = reverse("core:analytics-business-me")
STUDENT_URL = reverse("core:analytics-student-me")


def make_job(category, business_profile, title="Analytics Job", status=Job.Status.PUBLISHED):
    return Job.objects.create(
        business=business_profile,
        title=title,
        category=category,
        location=Point(77.5946, 12.9716, srid=4326),
        start_date=date.today(),
        end_date=date.today(),
        start_time=time(9, 0),
        end_time=time(17, 0),
        payment_amount="500",
        payment_type="DAILY",
        workers_required=1,
        application_deadline=date.today(),
        status=status,
    )


class AnalyticsPermissionTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="an-perm-admin@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.ADMIN,
        )
        self.student = User.objects.create_user(
            email="an-perm-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.business = User.objects.create_user(
            email="an-perm-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
        )

    def test_admin_endpoint_is_admin_only(self):
        response = self.client.get(ADMIN_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(ADMIN_URL).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.business)
        self.assertEqual(self.client.get(ADMIN_URL).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(ADMIN_URL).status_code, status.HTTP_200_OK)

    def test_business_endpoint_is_business_only(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(BUSINESS_URL).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(BUSINESS_URL).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.business)
        self.assertEqual(self.client.get(BUSINESS_URL).status_code, status.HTTP_200_OK)

    def test_student_endpoint_is_student_only(self):
        self.client.force_authenticate(self.business)
        self.assertEqual(self.client.get(STUDENT_URL).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(STUDENT_URL).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(STUDENT_URL).status_code, status.HTTP_200_OK)


class AdminAnalyticsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="an-admin@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.ADMIN,
        )
        self.client.force_authenticate(self.admin)

    def test_empty_platform_returns_zeroed_summary(self):
        response = self.client.get(ADMIN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["users"]["total"], 1)  # just the admin
        self.assertEqual(response.data["jobs"]["total"], 0)
        self.assertEqual(response.data["applications"]["selection_rate"], None)
        self.assertEqual(len(response.data["timeseries"]["new_jobs"]), 0)

    def test_counts_and_selection_rate(self):
        business_user = User.objects.create_user(
            email="an-data-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        campus = Campus.objects.create(
            name="An Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        profile = BusinessProfile.objects.create(
            user=business_user, business_name="An Co", campus=campus
        )
        category = JobCategory.objects.create(name="An Cat")
        job = make_job(category, profile, status=Job.Status.DRAFT)
        student_user = User.objects.create_user(
            email="an-data-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        student, _ = StudentProfile.objects.get_or_create(user=student_user)
        # One student, two DISTINCT jobs (job+student is unique).
        job2 = make_job(category, profile, title="Second Draft", status=Job.Status.DRAFT)
        Application.objects.create(job=job, student=student)
        Application.objects.create(job=job2, student=student, status=Application.Status.SELECTED)

        response = self.client.get(ADMIN_URL)
        self.assertEqual(response.data["users"]["total"], 3)
        self.assertEqual(response.data["jobs"]["by_status"]["DRAFT"], 2)
        self.assertEqual(response.data["applications"]["by_status"]["SUBMITTED"], 1)
        self.assertEqual(response.data["applications"]["by_status"]["SELECTED"], 1)
        # selection_rate = selected / all applications = 1/2.
        self.assertEqual(response.data["applications"]["selection_rate"], 0.5)
        self.assertEqual(response.data["users"]["by_role"]["business"], 1)

    def test_parameter_validation(self):
        response = self.client.get(ADMIN_URL, {"interval": "hourly"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # The custom error handler nests field errors under "details".
        self.assertIn("interval", str(response.data))

        response = self.client.get(ADMIN_URL, {"from": "2026-01-10", "to": "2026-01-01"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(ADMIN_URL, {"to": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_window_filters_new_in_window(self):
        business_user = User.objects.create_user(
            email="an-window-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        campus = Campus.objects.create(
            name="An Window Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        profile = BusinessProfile.objects.create(
            user=business_user, business_name="An Window Co", campus=campus
        )
        category = JobCategory.objects.create(name="An Window Cat")
        job = make_job(category, profile, title="Old Job", status=Job.Status.DRAFT)
        # Backdate the job out of a yesterday..today window.
        Job.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        today = date.today().isoformat()
        response = self.client.get(ADMIN_URL, {"from": yesterday, "to": today})
        self.assertEqual(response.data["jobs"]["total"], 1)  # total counts all jobs
        self.assertEqual(response.data["jobs"]["new_in_window"], 0)  # but not new in window


class BusinessAnalyticsTests(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(
            name="An Biz Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.category = JobCategory.objects.create(name="An Biz Cat")

        self.business_user = User.objects.create_user(
            email="an-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.profile = BusinessProfile.objects.create(
            user=self.business_user, business_name="An Biz Co", campus=self.campus
        )

        self.other_business_user = User.objects.create_user(
            email="an-biz-other@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.other_profile = BusinessProfile.objects.create(
            user=self.other_business_user, business_name="Other Co", campus=self.campus
        )

        self.my_job = make_job(self.category, self.profile, title="Mine", status=Job.Status.DRAFT)
        make_job(self.category, self.other_profile, title="Theirs", status=Job.Status.DRAFT)

    def test_scoped_to_own_jobs_and_applications(self):
        student_user = User.objects.create_user(
            email="an-biz-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        student, _ = StudentProfile.objects.get_or_create(user=student_user)
        Application.objects.create(job=self.my_job, student=student)

        self.client.force_authenticate(self.business_user)
        response = self.client.get(BUSINESS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only own jobs/applications are counted — never the other business's.
        self.assertEqual(response.data["jobs"]["total"], 1)
        self.assertEqual(response.data["applications"]["received"], 1)
        self.assertEqual(response.data["jobs"]["by_status"]["DRAFT"], 1)

    def test_rating_average_uses_published_reviews_about_the_business(self):
        # Reviews require a selected application on a completed (CLOSED) job,
        # so the fixture builds the full chain. Both reviews target the
        # business user: ratings 4 and 2 -> average 3.0.
        student_user = User.objects.create_user(
            email="an-biz-student2@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        student, _ = StudentProfile.objects.get_or_create(user=student_user)
        application = Application.objects.create(
            job=self.my_job, student=student, status=Application.Status.SELECTED
        )
        self.my_job.status = Job.Status.CLOSED
        self.my_job.save(update_fields=["status", "updated_at"])

        Review.objects.create(
            reviewer=self.other_business_user,
            reviewee=self.business_user,
            application=application,
            rating=4,
        )
        Review.objects.create(
            reviewer=student_user,
            reviewee=self.business_user,
            application=application,
            rating=2,
        )
        self.client.force_authenticate(self.business_user)
        response = self.client.get(BUSINESS_URL)
        self.assertEqual(response.data["rating_average"], 3.0)


class StudentAnalyticsTests(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(
            name="An Stu Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.category = JobCategory.objects.create(name="An Stu Cat")
        self.student_user = User.objects.create_user(
            email="an-stu@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.student, _ = StudentProfile.objects.get_or_create(user=self.student_user)

    def test_own_applications_summary(self):
        business_user = User.objects.create_user(
            email="an-stu-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        profile = BusinessProfile.objects.create(
            user=business_user, business_name="An Stu Co", campus=self.campus
        )
        # The nearby count needs the student registered at the campus.
        self.student.campus = self.campus
        self.student.save(update_fields=["campus", "updated_at"])
        # Applications attach via ORM to draft jobs; a separate PUBLISHED
        # job at the campus point drives the nearby-open-jobs count.
        job1 = make_job(self.category, profile, title="Applied Draft", status=Job.Status.DRAFT)
        job2 = make_job(self.category, profile, title="Withdrawn Draft", status=Job.Status.DRAFT)
        make_job(self.category, profile, title="Nearby Published", status=Job.Status.PUBLISHED)
        Application.objects.create(job=job1, student=self.student)
        Application.objects.create(job=job2, student=self.student, status=Application.Status.WITHDRAWN)

        self.client.force_authenticate(self.student_user)
        response = self.client.get(STUDENT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["applications"]["total"], 2)
        self.assertEqual(response.data["applications"]["withdrawn"], 1)
        # 0 selected of 2 total -> 0.0, not None (None only when there are none).
        self.assertEqual(response.data["applications"]["success_rate"], 0.0)
        self.assertIn("profile_completion_percentage", response.data)
        self.assertIn("open_jobs_near_campus", response.data)
        # One published job sits at the campus point, within the default radius.
        self.assertEqual(response.data["open_jobs_near_campus"], 1)

    def test_scoped_to_own_applications(self):
        other_student_user = User.objects.create_user(
            email="an-stu-other@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        other_student, _ = StudentProfile.objects.get_or_create(user=other_student_user)
        business_user = User.objects.create_user(
            email="an-stu-biz2@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        profile = BusinessProfile.objects.create(
            user=business_user, business_name="An Stu Co2", campus=self.campus
        )
        job = make_job(self.category, profile, status=Job.Status.DRAFT)
        Application.objects.create(job=job, student=other_student)

        self.client.force_authenticate(self.student_user)
        response = self.client.get(STUDENT_URL)
        self.assertEqual(response.data["applications"]["total"], 0)

    def test_student_without_campus_has_zero_nearby(self):
        business_user = User.objects.create_user(
            email="an-stu-nocampus-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        profile = BusinessProfile.objects.create(
            user=business_user, business_name="An Stu NoCampus Co", campus=self.campus
        )
        make_job(self.category, profile, status=Job.Status.DRAFT)

        self.client.force_authenticate(self.student_user)
        response = self.client.get(STUDENT_URL)
        self.assertEqual(response.data["open_jobs_near_campus"], 0)
