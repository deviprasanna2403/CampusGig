"""
Shared abstract base models.

These produce NO database tables of their own (abstract=True) — they only
add fields/behaviour to whatever concrete model inherits them. `User`
(apps/accounts/models.py) is the first consumer of `TimeStampedModel`.
`SoftDeleteModel` is not used yet in Phase 2; it will be adopted starting
with `Job`/`Application` in Phase 5/6, where an audit trail of "deleted"
records matters.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Adds self-maintaining created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """
    Default manager for soft-deletable models. `Model.objects` excludes
    soft-deleted rows by default; `Model.objects.all_with_deleted()` opts
    back in (used by admin/audit views).
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Abstract base for models that should never be hard-deleted by normal
    application code (e.g. Job, Application) — `delete()` flips a flag
    instead of removing the row, preserving history/audit trails.
    """

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["is_deleted", "deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)


class AuditLog(models.Model):
    """
    Phase 9B: immutable, append-only audit trail for consequential platform
    actions (job lifecycle, application lifecycle, verification decisions,
    report reviews).

    Immutability is enforced in three layers rather than by a DB trigger
    (this codebase uses no triggers):

    1. Rows are written ONLY by `AuditService.log()` (apps.core.audit) —
       there is no update path anywhere in application code.
    2. The API (`/api/v1/audit/logs/`) is read-only (GET list, admin role).
    3. The Django admin registration (apps.core.admin) is fully readonly —
       add/change/delete are all disabled.

    Deliberately NOT a `TimeStampedModel`: there is no `updated_at` because
    an audit record must never change after it is written.

    Note this is the *generic* platform trail and stays separate from
    `safety.VerificationHistory`, which remains the verification-specific
    record. Verification decisions appear here too, referencing the
    verification id in `metadata` — nothing is duplicated.
    """

    class TargetType(models.TextChoices):
        USER = "USER", _("User")
        JOB = "JOB", _("Job")
        APPLICATION = "APPLICATION", _("Application")
        BUSINESS_VERIFICATION = "BUSINESS_VERIFICATION", _("Business verification")
        REPORT = "REPORT", _("Report")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        null=True,
        blank=True,
        help_text=_(
            "User who performed the action. Null for system actions. "
            "SET_NULL so user deletion preserves the audit history; "
            "`actor_role` keeps the role readable afterwards."
        ),
    )
    actor_role = models.CharField(
        _("actor role"),
        max_length=20,
        blank=True,
        help_text=_("Snapshot of the actor's role at action time."),
    )
    action = models.CharField(
        _("action"),
        max_length=100,
        help_text=_("Dotted taxonomy, e.g. 'job.publish', 'application.withdraw'."),
    )
    target_type = models.CharField(
        _("target type"), max_length=50, choices=TargetType.choices
    )
    target_id = models.UUIDField(
        _("target id"), null=True, blank=True
    )
    metadata = models.JSONField(
        _("metadata"),
        default=dict,
        blank=True,
        help_text=_(
            "Free-form context: from/to statuses, snapshot titles, "
            "request IP / user-agent, related object ids."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
            models.Index(fields=["target_type", "target_id"], name="audit_target_idx"),
            models.Index(fields=["actor", "created_at"], name="audit_actor_created_idx"),
        ]
        verbose_name = _("audit log")
        verbose_name_plural = _("audit logs")

    def __str__(self):
        actor = self.actor.email if self.actor else "system"
        return f"{self.action} by {actor} at {self.created_at:%Y-%m-%d %H:%M}"
