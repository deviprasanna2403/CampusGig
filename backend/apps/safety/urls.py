from django.urls import path

from apps.safety.views import (
    BusinessVerificationView, JobRiskCalculateView, MyTrustScoreView,
    ReportAdminReviewView, ReportDetailView, ReportListCreateView,
    ReviewListCreateView, RiskAssessmentView, VerificationAdminListView,
    VerificationAdminRevokeView, VerificationAdminReviewView,
)

app_name = "safety"

urlpatterns = [
    path("verification/", BusinessVerificationView.as_view(), name="verification"),
    path("admin/verifications/", VerificationAdminListView.as_view(), name="verification-admin-list"),
    path("admin/verifications/<uuid:pk>/review/", VerificationAdminReviewView.as_view(), name="verification-admin-review"),
    path("admin/verifications/<uuid:pk>/revoke/", VerificationAdminRevokeView.as_view(), name="verification-admin-revoke"),
    path("reports/", ReportListCreateView.as_view(), name="report-list"),
    path("reports/<uuid:pk>/", ReportDetailView.as_view(), name="report-detail"),
    path("admin/reports/<uuid:pk>/review/", ReportAdminReviewView.as_view(), name="report-admin-review"),
    path("reviews/<uuid:user_id>/", ReviewListCreateView.as_view(), name="review-list"),
    path("trust/me/", MyTrustScoreView.as_view(), name="trust-me"),
    path("admin/risk/<uuid:pk>/", RiskAssessmentView.as_view(), name="risk-detail"),
    path("admin/risk/jobs/<uuid:job_id>/calculate/", JobRiskCalculateView.as_view(), name="risk-job-calculate"),
]
