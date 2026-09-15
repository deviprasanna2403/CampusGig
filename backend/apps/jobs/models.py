import uuid

from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel
from apps.profiles.models import BusinessProfile, Skill


class JobCategory(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("category name"), max_length=120, unique=True)
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "jobs_category"
        verbose_name = _("job category")
        verbose_name_plural = _("job categories")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Job(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        PUBLISHED = "PUBLISHED", _("Published")
        OPEN = "OPEN", _("Open")
        FULL = "FULL", _("Full")
        CLOSED = "CLOSED", _("Closed")
        EXPIRED = "EXPIRED", _("Expired")
        CANCELLED = "CANCELLED", _("Cancelled")

    class JobType(models.TextChoices):
        ONE_DAY_GIG = "ONE_DAY_GIG", _("One Day Gig")
        WEEKEND = "WEEKEND", _("Weekend")
        PART_TIME = "PART_TIME", _("Part Time")
        TEMPORARY = "TEMPORARY", _("Temporary")
        SEASONAL = "SEASONAL", _("Seasonal")
        EVENT_BASED = "EVENT_BASED", _("Event Based")
        INTERNSHIP = "INTERNSHIP", _("Internship")

    class PaymentType(models.TextChoices):
        HOURLY = "HOURLY", _("Hourly")
        DAILY = "DAILY", _("Daily")
        WEEKLY = "WEEKLY", _("Weekly")
        MONTHLY = "MONTHLY", _("Monthly")
        FIXED_PROJECT = "FIXED_PROJECT", _("Fixed Project")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.PROTECT,
        related_name="jobs",
        help_text=_("Employer/business account that owns the job."),
    )
    title = models.CharField(_("job title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    category = models.ForeignKey(
        JobCategory,
        on_delete=models.PROTECT,
        related_name="jobs",
        help_text=_("Job category reference data."),
    )
    job_type = models.CharField(
        _("job type"), max_length=30, choices=JobType.choices, default=JobType.ONE_DAY_GIG
    )
    required_skills = models.ManyToManyField(Skill, related_name="jobs", blank=True)
    location = gis_models.PointField(
        _("job location"),
        geography=True,
        srid=4326,
        help_text=_("Exact job location in WGS84 (longitude, latitude)."),
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    start_time = models.TimeField(_("start time"))
    end_time = models.TimeField(_("end time"))
    payment_amount = models.DecimalField(
        _("payment amount"), max_digits=12, decimal_places=2, default=0
    )
    payment_type = models.CharField(
        _("payment type"), max_length=30, choices=PaymentType.choices, default=PaymentType.HOURLY
    )
    workers_required = models.PositiveIntegerField(_("workers required"), default=1)
    application_deadline = models.DateField(_("application deadline"))
    eligibility_notes = models.TextField(_("eligibility requirements"), blank=True)
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        db_table = "jobs_job"
        verbose_name = _("job")
        verbose_name_plural = _("jobs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_date"], name="job_status_start_date_idx"),
            models.Index(fields=["business", "status"], name="job_business_status_idx"),
            models.Index(fields=["category"], name="job_category_idx"),
            models.Index(fields=["payment_type"], name="job_payment_type_idx"),
            models.Index(fields=["application_deadline"], name="job_deadline_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="job_end_date_after_or_equal_start_date",
            ),
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="job_end_time_after_start_time",
            ),
            models.CheckConstraint(
                check=models.Q(workers_required__gt=0),
                name="job_workers_required_positive",
            ),
            models.CheckConstraint(
                check=models.Q(payment_amount__gt=0),
                name="job_payment_amount_positive",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def latitude(self):
        return self.location.y if self.location else None

    @property
    def longitude(self):
        return self.location.x if self.location else None

    @property
    def is_published(self):
        return self.status in {self.Status.PUBLISHED, self.Status.OPEN, self.Status.FULL, self.Status.CLOSED}

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "end_date must be on or after start_date."})
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be after start_time."})
        if self.application_deadline and self.start_date and self.application_deadline > self.start_date:
            raise ValidationError({"application_deadline": "application_deadline must be on or before start_date."})
        if self.payment_amount is not None and self.payment_amount <= 0:
            raise ValidationError({"payment_amount": "payment_amount must be positive."})
        if self.workers_required is not None and self.workers_required <= 0:
            raise ValidationError({"workers_required": "workers_required must be positive."})
        if not self.location:
            raise ValidationError({"location": "A valid job location is required."})

    def is_publish_ready(self):
        required_fields = [
            self.title,
            self.description,
            self.category_id,
            self.job_type,
            self.payment_type,
            self.payment_amount,
            self.location,
            self.start_date,
            self.end_date,
            self.start_time,
            self.end_time,
            self.workers_required,
            self.application_deadline,
            self.eligibility_notes,
        ]
        if not all(field not in (None, "", 0) for field in required_fields):
            return False
        if not self.title.strip() or not self.description.strip() or not self.eligibility_notes.strip():
            return False
        return True

    def transition_to(self, new_status):
        allowed = {
            self.Status.DRAFT: {self.Status.PUBLISHED},
            self.Status.PUBLISHED: {self.Status.OPEN, self.Status.FULL, self.Status.CLOSED, self.Status.CANCELLED},
            self.Status.OPEN: {self.Status.FULL, self.Status.CLOSED, self.Status.CANCELLED},
            self.Status.FULL: {self.Status.OPEN, self.Status.CLOSED, self.Status.CANCELLED},
            self.Status.CLOSED: {self.Status.OPEN, self.Status.CANCELLED},
            self.Status.EXPIRED: set(),
            self.Status.CANCELLED: set(),
        }
        if self.status == new_status:
            return self
        if new_status not in allowed.get(self.status, set()):
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )
        self.status = new_status
        return self

    def publish(self):
        if self.status != self.Status.DRAFT:
            raise ValidationError("Only draft jobs can be published.")
        if not self.is_publish_ready():
            raise ValidationError("This job is incomplete and cannot be published.")
        self.status = self.Status.PUBLISHED
        return self

    def close(self):
        self.transition_to(self.Status.CLOSED)
        return self

    def cancel(self):
        self.transition_to(self.Status.CANCELLED)
        return self

    def reopen(self):
        if self.status not in {self.Status.CLOSED, self.Status.FULL}:
            raise ValidationError("Only closed or full jobs can be reopened.")
        self.status = self.Status.OPEN
        return self

    def save(self, *args, **kwargs):
        self.full_clean(exclude=None)
        super().save(*args, **kwargs)


__all__ = ["JobCategory", "Job"]
