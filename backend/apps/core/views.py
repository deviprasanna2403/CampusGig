import uuid as uuid_lib
from datetime import date as date_cls
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from apps.accounts.permissions import IsAdminRole, IsBusiness, IsStudent
from apps.core.analytics import _window, admin_summary, business_summary, student_summary
from apps.core.models import AuditLog
from apps.core.serializers import AuditLogSerializer


def health_check(request):
    """
    Unauthenticated liveness endpoint. Confirms settings load correctly
    and the app boots — does not touch the database, so it stays useful
    even if migrations haven't been run yet.
    """
    return JsonResponse(
        {
            "status": "ok",
            "project": "CampusGig",
            "phase": 2,
            "debug": settings.DEBUG,
        }
    )


# ---------------------------------------------------------------------------
# Phase 9B: shared request-parsing helpers
# ---------------------------------------------------------------------------

_INTERVALS = ("day", "week", "month")


def _parse_date(value, name):
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({name: f"{name} must be an ISO date (YYYY-MM-DD)."})


def _date_range(request):
    """Parse optional ?from/?to as an inclusive date window (validated)."""
    start = _parse_date(request.query_params["from"], "from") if request.query_params.get("from") else None
    end = _parse_date(request.query_params["to"], "to") if request.query_params.get("to") else None
    if start and end and start > end:
        raise ValidationError({"from": "'from' must not be after 'to'."})
    return start, end


def _default_window(start, end):
    """Default analytics window: the trailing 30 days ending today."""
    if end is None:
        end = timezone.localdate()
    if start is None:
        start = end - timedelta(days=29)
    return start, end


def _parse_interval(request):
    interval = request.query_params.get("interval", "day")
    if interval not in _INTERVALS:
        raise ValidationError({"interval": "interval must be one of: day, week, month."})
    return interval


def _parse_uuid(value, name):
    try:
        return uuid_lib.UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({name: f"{name} must be a valid UUID."})


# ---------------------------------------------------------------------------
# Phase 9B: admin audit trail (read-only)
# ---------------------------------------------------------------------------


class AuditLogListView(generics.ListAPIView):
    """
    Admin-only, read-only audit trail. There are deliberately no write
    endpoints for AuditLog — rows are appended exclusively by
    `AuditService.log()` (apps.core.audit).
    """

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor").all()
        params = self.request.query_params

        if params.get("action"):
            qs = qs.filter(action=params["action"])
        if params.get("target_type"):
            qs = qs.filter(target_type=params["target_type"].upper())
        if params.get("target_id"):
            qs = qs.filter(target_id=_parse_uuid(params["target_id"], "target_id"))
        if params.get("actor"):
            qs = qs.filter(actor_id=_parse_uuid(params["actor"], "actor"))

        start, end = _date_range(self.request)
        if start:
            # Use the same tz-aware window conversion as analytics so the
            # date-only filter covers the whole first day without naive-
            # datetime warnings (USE_TZ=True).
            aware_start, _ = _window(start, start)
            qs = qs.filter(created_at__gte=aware_start)
        if end:
            # Date-only 'to' should include the whole end day.
            qs = qs.filter(created_at__date__lte=end)
        return qs


# ---------------------------------------------------------------------------
# Phase 9B: analytics dashboards
# ---------------------------------------------------------------------------


class AdminAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        start, end = _default_window(*_date_range(request))
        interval = _parse_interval(request)
        return Response(admin_summary(start, end, interval))


class BusinessAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsBusiness]

    def get(self, request):
        start, end = _default_window(*_date_range(request))
        interval = _parse_interval(request)
        return Response(business_summary(request.user, start, end, interval))


class StudentAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        start, end = _default_window(*_date_range(request))
        interval = _parse_interval(request)
        return Response(student_summary(request.user, start, end, interval))
