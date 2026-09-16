"""
Phase 9B tests — the generic audit trail.

Covers:
- AuditService.log() writes immutable rows with actor/actor_role snapshots,
  target type/id mapping, and metadata enrichment (IP/user-agent).
- The API is admin-only and read-only: students/businesses get 403; there
  are no write endpoints (POST/PUT/PATCH/DELETE are 405, never effective).
- Filtering by action, target_type, target_id, actor, and date range.
- Every Phase 9B call site writes exactly one row: job lifecycle actions,
  application submit/withdraw/status change, verification review.
- Query efficiency (loose ceiling per the approved plan — correctness is
  the criterion, not an exact query count).
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import Application
from apps.core.audit import AuditService
from apps.core.models import AuditLog
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Campus, Skill, StudentProfile
from apps.safety.models import BusinessVerification, Report

User = get_user_model()


def make_job(category, business_profile, title="Audit Job"):
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
        status=Job.Status.PUBLISHED,
    )


class AuditLogAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="audit-admin@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.ADMIN,
        )
        self.student = User.objects.create_user(
            email="audit-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.url = reverse("core:audit-logs")

    def test_requires_authentication(self):
        AuditService.log(action="system.ping", target=Job())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_only_access(self):
        AuditService.log(action="system.ping", target=Job())
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["action"], "system.ping")

    def test_system_action_has_null_actor_and_role_snapshot(self):
        row = AuditService.log(action="system.maintenance", target=Job())
        self.assertIsNone(row.actor)
        self.assertEqual(row.actor_role, "")

        row = AuditService.log(action="system.ping", actor=self.student, target=Job())
        self.assertEqual(row.actor, self.student)
        self.assertEqual(row.actor_role, User.Role.STUDENT)

    def test_target_instance_maps_type_and_id(self):
        job = Job(id="11111111-1111-5111-8111-111111111111")  # unsaved; pk only
        row = AuditService.log(action="job.publish", actor=self.admin, target=job)
        self.assertEqual(row.target_type, AuditLog.TargetType.JOB)
        self.assertEqual(str(row.target_id), str(job.pk))

    def test_target_without_mapped_type_uses_model_name(self):
        # Skill is NOT in the explicit _TARGET_TYPES map — the fallback
        # derives the upper-snake name from the model itself.
        row = AuditService.log(action="system.maintenance", target=Skill())
        self.assertEqual(row.target_type, "SKILL")

    def test_mapped_types_resolve_via_map(self):
        for model_cls, expected in (
            (Job, AuditLog.TargetType.JOB),
            (Application, AuditLog.TargetType.APPLICATION),
            (BusinessVerification, AuditLog.TargetType.BUSINESS_VERIFICATION),
            (Report, AuditLog.TargetType.REPORT),
        ):
            row = AuditService.log(action="system.ping", target=model_cls())
            self.assertEqual(row.target_type, expected)

    def test_metadata_and_request_enrichment(self):
        request = RequestFactory().get("/", HTTP_USER_AGENT="pytest-agent")
        row = AuditService.log(
            action="job.publish",
            actor=self.admin,
            target=Job(),
            metadata={"title": "T", "ip": "1.2.3.4"},
            request=request,
        )
        # Request enriches ip/user-agent only; explicit keys are never clobbered.
        self.assertEqual(row.metadata["title"], "T")
        self.assertEqual(row.metadata["ip"], "1.2.3.4")
        self.assertEqual(row.metadata["user_agent"], "pytest-agent")

    def test_no_update_or_delete_methods_on_service(self):
        self.assertFalse(hasattr(AuditService, "update"))
        self.assertFalse(hasattr(AuditService, "delete"))

    # --------------------------------------------------------- filters

    def test_filter_by_action_and_target_type(self):
        AuditService.log(action="job.publish", target=Job())
        AuditService.log(action="application.submit", target=Application())

        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url, {"action": "job.publish"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["action"], "job.publish")

        response = self.client.get(self.url, {"target_type": "application"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["target_type"], "APPLICATION")

    def test_filter_by_actor_and_date_range(self):
        AuditService.log(action="job.publish", actor=self.admin, target=Job())
        AuditService.log(action="job.close", actor=self.student, target=Job())

        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url, {"actor": str(self.admin.id)})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["action"], "job.publish")

        today = date.today().isoformat()
        response = self.client.get(self.url, {"from": today, "to": today})
        self.assertEqual(response.data["count"], 2)

        response = self.client.get(self.url, {"from": "1999-01-01", "to": "1999-12-31"})
        self.assertEqual(response.data["count"], 0)

    def test_invalid_date_and_uuid_filters_return_400(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url, {"from": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(self.url, {"target_id": "not-a-uuid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_immutability_no_write_endpoints(self):
        """The API surface must be GET-only: POST/PUT/PATCH/DELETE must not
        be routable to any view that could create or modify audit rows."""
        self.client.force_authenticate(self.admin)
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)(self.url, {}, format="json")
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
                msg=f"{method.upper()} must be 405 on the audit list",
            )

    def test_list_page_query_count_is_bounded(self):
        """Loose N+1 guard: a paginated 30-row page stays well under the
        row count (no per-row queries). Not a rigid single-digit rule."""
        for i in range(30):
            AuditService.log(action="system.ping", actor=self.admin, target=Job())
        self.client.force_authenticate(self.admin)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(ctx.captured_queries), 8)


class JobLifecycleAuditTests(APITestCase):
    """Each job lifecycle action must write exactly one audit row."""

    def setUp(self):
        self.business_user = User.objects.create_user(
            email="audit-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.campus = Campus.objects.create(
            name="Audit Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user,
            business_name="Audit Co",
            campus=self.campus,
        )
        self.category = JobCategory.objects.create(name="Audit Cat")
        self.client.force_authenticate(self.business_user)

    def _create_job(self, title="Audit Job"):
        # "category" is matched by name (see JobSerializer.validate); the
        # write-only PK field is "category_id".
        return self.client.post(
            reverse("jobs:job-list"),
            {
                "title": title,
                "description": "desc",
                "category": self.category.name,
                "job_type": "ONE_DAY_GIG",
                "location_latitude": 12.9716,
                "location_longitude": 77.5946,
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
                "start_time": "09:00",
                "end_time": "17:00",
                "payment_amount": "500",
                "payment_type": "DAILY",
                "workers_required": 1,
                "application_deadline": date.today().isoformat(),
                "eligibility_notes": "Must be enrolled.",
            },
            format="json",
        )

    def test_publish_close_reopen_cancel_write_one_row_each(self):
        created = self._create_job()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        job_id = created.data["id"]
        self.assertEqual(AuditLog.objects.count(), 0)  # creation isn't audited

        self.client.post(reverse("jobs:job-publish", kwargs={"pk": job_id}), format="json")
        self.assertEqual(AuditLog.objects.filter(action="job.publish").count(), 1)

        self.client.post(reverse("jobs:job-close", kwargs={"pk": job_id}), format="json")
        self.assertEqual(AuditLog.objects.filter(action="job.close").count(), 1)

        self.client.post(reverse("jobs:job-reopen", kwargs={"pk": job_id}), format="json")
        self.assertEqual(AuditLog.objects.filter(action="job.reopen").count(), 1)

        self.client.post(reverse("jobs:job-cancel", kwargs={"pk": job_id}), format="json")
        self.assertEqual(AuditLog.objects.filter(action="job.cancel").count(), 1)

        row = AuditLog.objects.filter(action="job.publish").get()
        self.assertEqual(row.target_type, "JOB")
        self.assertEqual(str(row.target_id), str(job_id))
        self.assertEqual(row.metadata["from_status"], "DRAFT")
        self.assertEqual(row.metadata["to_status"], "PUBLISHED")
        self.assertEqual(row.actor_role, User.Role.BUSINESS)

    def test_failed_action_writes_no_row(self):
        created = self._create_job()
        # Closing a DRAFT job is rejected -> no audit row.
        self.client.post(reverse("jobs:job-close", kwargs={"pk": created.data["id"]}), format="json")
        self.assertEqual(AuditLog.objects.count(), 0)


class ApplicationLifecycleAuditTests(APITestCase):
    def setUp(self):
        self.business_user = User.objects.create_user(
            email="audit-app-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
            is_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="audit-app-student@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.STUDENT,
        )
        self.campus = Campus.objects.create(
            name="Audit App Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user,
            business_name="Audit App Co",
            campus=self.campus,
        )
        self.category = JobCategory.objects.create(name="Audit App Cat")
        self.job = make_job(self.category, self.business_profile, title="Audit App Job")
        self.student, _ = StudentProfile.objects.get_or_create(user=self.student_user)

    def _apply(self):
        self.client.force_authenticate(self.student_user)
        return self.client.post(
            reverse("applications:student-list"),
            {"job_id": str(self.job.id), "cover_note": "hi"},
            format="json",
        )

    def test_submit_writes_audit_row(self):
        response = self._apply()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        row = AuditLog.objects.get(action="application.submit")
        self.assertEqual(str(row.target_id), str(response.data["id"]))
        self.assertEqual(row.target_type, "APPLICATION")
        self.assertEqual(row.metadata["job_title"], "Audit App Job")

    def test_withdraw_writes_audit_row_with_status_transition(self):
        response = self._apply()
        application_id = response.data["id"]
        # WithdrawView is an UpdateAPIView: PATCH (not POST) drives update().
        self.client.patch(
            reverse("applications:student-withdraw", kwargs={"pk": application_id}), format="json"
        )
        row = AuditLog.objects.get(action="application.withdraw")
        self.assertEqual(row.metadata["from_status"], "SUBMITTED")
        self.assertEqual(row.metadata["to_status"], "WITHDRAWN")

    def test_business_status_change_writes_audit_row(self):
        response = self._apply()
        application_id = response.data["id"]
        self.client.force_authenticate(self.business_user)
        self.client.patch(
            reverse("applications:business-detail", kwargs={"pk": application_id}),
            {"status": "SHORTLISTED"},
            format="json",
        )
        row = AuditLog.objects.get(action="application.status_change")
        self.assertEqual(row.metadata["from_status"], "SUBMITTED")
        self.assertEqual(row.metadata["to_status"], "SHORTLISTED")
        self.assertEqual(row.actor_role, User.Role.BUSINESS)


class VerificationAndReportAuditTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="audit-v-admin@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.ADMIN,
        )
        self.business_user = User.objects.create_user(
            email="audit-v-biz@example.com",
            password="C@mpusGig-Str0ng!",
            role=User.Role.BUSINESS,
        )
        self.campus = Campus.objects.create(
            name="Audit V Campus",
            city="Bengaluru",
            location=Point(77.5946, 12.9716, srid=4326),
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user,
            business_name="Audit V Co",
            campus=self.campus,
        )
        self.client.force_authenticate(self.business_user)
        self.client.get(reverse("safety:verification"))
        self.verification = BusinessVerification.objects.get(business=self.business_profile)

    def test_admin_review_writes_generic_row_referencing_verification(self):
        """The generic trail records the decision and references the
        verification id — VerificationHistory stays the domain record."""
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("safety:verification-admin-review", kwargs={"pk": self.verification.id}),
            {"status": "UNDER_REVIEW"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = AuditLog.objects.get(action="verification.review")
        self.assertEqual(row.target_type, "BUSINESS_VERIFICATION")
        self.assertEqual(row.metadata["verification_id"], str(self.verification.id))
        self.assertEqual(row.metadata["from_status"], "SUBMITTED")
        self.assertEqual(row.metadata["to_status"], "UNDER_REVIEW")
        self.assertEqual(row.actor_role, User.Role.ADMIN)

    def test_report_review_writes_audit_row(self):
        report = Report.objects.create(
            reporter=self.business_user,
            target_type=Report.TargetType.JOB,
            target_id="11111111-1111-5111-8111-111111111111",
            category=Report.Category.OTHER,
            description="Test report",
        )
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("safety:report-admin-review", kwargs={"pk": report.id}),
            {"status": "VALID", "resolution_notes": "Confirmed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        row = AuditLog.objects.get(action="report.review")
        self.assertEqual(row.target_type, "REPORT")
        self.assertEqual(str(row.target_id), str(report.id))
        self.assertEqual(row.metadata["from_status"], "OPEN")
        self.assertEqual(row.metadata["to_status"], "VALID")
        self.assertEqual(row.actor_role, User.Role.ADMIN)
