from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsAdminRole, IsBusiness, IsStudent
from apps.applications.models import Application
from apps.profiles.models import BusinessProfile
from apps.safety.models import BusinessVerification, Report, Review, RiskAssessment, TrustScoreSnapshot
from apps.safety.permissions import IsReportOwnerOrAdmin
from apps.safety.serializers import (
    BusinessVerificationSerializer, ReportReviewSerializer, ReportSerializer,
    ReviewSerializer, RiskAssessmentSerializer, TrustScoreSerializer,
    VerificationRevokeSerializer, VerificationReviewSerializer,
)
from apps.safety.services import RiskService, SafetyScoreService, VerificationService


class BusinessVerificationView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsBusiness]
    serializer_class = BusinessVerificationSerializer

    def get_object(self):
        business, _ = BusinessProfile.objects.get_or_create(user=self.request.user)
        verification, _ = BusinessVerification.objects.get_or_create(business=business, defaults={"legal_name": business.business_name or self.request.user.email})
        return verification

    def perform_update(self, serializer):
        instance = self.get_object()
        # The PATCH *is* the submission act: the row is lazily created as
        # SUBMITTED by the GET, so SUBMITTED stays editable (first-time
        # details) and REJECTED may resubmit. UNDER_REVIEW/VERIFIED are
        # with the admins; REVOKED is terminal (a revoked business must
        # contact support, per the approved Phase 9 design).
        if instance.status in {
            BusinessVerification.Status.UNDER_REVIEW,
            BusinessVerification.Status.VERIFIED,
            BusinessVerification.Status.REVOKED,
        }:
            # DRF's ValidationError (not Django's) so the project exception
            # handler renders the standard 400 envelope.
            raise DRFValidationError(
                "This verification is under review, verified, or revoked and cannot be changed here."
            )
        serializer.save(status=BusinessVerification.Status.SUBMITTED)


class VerificationAdminListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = BusinessVerificationSerializer
    queryset = BusinessVerification.objects.select_related("business__user", "reviewed_by").all()


class VerificationAdminReviewView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = VerificationReviewSerializer
    queryset = BusinessVerification.objects.all()

    def update(self, request, *args, **kwargs):
        # Phase 9: all review transitions flow through the service so that
        # history, User.is_verified sync, and notifications cannot drift.
        # (Previously this wrote rows directly and never synced is_verified
        # — the publish gate stayed shut even for VERIFIED businesses.)
        verification = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            verification = VerificationService().transition(
                verification,
                new_status=serializer.validated_data["status"],
                changed_by=request.user,
                notes=serializer.validated_data.get("review_notes", ""),
            )
        except ValidationError as exc:
            return Response(
                {"success": False, "data": None, "error": {"code": 400, "message": str(exc), "details": None}},
                status=400,
            )
        return Response(BusinessVerificationSerializer(verification).data)


class VerificationAdminRevokeView(generics.UpdateAPIView):
    """Admin-only: revoke a VERIFIED verification (e.g. after a valid
    FAKE_BUSINESS report). Requires notes; sets User.is_verified=False."""

    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = VerificationRevokeSerializer
    queryset = BusinessVerification.objects.all()

    def update(self, request, *args, **kwargs):
        verification = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data["review_notes"]
        try:
            verification = VerificationService().transition(
                verification,
                new_status=BusinessVerification.Status.REVOKED,
                changed_by=request.user,
                notes=notes,
            )
        except ValidationError as exc:
            return Response(
                {"success": False, "data": None, "error": {"code": 400, "message": str(exc), "details": None}},
                status=400,
            )
        return Response(BusinessVerificationSerializer(verification).data)


class ReportListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReportSerializer

    def get_queryset(self):
        if self.request.user.role == User.Role.ADMIN:
            return Report.objects.all().select_related("reporter", "reviewed_by")
        return Report.objects.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class ReportDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsReportOwnerOrAdmin]
    serializer_class = ReportSerializer

    def get_queryset(self):
        return Report.objects.all() if self.request.user.role == User.Role.ADMIN else Report.objects.filter(reporter=self.request.user)


class ReportAdminReviewView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = ReportReviewSerializer
    queryset = Report.objects.all()

    def update(self, request, *args, **kwargs):
        report = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.status = serializer.validated_data["status"]
        report.resolution_notes = serializer.validated_data.get("resolution_notes", "")
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "resolution_notes", "reviewed_by", "reviewed_at", "updated_at"])
        return Response(ReportSerializer(report).data)


class ReviewListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return Review.objects.filter(reviewee_id=self.kwargs["user_id"], status=Review.Status.PUBLISHED)

    def perform_create(self, serializer):
        serializer.save()


class MyTrustScoreView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TrustScoreSerializer

    def retrieve(self, request, *args, **kwargs):
        snapshot = SafetyScoreService().calculate(request.user)
        return Response(self.get_serializer(snapshot).data)


class RiskAssessmentView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = RiskAssessmentSerializer
    queryset = RiskAssessment.objects.all()

    def retrieve(self, request, *args, **kwargs):
        assessment = self.get_object()
        return Response(self.get_serializer(assessment).data)


class JobRiskCalculateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = RiskAssessmentSerializer

    def create(self, request, *args, **kwargs):
        from apps.jobs.models import Job
        job = get_object_or_404(Job, pk=kwargs["job_id"])
        assessment = RiskService().assess_job(job)
        return Response(self.get_serializer(assessment).data, status=status.HTTP_200_OK)
