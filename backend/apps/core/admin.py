from django.contrib import admin

from apps.core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Audit trail admin — strictly read-only (Phase 9B).

    Mirrors the Phase 9A hardening of `VerificationHistory`: an audit log
    must be immutable, so add/change/delete are all disabled and every
    field is readonly in the detail view.
    """

    list_display = ("action", "actor_email", "actor_role", "target_type", "target_id", "created_at")
    list_filter = ("action", "target_type", "actor_role", "created_at")
    search_fields = ("actor__email", "action", "target_id")
    date_hierarchy = "created_at"
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="actor", ordering="actor")
    def actor_email(self, obj):
        return obj.actor.email if obj.actor else "— (system)"
