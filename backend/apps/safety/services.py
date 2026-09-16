from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import create_notification

from apps.accounts.models import User
from apps.applications.models import Application
from apps.core.audit import AuditService
from apps.jobs.models import Job
from apps.safety.models import (
    BusinessVerification,
    Report,
    Review,
    RiskAssessment,
    TrustScoreSnapshot,
    VerificationHistory,
)


@dataclass(frozen=True)
class ScoreResult:
    score: Decimal
    explanation: dict
    strategy: str


class TrustScoreStrategy:
    key = "rule_based_trust_v1"

    def score_business(self, user: User) -> ScoreResult:
        verification = BusinessVerification.objects.filter(business__user=user).first()
        completed = Application.objects.filter(job__business__user=user, status=Application.Status.SELECTED, job__status__in=[Job.Status.CLOSED, Job.Status.EXPIRED]).count()
        reviews = Review.objects.filter(reviewee=user, status=Review.Status.PUBLISHED)
        average = reviews.aggregate(value=Avg("rating"))["value"] or 0
        valid_reports = Report.objects.filter(target_type=Report.TargetType.BUSINESS, target_id=getattr(user.business_profile, "id", None), status__in=[Report.Status.VALID, Report.Status.ACTIONED]).count()
        cancellations = Job.objects.filter(business__user=user, status=Job.Status.CANCELLED).count()
        verification_points = 35 if verification and verification.status == BusinessVerification.Status.VERIFIED else 0
        completed_points = min(completed * 5, 30)
        rating_points = min(float(average) * 5, 25)
        penalties = min(valid_reports * 8 + cancellations * 3, 40)
        score = max(0, min(100, verification_points + completed_points + rating_points - penalties))
        return ScoreResult(Decimal(str(round(score, 2))), {"verification": verification_points, "completed_jobs": completed, "rating_average": float(average), "rating_points": rating_points, "valid_reports": valid_reports, "cancellations": cancellations, "penalties": penalties}, self.key)

    def score_student(self, user: User) -> ScoreResult:
        completed = Application.objects.filter(student__user=user, status=Application.Status.SELECTED, job__status__in=[Job.Status.CLOSED, Job.Status.EXPIRED]).count()
        reviews = Review.objects.filter(reviewee=user, status=Review.Status.PUBLISHED)
        average = reviews.aggregate(value=Avg("rating"))["value"] or 0
        valid_reports = Report.objects.filter(target_type=Report.TargetType.USER, target_id=user.id, status__in=[Report.Status.VALID, Report.Status.ACTIONED]).count()
        withdrawals = Application.objects.filter(student__user=user, status=Application.Status.WITHDRAWN).count()
        score = max(0, min(100, min(completed * 12, 48) + min(float(average) * 8, 40) - min(valid_reports * 8 + withdrawals * 2, 30)))
        return ScoreResult(Decimal(str(round(score, 2))), {"completed_gigs": completed, "rating_average": float(average), "valid_reports": valid_reports, "withdrawals": withdrawals}, "rule_based_reputation_v1")


class SafetyScoreService:
    def __init__(self, strategy=None):
        self.strategy = strategy or TrustScoreStrategy()

    def calculate(self, user: User) -> TrustScoreSnapshot:
        result = self.strategy.score_business(user) if user.role == User.Role.BUSINESS else self.strategy.score_student(user)
        return TrustScoreSnapshot.objects.create(subject=user, score=result.score, explanation=result.explanation, strategy=result.strategy)


class VerificationService:
    """All review-side status changes go through this service so that the
    three things that must happen together cannot drift apart: (1) the
    VerificationHistory audit row is written, (2) the business's
    User.is_verified flag is synced to the decision, and (3) the business
    is notified. Phase 9 (approved plan): no fast-track — SUBMITTED must
    reach UNDER_REVIEW before VERIFIED/REJECTED; REVOKED only from VERIFIED."""

    def transition(self, verification, *, new_status, changed_by, notes=""):
        old_status = verification.status
        # Raises ValidationError on an illegal transition (no fast-track).
        verification.transition_to(new_status)
        with transaction.atomic():
            verification.review_notes = notes
            verification.reviewed_by = changed_by
            verification.reviewed_at = timezone.now()
            verification.save(update_fields=[
                "status", "review_notes", "reviewed_by", "reviewed_at", "updated_at",
            ])
            VerificationHistory.objects.create(
                verification=verification,
                from_status=old_status,
                to_status=verification.status,
                changed_by=changed_by,
                notes=notes,
            )
            user = verification.business.user
            user.is_verified = verification.status == BusinessVerification.Status.VERIFIED
            user.save(update_fields=["is_verified"])
            # Phase 9B: also record the decision on the *generic* audit
            # trail. VerificationHistory remains the verification-specific
            # record; this row only references it via metadata — nothing
            # is duplicated.
            AuditService.log(
                action="verification.review",
                actor=changed_by,
                target=verification,
                metadata={
                    "verification_id": str(verification.id),
                    "from_status": old_status,
                    "to_status": verification.status,
                },
            )
        self._notify(verification, old_status=old_status)
        return verification

    def _notify(self, verification, *, old_status):
        event_map = {
            BusinessVerification.Status.VERIFIED: Notification.Event.VERIFICATION_VERIFIED,
            BusinessVerification.Status.REJECTED: Notification.Event.VERIFICATION_REJECTED,
            BusinessVerification.Status.REVOKED: Notification.Event.VERIFICATION_REVOKED,
        }
        event = event_map.get(verification.status)
        if not event or old_status == verification.status:
            return
        titles = {
            Notification.Event.VERIFICATION_VERIFIED: "Business verified",
            Notification.Event.VERIFICATION_REJECTED: "Verification rejected",
            Notification.Event.VERIFICATION_REVOKED: "Verification revoked",
        }
        create_notification(
            recipient=verification.business.user,
            event=event,
            title=titles[event],
            body=f"Your business verification status is now {verification.status.lower()}.",
            payload={"verification_id": str(verification.id)},
        )


class RiskService:
    strategy_key = "rule_based_safety_v1"
    external_payment_terms = ("pay outside", "send money", "crypto", "gift card", "whatsapp payment")

    def assess_job(self, job: Job) -> RiskAssessment:
        signals = []
        if not BusinessVerification.objects.filter(business=job.business, status=BusinessVerification.Status.VERIFIED).exists():
            signals.append("unverified_business")
        text = f"{job.title} {job.description} {job.eligibility_notes}".lower()
        if any(term in text for term in self.external_payment_terms):
            signals.append("external_payment_request")
        report_count = Report.objects.filter(target_type=Report.TargetType.JOB, target_id=job.id, status__in=[Report.Status.VALID, Report.Status.ACTIONED]).count()
        if report_count:
            signals.append("valid_reports")
        score = min(100, len(signals) * 30 + report_count * 10)
        status = RiskAssessment.Status.BLOCKED if score >= 70 else RiskAssessment.Status.REVIEW if score else RiskAssessment.Status.CLEAR
        assessment, _ = RiskAssessment.objects.update_or_create(target_type=Report.TargetType.JOB, target_id=job.id, defaults={"score": score, "status": status, "signals": signals, "strategy": self.strategy_key})
        return assessment
