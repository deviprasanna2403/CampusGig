from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    """
    Phase 4: StudentProfile, BusinessProfile, Campus, Skill, StudentSkill,
    Availability. See apps/profiles/models.py for the full design notes.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profiles"
    label = "profiles"
    verbose_name = "Profiles"
