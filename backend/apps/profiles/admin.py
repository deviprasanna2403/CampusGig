from django.contrib import admin

from apps.profiles.models import (
    Availability,
    BusinessProfile,
    Campus,
    Skill,
    StudentProfile,
    StudentSkill,
)


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "state", "country", "is_active", "created_at"]
    list_filter = ["is_active", "state", "country"]
    search_fields = ["name", "city"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "is_active"]
    list_filter = ["is_active", "category"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]


class StudentSkillInline(admin.TabularInline):
    model = StudentSkill
    extra = 0
    autocomplete_fields = ["skill"]


class AvailabilityInline(admin.TabularInline):
    model = Availability
    extra = 0


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "user", "campus", "year_of_study", "is_complete"]
    list_filter = ["campus", "year_of_study"]
    search_fields = ["full_name", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [StudentSkillInline, AvailabilityInline]

    @admin.display(boolean=True)
    def is_complete(self, obj):
        return obj.is_complete


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ["business_name", "user", "campus", "is_complete"]
    list_filter = ["campus"]
    search_fields = ["business_name", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]

    @admin.display(boolean=True)
    def is_complete(self, obj):
        return obj.is_complete
