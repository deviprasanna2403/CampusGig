"""
Phase 9B analytics — efficient ORM aggregations for admin, business, and
student dashboards.

Design rules:

- Pure aggregation queries (`Count`/`Avg`/`Q`/`TruncDate`/`TruncMonth`) —
  no per-row Python work, no N+1 (each summary issues a small, fixed
  number of aggregate queries regardless of data volume).
- Every function takes an inclusive `[from_date, to_date]` window
  (already validated by the view) and filters on `created_at` /
  `submitted_at` accordingly.
- Business/student summaries are strictly scoped to the requesting user
  inside the query itself (defense in depth — the permission class is
  not the only gate).

All datetimes are timezone-aware (`USE_TZ=True` in this project); dates
passed in are interpreted as calendar days in the project timezone.
"""

from datetime import datetime
from datetime import time as time_of_day

from django.db.models import Avg, Count, Q
from django.db.models.functions import Trunc
from django.utils import timezone

from apps.accounts.models import User
from apps.applications.models import Application
from apps.jobs.models import Job
from apps.profiles.models import StudentProfile
from apps.safety.models import (
    BusinessVerification,
    Report,
    Review,
)


def _window(from_date, to_date):
    """Convert an inclusive date range into a tz-aware datetime window
    covering [from_date 00:00:00.000000, to_date 23:59:59.999999]."""
    start = timezone.make_aware(datetime.combine(from_date, time_of_day.min))
    end = timezone.make_aware(datetime.combine(to_date, time_of_day.max))
    return start, end


def _timeseries(queryset, timestamp_field, interval, start, end):
    """Group rows in the window by day/week/month and count them."""
    trunc_kind = {"day": "day", "week": "week", "month": "month"}[interval]
    bucket = Trunc(timestamp_field, trunc_kind)
    rows = (
        queryset.filter(**{f"{timestamp_field}__range": (start, end)})
        .annotate(bucket=bucket)
        .values("bucket")
        .annotate(count=Count("id"))
        .order_by("bucket")
    )
    return [
        {"date": row["bucket"].date().isoformat(), "count": row["count"]}
        for row in rows
    ]


def admin_summary(from_date, to_date, interval="day"):
    """Platform-wide counts for admins."""
    window = _window(from_date, to_date)
    start, end = window

    users_by_role = dict(
        User.objects.values_list("role").annotate(c=Count("id"))
    )
    verified_users = User.objects.filter(is_verified=True).count()

    jobs_by_status = dict(
        Job.objects.values_list("status").annotate(c=Count("id"))
    )
    applications_by_status = dict(
        Application.objects.values_list("status").annotate(c=Count("id"))
    )
    verifications_by_status = dict(
        BusinessVerification.objects.values_list("status").annotate(c=Count("id"))
    )
    reports_by_status = dict(Report.objects.values_list("status").annotate(c=Count("id")))

    # Windowed totals (new rows created inside [from, to]).
    new_users = User.objects.filter(created_at__range=window).count()
    new_jobs = Job.objects.filter(created_at__range=window).count()
    new_applications = Application.objects.filter(
        submitted_at__range=window
    ).count()

    total_applications = sum(applications_by_status.values())
    selected = applications_by_status.get(Application.Status.SELECTED, 0)

    return {
        "window": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "interval": interval,
        "users": {
            "total": sum(users_by_role.values()),
            "by_role": users_by_role,
            "verified": verified_users,
            "new_in_window": new_users,
        },
        "jobs": {
            "total": sum(jobs_by_status.values()),
            "by_status": jobs_by_status,
            "new_in_window": new_jobs,
        },
        "applications": {
            "total": total_applications,
            "by_status": applications_by_status,
            "new_in_window": new_applications,
            # Share of ALL applications that ended in selection.
            "selection_rate": round(selected / total_applications, 4) if total_applications else None,
        },
        "verifications": {"by_status": verifications_by_status},
        "reports": {"by_status": reports_by_status},
        "timeseries": {
            "new_users": _timeseries(
                User.objects.all(),
                "created_at",
                interval,
                start,
                end,
            ),
            "new_jobs": _timeseries(Job.objects.all(), "created_at", interval, start, end),
            "new_applications": _timeseries(
                Application.objects.all(), "submitted_at", interval, start, end
            ),
        },
    }


def business_summary(user, from_date, to_date, interval="day"):
    """Summary for one business — only its own jobs/applications."""
    start, end = _window(from_date, to_date)
    own_jobs = Job.objects.filter(business__user=user)
    own_apps = Application.objects.filter(job__business__user=user)

    jobs_by_status = dict(own_jobs.values_list("status").annotate(c=Count("id")))
    apps_by_status = dict(own_apps.values_list("status").annotate(c=Count("id")))

    total_received = sum(apps_by_status.values())
    selected = apps_by_status.get(Application.Status.SELECTED, 0)

    rating = (
        Review.objects.filter(
            reviewee=user, status=Review.Status.PUBLISHED
        ).aggregate(value=Avg("rating"))["value"]
    )

    return {
        "window": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "interval": interval,
        "jobs": {
            "total": sum(jobs_by_status.values()),
            "by_status": jobs_by_status,
            "cancelled": jobs_by_status.get(Job.Status.CANCELLED, 0),
        },
        "applications": {
            "received": total_received,
            "by_status": apps_by_status,
            # Share of ALL received applications that ended in selection.
            "selection_rate": round(selected / total_received, 4) if total_received else None,
        },
        "rating_average": round(rating, 2) if rating is not None else None,
        "timeseries": {
            "applications_received": _timeseries(own_apps, "submitted_at", interval, start, end),
        },
    }


def student_summary(user, from_date, to_date, interval="day"):
    """Summary for one student — only their own applications/profile."""
    start, end = _window(from_date, to_date)
    student, _ = StudentProfile.objects.get_or_create(user=user)
    own_apps = Application.objects.filter(student=student)

    apps_by_status = dict(own_apps.values_list("status").annotate(c=Count("id")))
    total_applications = sum(apps_by_status.values())
    selected = apps_by_status.get(Application.Status.SELECTED, 0)

    rating = (
        Review.objects.filter(
            reviewee=user, status=Review.Status.PUBLISHED
        ).aggregate(value=Avg("rating"))["value"]
    )

    # Open jobs near the student's campus, using the same campus-based
    # discovery pattern as Phase 4/5 (no personal GPS data involved).
    open_nearby = 0
    if student.campus_id:
        from django.contrib.gis.db.models.functions import Distance
        from django.contrib.gis.measure import D

        from django.conf import settings as dj_settings

        open_nearby = Job.objects.filter(
            status__in=[Job.Status.PUBLISHED, Job.Status.OPEN],
            is_active=True,
            location__distance_lte=(
                student.campus.location,
                D(km=dj_settings.DEFAULT_DISCOVERY_RADIUS_KM),
            ),
        ).count()

    return {
        "window": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "interval": interval,
        "profile_completion_percentage": student.completion_percentage,
        "applications": {
            "total": total_applications,
            "by_status": apps_by_status,
            # Share of ALL the student's applications that ended in selection.
            "success_rate": round(selected / total_applications, 4) if total_applications else None,
            "withdrawn": apps_by_status.get(Application.Status.WITHDRAWN, 0),
        },
        "completed_gigs": apps_by_status.get(Application.Status.SELECTED, 0),
        "rating_average": round(rating, 2) if rating is not None else None,
        "open_jobs_near_campus": open_nearby,
        "timeseries": {
            "applications_submitted": _timeseries(own_apps, "submitted_at", interval, start, end),
        },
    }
