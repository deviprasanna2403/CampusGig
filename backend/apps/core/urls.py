from django.urls import path

from apps.core.views import (
    AdminAnalyticsView,
    AuditLogListView,
    BusinessAnalyticsView,
    StudentAnalyticsView,
    health_check,
)

app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("audit/logs/", AuditLogListView.as_view(), name="audit-logs"),
    path("analytics/admin/", AdminAnalyticsView.as_view(), name="analytics-admin"),
    path("analytics/business/me/", BusinessAnalyticsView.as_view(), name="analytics-business-me"),
    path("analytics/student/me/", StudentAnalyticsView.as_view(), name="analytics-student-me"),
]
