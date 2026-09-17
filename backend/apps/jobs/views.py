from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole, IsBusiness, IsStudent, IsVerified
from apps.core.audit import AuditService
from apps.jobs.models import Job, JobCategory
from apps.jobs.permissions import IsBusinessOwnerOrAdmin
from apps.jobs.serializers import JobCategorySerializer, JobSerializer
from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.profiles.models import BusinessProfile, Campus


class CategoryInUse(APIException):
    """Raised when deleting a JobCategory that jobs still reference."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This category is referenced by one or more jobs and cannot be deleted."
    default_code = "category_in_use"


class JobCategoryViewSet(viewsets.ModelViewSet):
    queryset = JobCategory.objects.filter(is_active=True)
    serializer_class = JobCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), permissions.IsAdminUser()]

    def perform_destroy(self, instance):
        # A category referenced by any job is protected at the DB level
        # (Job.category is on_delete=PROTECT). Surface that as a clean 409
        # instead of letting ProtectedError escape as a 500.
        try:
            instance.delete()
        except ProtectedError:
            raise CategoryInUse()


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.select_related("business__user", "category").prefetch_related("required_skills").all()
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusinessOwnerOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "business":
            qs = qs.filter(business__user=user)
        elif user.role == "student":
            qs = qs.filter(status__in=[Job.Status.PUBLISHED, Job.Status.OPEN])
        if self.request.query_params.get("category"):
            qs = qs.filter(category__name__iexact=self.request.query_params.get("category"))
        if self.request.query_params.get("job_type"):
            qs = qs.filter(job_type=self.request.query_params.get("job_type"))
        if self.request.query_params.get("payment_type"):
            qs = qs.filter(payment_type=self.request.query_params.get("payment_type"))
        if self.request.query_params.get("min_payment"):
            qs = qs.filter(payment_amount__gte=self.request.query_params.get("min_payment"))
        if self.request.query_params.get("max_payment"):
            qs = qs.filter(payment_amount__lte=self.request.query_params.get("max_payment"))
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params.get("status"))
        if self.request.query_params.get("date"):
            qs = qs.filter(start_date__lte=self.request.query_params.get("date"), end_date__gte=self.request.query_params.get("date"))
        if self.request.query_params.get("skill"):
            qs = qs.filter(required_skills__name__iexact=self.request.query_params.get("skill")).distinct()

        sort = self.request.query_params.get("sort")
        if sort == "distance":
            origin = self._get_student_origin()
            qs = qs.annotate(distance=Distance("location", origin.location)).order_by("distance")
        elif sort == "payment":
            qs = qs.order_by("-payment_amount")
        elif sort == "newest":
            qs = qs.order_by("-created_at")
        elif sort == "deadline":
            qs = qs.order_by("application_deadline")
        else:
            qs = qs.order_by("-created_at")
        return qs

    def get_object(self):
        # F6: students keep read access to jobs they have history with
        # (application or engagement) even after the job leaves discovery —
        # e.g. a takedown — so the detail page can explain why it vanished.
        queryset = self.get_queryset()
        pk = self.kwargs["pk"]
        if self.request.user.role == "student":
            queryset = queryset | Job.objects.filter(
                pk=pk,
                applications__student__user=self.request.user,
            ) | Job.objects.filter(
                pk=pk,
                student_engagements__student__user=self.request.user,
            )
        try:
            obj = get_object_or_404(queryset.distinct(), pk=pk)
        except (ValueError, TypeError, ValidationError):
            raise Http404
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        """Wrap the standard list() so that `?sort=distance` without any
        resolvable campus (no campus_id param, no campus on the caller's
        profile) surfaces as a clean 400 instead of a 500 — the queryset
        build raises ValueError in that case (see _get_student_origin)."""
        try:
            return super().list(request, *args, **kwargs)
        except ValueError:
            return Response(
                {
                    "success": False,
                    "data": None,
                    "error": {
                        "code": 400,
                        "message": "A campus_id is required or a campus must be set on your profile to sort by distance.",
                        "details": None,
                    },
                },
                status=400,
            )

    def _get_student_origin(self):
        campus_id = self.request.query_params.get("campus_id")
        if campus_id:
            campus = get_object_or_404(Campus, pk=campus_id, is_active=True)
            return campus
        profile = getattr(self.request.user, "student_profile", None)
        if profile and profile.campus_id:
            return profile.campus
        business_profile = getattr(self.request.user, "business_profile", None)
        if business_profile and business_profile.campus_id:
            return business_profile.campus
        raise ValueError("A campus_id is required or a campus must be set on the student/business profile.")

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "publish", "close", "cancel", "reopen"}:
            perms = [permissions.IsAuthenticated(), IsBusiness()]
            if self.action == "publish":
                # Phase 5 rule: only verified businesses can publish jobs
                # (the IsVerified permission added for this in Phase 3).
                perms.append(IsVerified())
            return perms
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({"success": False, "data": None, "error": {"code": 401, "message": "Authentication required.", "details": None}}, status=401)
        if request.user.role != "student":
            return Response({"success": False, "data": None, "error": {"code": 403, "message": "Only students may access nearby jobs.", "details": None}}, status=403)

        # radius_km must be a positive number — reject anything else with a
        # clean 400 instead of an unhandled ValueError (500).
        radius_param = request.query_params.get("radius_km")
        if radius_param is not None:
            try:
                radius_km = float(radius_param)
            except (TypeError, ValueError):
                return Response({"success": False, "data": None, "error": {"code": 400, "message": "radius_km must be a number.", "details": None}}, status=400)
            if radius_km <= 0:
                return Response({"success": False, "data": None, "error": {"code": 400, "message": "radius_km must be positive.", "details": None}}, status=400)
        else:
            radius_km = settings.DEFAULT_DISCOVERY_RADIUS_KM

        campus = None
        campus_id = request.query_params.get("campus_id")
        if campus_id:
            campus = get_object_or_404(Campus, pk=campus_id, is_active=True)
        else:
            student_profile = getattr(request.user, "student_profile", None)
            if student_profile and student_profile.campus:
                campus = student_profile.campus

        # Campus-based discovery requires a reference point. Without one we
        # return 400 rather than silently returning every open job.
        if campus is None:
            return Response({"success": False, "data": None, "error": {"code": 400, "message": "A campus_id is required or a campus must be set on your student profile.", "details": None}}, status=400)

        nearby = Job.objects.filter(
            status__in=[Job.Status.PUBLISHED, Job.Status.OPEN],
            is_active=True,
            location__distance_lte=(campus.location, D(km=radius_km)),
        ).select_related("business__user", "category").prefetch_related("required_skills").annotate(distance=Distance("location", campus.location)).order_by("distance")

        page = self.paginate_queryset(nearby)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(nearby, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, *args, **kwargs):
        job = self.get_object()
        if request.user.role != "admin" and job.business.user != request.user:
            return Response({"success": False, "data": None, "error": {"code": 403, "message": "You do not have permission to publish this job.", "details": None}}, status=403)
        if job.status != Job.Status.DRAFT:
            return Response({"success": False, "data": None, "error": {"code": 400, "message": "Only draft jobs can be published.", "details": None}}, status=400)
        if not job.is_publish_ready():
            return Response({"success": False, "data": None, "error": {"code": 400, "message": "This job is incomplete and cannot be published.", "details": None}}, status=400)
        old_status = job.status
        job.status = Job.Status.PUBLISHED
        job.save(update_fields=["status", "updated_at"])
        AuditService.log(
            action="job.publish",
            actor=request.user,
            target=job,
            metadata={"title": job.title, "from_status": old_status, "to_status": job.status},
            request=request,
        )
        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, *args, **kwargs):
        job = self.get_object()
        if request.user.role != "admin" and job.business.user != request.user:
            return Response({"success": False, "data": None, "error": {"code": 403, "message": "You do not have permission to close this job.", "details": None}}, status=403)
        if job.status not in {Job.Status.PUBLISHED, Job.Status.OPEN, Job.Status.FULL}:
            return Response({"success": False, "data": None, "error": {"code": 400, "message": "Only published/open/full jobs can be closed.", "details": None}}, status=400)
        old_status = job.status
        job.status = Job.Status.CLOSED
        job.save(update_fields=["status", "updated_at"])
        AuditService.log(
            action="job.close",
            actor=request.user,
            target=job,
            metadata={"title": job.title, "from_status": old_status, "to_status": job.status},
            request=request,
        )
        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, *args, **kwargs):
        job = self.get_object()
        if request.user.role != "admin" and job.business.user != request.user:
            return Response({"success": False, "data": None, "error": {"code": 403, "message": "You do not have permission to cancel this job.", "details": None}}, status=403)
        if job.status in {Job.Status.CANCELLED, Job.Status.EXPIRED}:
            return Response({"success": False, "data": None, "error": {"code": 400, "message": "This job cannot be cancelled from its current status.", "details": None}}, status=400)
        old_status = job.status
        job.status = Job.Status.CANCELLED
        job.save(update_fields=["status", "updated_at"])
        AuditService.log(
            action="job.cancel",
            actor=request.user,
            target=job,
            metadata={"title": job.title, "from_status": old_status, "to_status": job.status},
            request=request,
        )
        for application in job.applications.select_related("student__user"):
            create_notification(
                recipient=application.student.user,
                event=Notification.Event.JOB_CANCELLED,
                title="Job cancelled",
                body=f"The job {job.title} has been cancelled.",
                payload={"job_id": str(job.id), "application_id": str(application.id)},
            )
        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, *args, **kwargs):
        job = self.get_object()
        if request.user.role != "admin" and job.business.user != request.user:
            return Response({"success": False, "data": None, "error": {"code": 403, "message": "You do not have permission to reopen this job.", "details": None}}, status=403)
        if job.status not in {Job.Status.CLOSED, Job.Status.FULL}:
            return Response({"success": False, "data": None, "error": {"code": 400, "message": "Only closed or full jobs can be reopened.", "details": None}}, status=400)
        old_status = job.status
        job.status = Job.Status.OPEN
        job.save(update_fields=["status", "updated_at"])
        AuditService.log(
            action="job.reopen",
            actor=request.user,
            target=job,
            metadata={"title": job.title, "from_status": old_status, "to_status": job.status},
            request=request,
        )
        serializer = self.get_serializer(job)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()
