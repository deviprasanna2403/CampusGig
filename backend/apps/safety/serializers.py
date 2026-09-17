from rest_framework import serializers

from apps.applications.models import Application
from apps.safety.models import BusinessVerification, Report, Review, RiskAssessment, TrustScoreSnapshot


class BusinessVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessVerification
        fields = ["id", "business", "status", "legal_name", "registration_reference", "evidence", "review_notes", "reviewed_by", "reviewed_at", "created_at", "updated_at"]
        read_only_fields = ["id", "business", "status", "reviewed_by", "reviewed_at", "created_at", "updated_at"]

    def validate_evidence(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Evidence must be an object.")
        return value


class VerificationReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[BusinessVerification.Status.UNDER_REVIEW, BusinessVerification.Status.VERIFIED, BusinessVerification.Status.REJECTED])
    review_notes = serializers.CharField(required=False, allow_blank=True)


class VerificationRevokeSerializer(serializers.Serializer):
    """Revoke takes no target status (it is always REVOKED) but requires
    the admin to state why — notes are mandatory, unlike review."""

    review_notes = serializers.CharField(required=True, allow_blank=False)


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "reporter", "target_type", "target_id", "category", "description", "status", "reviewed_by", "reviewed_at", "resolution_notes", "created_at", "updated_at"]
        read_only_fields = ["id", "reporter", "status", "reviewed_by", "reviewed_at", "resolution_notes", "created_at", "updated_at"]

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Please provide at least 10 characters.")
        return value


class ReportReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[Report.Status.UNDER_REVIEW, Report.Status.VALID, Report.Status.DISMISSED, Report.Status.ACTIONED])
    resolution_notes = serializers.CharField(required=False, allow_blank=True)


class ReviewSerializer(serializers.ModelSerializer):
    # F6 UI: display emails alongside the raw ids (reviewer/reviewee remain
    # UUIDs for API stability — Phase 8 clients see no breaking change).
    reviewer_email = serializers.CharField(source="reviewer.email", read_only=True)
    reviewee_email = serializers.CharField(source="reviewee.email", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "application", "reviewer", "reviewee", "reviewer_email", "reviewee_email", "rating", "comment", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "reviewer", "reviewee", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        application = attrs["application"]
        user = self.context["request"].user
        if application.status != Application.Status.SELECTED or application.job.status not in {"CLOSED", "EXPIRED"}:
            raise serializers.ValidationError("Reviews require a completed selected engagement.")
        if user.id == application.student.user_id:
            reviewee_id = application.job.business.user_id
        elif user.id == application.job.business.user_id:
            reviewee_id = application.student.user_id
        else:
            raise serializers.ValidationError("Only engagement participants can review.")
        if Review.objects.filter(application=application, reviewer=user).exists():
            raise serializers.ValidationError("You have already reviewed this engagement.")
        attrs["_reviewee_id"] = reviewee_id
        return attrs

    def create(self, validated_data):
        reviewee_id = validated_data.pop("_reviewee_id")
        validated_data["reviewer"] = self.context["request"].user
        validated_data["reviewee_id"] = reviewee_id
        return super().create(validated_data)


class TrustScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustScoreSnapshot
        fields = ["id", "subject", "score", "explanation", "strategy", "created_at"]
        read_only_fields = fields


class RiskAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskAssessment
        fields = ["id", "target_type", "target_id", "score", "status", "signals", "strategy", "reviewed_by", "reviewed_at", "created_at"]
        read_only_fields = fields
