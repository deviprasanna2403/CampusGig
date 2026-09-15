"""
Phase 4 domain models: profile completion, campus selection, and the
skill/availability data that campus-based discovery (and later, Jobs
matching) is built on.

Design decisions (Phase 1/4 architecture):

- No student ever has their own GPS coordinates anywhere in this schema.
  `StudentProfile` only has a ForeignKey to `Campus`. Discovery is done by
  finding *campuses* within a radius of a reference point and then finding
  students registered at those campuses (see apps/profiles/views.py,
  `StudentDiscoveryView`). This is what "do not expose a student's exact
  personal GPS location to businesses" means structurally, not just at the
  serializer layer: the field simply does not exist.
- `Campus.location` is a PostGIS **geography** Point (SRID 4326 / WGS84).
  Using `geography=True` (rather than a plain geometry Point) means
  distance lookups (`distance_lte`, `Distance()`) return real-world
  great-circle distances in metres directly — no manual SRID
  transformation to a projected CRS is required to get correct kilometre
  distances for a 20 km radius query.
- Every model uses a UUID primary key, matching `accounts.User`, so IDs
  are not sequentially enumerable via the API.
- `StudentProfile`/`BusinessProfile` are created lazily (get_or_create) by
  the "me" views rather than via a signal on `User`, specifically so that
  `apps.accounts` does not need to be touched for Phase 4.
"""

import uuid

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Campus(TimeStampedModel):
    """
    A physical college/university campus. The unit of geographic discovery
    in CampusGig — see module docstring.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("campus name"), max_length=255, unique=True)
    city = models.CharField(_("city"), max_length=100)
    state = models.CharField(_("state"), max_length=100, blank=True)
    country = models.CharField(_("country"), max_length=100, default="India")
    location = gis_models.PointField(
        _("location"),
        geography=True,
        srid=4326,
        help_text=_(
            "Campus coordinates (WGS84). Drives the 20 km campus-based "
            "discovery radius (settings.DEFAULT_DISCOVERY_RADIUS_KM)."
        ),
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "profiles_campus"
        verbose_name = _("campus")
        verbose_name_plural = _("campuses")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}, {self.city}"

    @property
    def latitude(self):
        """Decimal-degree latitude, derived from `location`. Read-only."""
        return self.location.y if self.location else None

    @property
    def longitude(self):
        """Decimal-degree longitude, derived from `location`. Read-only."""
        return self.location.x if self.location else None


class Skill(TimeStampedModel):
    """
    A single skill/tag a student can attach to their profile
    (`StudentSkill`). Reference data — created by admins, read by everyone.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("skill name"), max_length=100, unique=True)
    category = models.CharField(_("category"), max_length=100, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "profiles_skill"
        verbose_name = _("skill")
        verbose_name_plural = _("skills")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category"], name="skill_category_idx"),
        ]

    def __str__(self):
        return self.name


class StudentProfile(TimeStampedModel):
    """
    Extends a `student`-role User with the fields needed for discovery and
    matching. One-to-one with User; created lazily by
    `StudentProfileMeView.get_object()` on first access, not via a signal.
    """

    class YearOfStudy(models.IntegerChoices):
        FIRST = 1, _("1st Year")
        SECOND = 2, _("2nd Year")
        THIRD = 3, _("3rd Year")
        FOURTH = 4, _("4th Year")
        FIFTH = 5, _("5th Year")
        POSTGRADUATE = 6, _("Postgraduate")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    full_name = models.CharField(_("full name"), max_length=150, blank=True)
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        related_name="student_profiles",
        null=True,
        blank=True,
        help_text=_(
            "The student's registered campus. This — not any personal "
            "GPS coordinate — is what campus-based discovery filters on."
        ),
    )
    year_of_study = models.PositiveSmallIntegerField(
        _("year of study"), choices=YearOfStudy.choices, null=True, blank=True
    )
    bio = models.TextField(_("bio"), blank=True, max_length=1000)
    resume_headline = models.CharField(_("headline"), max_length=150, blank=True)
    skills = models.ManyToManyField(
        Skill,
        through="StudentSkill",
        related_name="student_profiles",
        blank=True,
    )

    # Number of independently-checkable fields used by `completion_percentage`.
    # Kept in sync with that property by hand (see its docstring) rather than
    # introducing a stored, potentially-stale "is_complete" column.
    _COMPLETION_CHECKS = 4

    class Meta:
        db_table = "profiles_student_profile"
        verbose_name = _("student profile")
        verbose_name_plural = _("student profiles")
        indexes = [
            models.Index(fields=["campus"], name="student_profile_campus_idx"),
        ]

    def __str__(self):
        return f"StudentProfile<{self.user.email}>"

    def clean(self):
        if self.user_id and self.user.role != self.user.Role.STUDENT:
            raise ValidationError(
                "A student profile can only be linked to a student account."
            )

    @property
    def completion_percentage(self):
        """
        Computed on the fly from four checks: full name set, campus
        selected, at least one skill added, at least one availability slot
        added. Not persisted, so it can never drift from the actual data.
        """
        completed = 0
        if self.full_name.strip():
            completed += 1
        if self.campus_id:
            completed += 1
        if self.pk and self.student_skills.exists():
            completed += 1
        if self.pk and self.availabilities.exists():
            completed += 1
        return int((completed / self._COMPLETION_CHECKS) * 100)

    @property
    def is_complete(self):
        return self.completion_percentage == 100


