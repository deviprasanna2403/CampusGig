"""
Shared abstract base models.

These produce NO database tables of their own (abstract=True) — they only
add fields/behaviour to whatever concrete model inherits them. `User`
(apps/accounts/models.py) is the first consumer of `TimeStampedModel`.
`SoftDeleteModel` is not used yet in Phase 2; it will be adopted starting
with `Job`/`Application` in Phase 5/6, where an audit trail of "deleted"
records matters.
"""

from django.db import models
from django.utils import timezone


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
