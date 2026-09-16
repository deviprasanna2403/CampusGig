"""
Phase 9B audit service — the ONLY code path that writes `AuditLog` rows.

Views/services call `AuditService.log(...)` inside their existing
`transaction.atomic()` block where one exists (the insert then commits
atomically with the action it records). There is deliberately no update
or delete method here at all: audit rows are append-only.

`target` is a model instance. Its type is mapped to `AuditLog.TargetType`
by class name, which keeps `apps.core` import-decoupled from the domain
apps (jobs/safety import core, never the reverse).
"""

from apps.core.models import AuditLog

_TARGET_TYPES = {
    "User": AuditLog.TargetType.USER,
    "Job": AuditLog.TargetType.JOB,
    "Application": AuditLog.TargetType.APPLICATION,
    "BusinessVerification": AuditLog.TargetType.BUSINESS_VERIFICATION,
    "Report": AuditLog.TargetType.REPORT,
}


class AuditService:
    """Append-only writer for the generic platform audit trail."""

    @staticmethod
    def log(*, action, actor=None, target=None, metadata=None, request=None):
        """
        Write one immutable audit row and return it.

        - `action`: dotted taxonomy string, e.g. "job.publish".
        - `actor`: the performing User, or None for system actions.
        - `target`: the affected model instance (Job, Application, ...).
        - `metadata`: dict of extra context (from/to statuses, ids, ...).
          When `request` is given, the client IP and user-agent are added
          (truncated) unless already present.
        """
        target_type = None
        target_id = None
        if target is not None:
            target_type = _TARGET_TYPES.get(type(target).__name__) or type(
                target
            )._meta.model_name.upper()
            target_id = target.pk

        data = dict(metadata or {})
        if request is not None:
            data.setdefault("ip", request.META.get("REMOTE_ADDR"))
            data.setdefault(
                "user_agent", (request.META.get("HTTP_USER_AGENT") or "")[:300]
            )

        return AuditLog.objects.create(
            actor=actor,
            actor_role=(getattr(actor, "role", "") or ""),
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=data,
        )