class BusinessProfile(TimeStampedModel):
    """
    Extends a `business`-role User. `campus` here is the campus the
    business primarily hires from/operates near — used as the default
    reference point for `StudentDiscoveryView` when a business doesn't
    pass an explicit `campus_id` query param.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_profile",
    )
    business_name = models.CharField(_("business name"), max_length=200, blank=True)
    description = models.TextField(_("description"), blank=True, max_length=2000)
    website = models.URLField(_("website"), blank=True)
    industry = models.CharField(_("industry"), max_length=100, blank=True)
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        related_name="business_profiles",
        null=True,
        blank=True,
        help_text=_(
            "Default reference campus for this business's student "
            "discovery searches."
        ),
    )

    _COMPLETION_CHECKS = 3

    class Meta:
        db_table = "profiles_business_profile"
        verbose_name = _("business profile")
        verbose_name_plural = _("business profiles")
        indexes = [
            models.Index(fields=["campus"], name="business_profile_campus_idx"),
        ]

    def __str__(self):
        return f"BusinessProfile<{self.user.email}>"

    def clean(self):
        if self.user_id and self.user.role != self.user.Role.BUSINESS:
            raise ValidationError(
                "A business profile can only be linked to a business account."
            )

    @property
    def completion_percentage(self):
        completed = 0
        if self.business_name.strip():
            completed += 1
        if self.campus_id:
            completed += 1
        if self.description.strip():
            completed += 1
        return int((completed / self._COMPLETION_CHECKS) * 100)

    @property
    def is_complete(self):
        return self.completion_percentage == 100


class StudentSkill(TimeStampedModel):
    """Through model for StudentProfile <-> Skill, carrying proficiency."""

    class Proficiency(models.TextChoices):
        BEGINNER = "beginner", _("Beginner")
        INTERMEDIATE = "intermediate", _("Intermediate")
        ADVANCED = "advanced", _("Advanced")
        EXPERT = "expert", _("Expert")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="student_skills"
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="student_skills"
    )
    proficiency = models.CharField(
        _("proficiency"),
        max_length=20,
        choices=Proficiency.choices,
        default=Proficiency.BEGINNER,
    )
    years_of_experience = models.PositiveSmallIntegerField(
        _("years of experience"), null=True, blank=True
    )

    class Meta:
        db_table = "profiles_student_skill"
        verbose_name = _("student skill")
        verbose_name_plural = _("student skills")
        ordering = ["-proficiency", "skill__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "skill"], name="uniq_student_skill"
            ),
        ]
        indexes = [
            models.Index(fields=["skill"], name="student_skill_skill_idx"),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.skill_id} ({self.proficiency})"


class Availability(TimeStampedModel):
    """A single recurring weekly time slot a student is available for gigs."""

    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, _("Monday")
        TUESDAY = 1, _("Tuesday")
        WEDNESDAY = 2, _("Wednesday")
        THURSDAY = 3, _("Thursday")
        FRIDAY = 4, _("Friday")
        SATURDAY = 5, _("Saturday")
        SUNDAY = 6, _("Sunday")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="availabilities"
    )
    day_of_week = models.PositiveSmallIntegerField(
        _("day of week"), choices=DayOfWeek.choices
    )
    start_time = models.TimeField(_("start time"))
    end_time = models.TimeField(_("end time"))
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "profiles_availability"
        verbose_name = _("availability slot")
        verbose_name_plural = _("availability slots")
        ordering = ["day_of_week", "start_time"]
        indexes = [
            models.Index(
                fields=["student", "day_of_week"], name="availability_student_day_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="availability_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.student_id} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be after start_time."})

        if self.student_id is not None and self.day_of_week is not None:
            overlapping = Availability.objects.filter(
                student_id=self.student_id, day_of_week=self.day_of_week
            ).exclude(pk=self.pk)
            for slot in overlapping:
                if self.start_time < slot.end_time and slot.start_time < self.end_time:
                    raise ValidationError(
                        "This availability slot overlaps with an existing slot "
                        "for the same day."
                    )
