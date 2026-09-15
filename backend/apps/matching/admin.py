from django.contrib import admin

from apps.matching.models import JobMatch, StudentJobEngagement, StudentPreference


@admin.register(JobMatch)
class JobMatchAdmin(admin.ModelAdmin):
    list_display = ("student", "job", "score", "strategy", "calculated_at")
    list_filter = ("strategy",)
    search_fields = ("student__user__email", "job__title")


@admin.register(StudentJobEngagement)
class StudentJobEngagementAdmin(admin.ModelAdmin):
    list_display = ("student", "job", "kind", "created_at")
    list_filter = ("kind",)


@admin.register(StudentPreference)
class StudentPreferenceAdmin(admin.ModelAdmin):
    list_display = ("student", "minimum_payment", "maximum_payment", "maximum_distance_km")
