import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.applications.models import Application
from apps.core.models import TimeStampedModel


class Interview(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", _("Scheduled")
        CONFIRMED = "CONFIRMED", _("Confirmed")
        DECLINED = "DECLINED", _("Declined")
        COMPLETED = "COMPLETED", _("Completed")
        CANCELLED = "CANCELLED", _("Cancelled")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="interviews")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    timezone_name = models.CharField(max_length=64, default="Asia/Kolkata")
    meeting_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    proposed_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="proposed_interviews")

    class Meta:
        db_table = "interviews_interview"
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["application", "starts_at"], name="interview_application_idx")]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "ends_at must be after starts_at."})
        if timezone.is_naive(self.starts_at) or timezone.is_naive(self.ends_at):
            raise ValidationError("Interview times must be timezone-aware.")
        if self.starts_at <= timezone.now() and not self.pk:
            raise ValidationError({"starts_at": "Interview must be scheduled in the future."})
        if self.application_id and self.application.status not in {Application.Status.SHORTLISTED, Application.Status.INTERVIEW}:
            raise ValidationError("An interview requires a shortlisted or interview-stage application.")
        if self.proposed_by_id and self.application_id:
            allowed = {self.application.student.user_id, self.application.job.business.user_id}
            if self.proposed_by_id not in allowed:
                raise ValidationError("Only application participants can schedule an interview.")
