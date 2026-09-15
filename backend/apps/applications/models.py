import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.jobs.models import Job
from apps.profiles.models import StudentProfile


class Application(TimeStampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", _("Submitted")
        SHORTLISTED = "SHORTLISTED", _("Shortlisted")
        INTERVIEW = "INTERVIEW", _("Interview")
        SELECTED = "SELECTED", _("Selected")
        REJECTED = "REJECTED", _("Rejected")
        WITHDRAWN = "WITHDRAWN", _("Withdrawn")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="applications")
    cover_note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "applications_application"
        constraints = [
            models.UniqueConstraint(fields=["job", "student"], name="uniq_application_job_student"),
        ]
        indexes = [
            models.Index(fields=["job", "status"], name="application_job_status_idx"),
            models.Index(fields=["student", "status"], name="application_student_status_idx"),
        ]

    def clean(self):
        if self.job_id and self.job.status not in {Job.Status.PUBLISHED, Job.Status.OPEN} and not self.pk:
            raise ValidationError("Applications can only be submitted for open jobs.")
        if self.status == self.Status.WITHDRAWN and self.pk:
            previous = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous in {self.Status.SELECTED, self.Status.REJECTED, self.Status.WITHDRAWN}:
                raise ValidationError("This application can no longer be withdrawn or changed.")
