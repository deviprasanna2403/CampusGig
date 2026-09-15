import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.jobs.models import Job, JobCategory
from apps.profiles.models import StudentProfile


class JobMatch(TimeStampedModel):
    """Persisted, explainable match result for one student and one job."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="job_matches"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="student_matches")
    score = models.DecimalField(max_digits=5, decimal_places=2)
    skill_score = models.DecimalField(max_digits=5, decimal_places=2)
    location_score = models.DecimalField(max_digits=5, decimal_places=2)
    availability_score = models.DecimalField(max_digits=5, decimal_places=2)
    experience_score = models.DecimalField(max_digits=5, decimal_places=2)
    explanation = models.JSONField(default=dict)
    strategy = models.CharField(max_length=80, default="rule_based_v1")
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matching_job_match"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "job"], name="uniq_matching_student_job"
            ),
        ]
        indexes = [
            models.Index(fields=["student", "score"], name="match_student_score_idx"),
            models.Index(fields=["job", "score"], name="match_job_score_idx"),
        ]
        ordering = ["-score", "-calculated_at"]

    def clean(self):
        for field in (
            "score",
            "skill_score",
            "location_score",
            "availability_score",
            "experience_score",
        ):
            value = getattr(self, field)
            if value is not None and not 0 <= value <= 100:
                raise ValidationError({field: "Scores must be between 0 and 100."})


class StudentJobEngagement(TimeStampedModel):
    """Student-owned signals used by recommendations, not an application workflow."""

    class Kind(models.TextChoices):
        VIEWED = "VIEWED", _("Viewed")
        SAVED = "SAVED", _("Saved")
        APPLIED = "APPLIED", _("Application signal")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="job_engagements"
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="student_engagements")
    kind = models.CharField(max_length=20, choices=Kind.choices)

    class Meta:
        db_table = "matching_student_job_engagement"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "job", "kind"], name="uniq_student_job_engagement"
            ),
        ]
        indexes = [
            models.Index(fields=["student", "kind"], name="engagement_student_kind_idx"),
        ]


class StudentPreference(TimeStampedModel):
    """Optional student controls for recommendation ranking."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        StudentProfile, on_delete=models.CASCADE, related_name="matching_preferences"
    )
    preferred_categories = models.ManyToManyField(
        JobCategory, blank=True, related_name="student_preferences"
    )
    preferred_job_types = models.JSONField(default=list, blank=True)
    preferred_payment_types = models.JSONField(default=list, blank=True)
    minimum_payment = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    maximum_payment = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    maximum_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, default=20, help_text="Capped by the platform 20 km discovery radius."
    )

    class Meta:
        db_table = "matching_student_preference"

    def clean(self):
        if self.minimum_payment is not None and self.maximum_payment is not None:
            if self.maximum_payment < self.minimum_payment:
                raise ValidationError({"maximum_payment": "Must be at least minimum_payment."})
        if self.maximum_distance_km is not None and not 0 < self.maximum_distance_km <= 20:
            raise ValidationError({"maximum_distance_km": "Must be between 0 and 20 km."})
