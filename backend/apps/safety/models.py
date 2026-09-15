import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.applications.models import Application
from apps.core.models import TimeStampedModel
from apps.jobs.models import Job
from apps.profiles.models import BusinessProfile, StudentProfile


class BusinessVerification(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", _("Submitted")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under review")
        VERIFIED = "VERIFIED", _("Verified")
        REJECTED = "REJECTED", _("Rejected")
        REVOKED = "REVOKED", _("Revoked")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(BusinessProfile, on_delete=models.CASCADE, related_name="verification")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    legal_name = models.CharField(max_length=200)
    registration_reference = models.CharField(max_length=200, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="verification_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "safety_business_verification"

    @property
    def is_verified(self):
        return self.status == self.Status.VERIFIED

    def transition_to(self, new_status):
        """Enforce the legal status transitions. Phase 9 rule (approved):
        no fast-track — a submission must pass through UNDER_REVIEW before
        an admin can move it to VERIFIED/REJECTED, and only VERIFIED can
        be REVOKED (admin action). Resubmission from REJECTED happens via
        the business-owned submission endpoint, not via this map."""
        allowed = {
            self.Status.SUBMITTED: {self.Status.UNDER_REVIEW},
            self.Status.UNDER_REVIEW: {self.Status.VERIFIED, self.Status.REJECTED},
            self.Status.VERIFIED: {self.Status.REVOKED},
            self.Status.REJECTED: set(),  # resubmit via BusinessVerificationView
            self.Status.REVOKED: set(),
        }
        if self.status == new_status:
            return self
        if new_status not in allowed.get(self.status, set()):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )
        self.status = new_status
        return self


class VerificationHistory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    verification = models.ForeignKey(BusinessVerification, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="verification_history_changes")
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "safety_verification_history"
        ordering = ["-created_at"]


class Report(TimeStampedModel):
    class Category(models.TextChoices):
        FAKE_JOB = "FAKE_JOB", _("Fake job or scam")
        HARASSMENT = "HARASSMENT", _("Harassment")
        PAYMENT_ISSUE = "PAYMENT_ISSUE", _("Payment issue")
        FAKE_BUSINESS = "FAKE_BUSINESS", _("Fake business")
        INAPPROPRIATE_CONTENT = "INAPPROPRIATE_CONTENT", _("Inappropriate content")
        OTHER = "OTHER", _("Other")

    class Status(models.TextChoices):
        OPEN = "OPEN", _("Open")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under review")
        VALID = "VALID", _("Valid")
        DISMISSED = "DISMISSED", _("Dismissed")
        ACTIONED = "ACTIONED", _("Actioned")

    class TargetType(models.TextChoices):
        JOB = "JOB", _("Job")
        BUSINESS = "BUSINESS", _("Business")
        USER = "USER", _("User")
        APPLICATION = "APPLICATION", _("Application")
        MESSAGE = "MESSAGE", _("Message")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_filed")
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.UUIDField()
    category = models.CharField(max_length=30, choices=Category.choices)
    description = models.TextField(max_length=5000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="reports_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = "safety_report"
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="safety_report_target_idx"),
            models.Index(fields=["status", "created_at"], name="safety_report_status_idx"),
        ]

    def clean(self):
        if not self.description.strip():
            raise ValidationError({"description": "Description cannot be blank."})
        if self.target_type == self.TargetType.JOB and not Job.objects.filter(pk=self.target_id).exists():
            raise ValidationError({"target_id": "Target job does not exist."})
        if self.target_type == self.TargetType.BUSINESS and not BusinessProfile.objects.filter(pk=self.target_id).exists():
            raise ValidationError({"target_id": "Target business does not exist."})
        if self.target_type == self.TargetType.USER and not User.objects.filter(pk=self.target_id).exists():
            raise ValidationError({"target_id": "Target user does not exist."})
        if self.target_type == self.TargetType.APPLICATION and not Application.objects.filter(pk=self.target_id).exists():
            raise ValidationError({"target_id": "Target application does not exist."})


class Review(TimeStampedModel):
    class Status(models.TextChoices):
        PUBLISHED = "PUBLISHED", _("Published")
        HIDDEN = "HIDDEN", _("Hidden")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under review")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_written")
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_received")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, max_length=3000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)

    class Meta:
        db_table = "safety_review"
        constraints = [
            models.UniqueConstraint(fields=["application", "reviewer"], name="uniq_review_application_reviewer"),
            models.CheckConstraint(check=models.Q(rating__gte=1) & models.Q(rating__lte=5), name="review_rating_1_to_5"),
        ]
        indexes = [models.Index(fields=["reviewee", "status"], name="safety_review_reviewee_idx")]

    def clean(self):
        if self.reviewer_id == self.reviewee_id:
            raise ValidationError("A user cannot review themselves.")
        if self.application.status != Application.Status.SELECTED or self.application.job.status not in {Job.Status.CLOSED, Job.Status.EXPIRED}:
            raise ValidationError("Reviews require a selected application on a completed job.")
        allowed = {self.application.student.user_id, self.application.job.business.user_id}
        if self.reviewer_id not in allowed or self.reviewee_id not in allowed:
            raise ValidationError("Review participants must belong to the completed application.")
        if not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})


class RiskAssessment(TimeStampedModel):
    class Status(models.TextChoices):
        CLEAR = "CLEAR", _("Clear")
        REVIEW = "REVIEW", _("Review")
        BLOCKED = "BLOCKED", _("Blocked")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=20, choices=Report.TargetType.choices)
    target_id = models.UUIDField()
    score = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CLEAR)
    signals = models.JSONField(default=list)
    strategy = models.CharField(max_length=80, default="rule_based_safety_v1")
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="risk_reviews")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "safety_risk_assessment"
        constraints = [models.UniqueConstraint(fields=["target_type", "target_id"], name="uniq_risk_target")]
        indexes = [models.Index(fields=["status", "score"], name="safety_risk_status_idx")]

    def clean(self):
        if not 0 <= self.score <= 100:
            raise ValidationError({"score": "Risk score must be between 0 and 100."})


class TrustScoreSnapshot(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trust_scores")
    score = models.DecimalField(max_digits=5, decimal_places=2)
    explanation = models.JSONField(default=dict)
    strategy = models.CharField(max_length=80, default="rule_based_trust_v1")

    class Meta:
        db_table = "safety_trust_score_snapshot"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["subject", "created_at"], name="safety_trust_subject_idx")]
