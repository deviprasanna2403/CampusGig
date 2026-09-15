import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Event(models.TextChoices):
        APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED", _("Application submitted")
        APPLICATION_SHORTLISTED = "APPLICATION_SHORTLISTED", _("Application shortlisted")
        INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED", _("Interview scheduled")
        INTERVIEW_UPDATED = "INTERVIEW_UPDATED", _("Interview updated")
        SELECTED = "SELECTED", _("Selected")
        REJECTED = "REJECTED", _("Rejected")
        JOB_CANCELLED = "JOB_CANCELLED", _("Job cancelled")
        JOB_DEADLINE_REMINDER = "JOB_DEADLINE_REMINDER", _("Job deadline reminder")
        NEW_APPLICATION = "NEW_APPLICATION", _("New application")
        APPLICATION_WITHDRAWN = "APPLICATION_WITHDRAWN", _("Application withdrawn")
        INTERVIEW_RESPONSE = "INTERVIEW_RESPONSE", _("Interview response")
        VERIFICATION_VERIFIED = "VERIFICATION_VERIFIED", _("Business verification approved")
        VERIFICATION_REJECTED = "VERIFICATION_REJECTED", _("Business verification rejected")
        VERIFICATION_REVOKED = "VERIFICATION_REVOKED", _("Business verification revoked")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    event = models.CharField(max_length=40, choices=Event.choices)
    title = models.CharField(max_length=200)
    body = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at"], name="notif_recipient_read_idx"), models.Index(fields=["event", "created_at"], name="notification_event_idx")]
