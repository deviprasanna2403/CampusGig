from django.contrib import admin

from apps.safety.models import (
    BusinessVerification,
    Report,
    Review,
    RiskAssessment,
    TrustScoreSnapshot,
    VerificationHistory,
)


@admin.register(BusinessVerification)
class BusinessVerificationAdmin(admin.ModelAdmin):
    """Review-queue admin for verification submissions.

    The status field is READONLY here on purpose: admin-side status
    changes must go through VerificationService (via the API endpoints)
    so that a VerificationHistory row is written, the business user's
    is_verified flag syncs, and a notification fires. Editing status
    directly in the admin would bypass all three — the audit gap found in
    the pre-Phase-9 admin.
    """

    list_display = ("business", "status", "reviewed_by", "reviewed_at", "updated_at")
    list_filter = ("status",)
    search_fields = (
        "business__business_name",
        "business__user__email",
        "legal_name",
        "registration_reference",
    )
    date_hierarchy = "reviewed_at"
    ordering = ("-updated_at",)
    readonly_fields = ("status", "reviewed_by", "reviewed_at", "business")


@admin.register(VerificationHistory)
class VerificationHistoryAdmin(admin.ModelAdmin):
    """Audit trail for verification status changes. IMMUTABLE: no add,
    change, or delete via the admin — history rows are written only by
    VerificationService."""

    list_display = ("verification", "from_status", "to_status", "changed_by", "created_at")
    list_filter = ("to_status",)
    search_fields = (
        "verification__business__business_name",
        "verification__business__user__email",
        "notes",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("target_type", "target_id", "category", "status", "reporter", "created_at")
    list_filter = ("target_type", "category", "status")
    search_fields = ("description", "reporter__email")
    readonly_fields = ("reporter", "target_type", "target_id")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("reviewee", "reviewer", "rating", "status", "created_at")
    list_filter = ("status", "rating")
    search_fields = ("comment", "reviewer__email", "reviewee__email")


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ("target_type", "target_id", "score", "status", "strategy", "created_at")
    list_filter = ("status",)
    search_fields = ("target_id",)


@admin.register(TrustScoreSnapshot)
class TrustScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ("subject", "score", "strategy", "created_at")
    list_filter = ("strategy",)
    search_fields = ("subject__email",)
    # Snapshots are point-in-time records; keep them immutable in admin.
    readonly_fields = ("subject", "score", "explanation", "strategy")
