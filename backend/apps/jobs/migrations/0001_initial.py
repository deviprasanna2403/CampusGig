import uuid

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("profiles", "0002_studentprofile_skills"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobCategory",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="category name")),
                ("description", models.TextField(blank=True, verbose_name="description")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
            ],
            options={
                "verbose_name": "job category",
                "verbose_name_plural": "job categories",
                "db_table": "jobs_category",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Job",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200, verbose_name="job title")),
                ("description", models.TextField(blank=True, verbose_name="description")),
                ("job_type", models.CharField(choices=[("ONE_DAY_GIG", "One Day Gig"), ("WEEKEND", "Weekend"), ("PART_TIME", "Part Time"), ("TEMPORARY", "Temporary"), ("SEASONAL", "Seasonal"), ("EVENT_BASED", "Event Based"), ("INTERNSHIP", "Internship")], default="ONE_DAY_GIG", max_length=30, verbose_name="job type")),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        geography=True,
                        help_text="Exact job location in WGS84 (longitude, latitude).",
                        srid=4326,
                        verbose_name="job location",
                    ),
                ),
                ("start_date", models.DateField(verbose_name="start date")),
                ("end_date", models.DateField(verbose_name="end date")),
                ("start_time", models.TimeField(verbose_name="start time")),
                ("end_time", models.TimeField(verbose_name="end time")),
                ("payment_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name="payment amount")),
                ("payment_type", models.CharField(choices=[("HOURLY", "Hourly"), ("DAILY", "Daily"), ("WEEKLY", "Weekly"), ("MONTHLY", "Monthly"), ("FIXED_PROJECT", "Fixed Project")], default="HOURLY", max_length=30, verbose_name="payment type")),
                ("workers_required", models.PositiveIntegerField(default=1, verbose_name="workers required")),
                ("application_deadline", models.DateField(verbose_name="application deadline")),
                ("eligibility_notes", models.TextField(blank=True, verbose_name="eligibility requirements")),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("PUBLISHED", "Published"), ("OPEN", "Open"), ("FULL", "Full"), ("CLOSED", "Closed"), ("EXPIRED", "Expired"), ("CANCELLED", "Cancelled")], default="DRAFT", max_length=20, verbose_name="status")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
                ("business", models.ForeignKey(help_text="Employer/business account that owns the job.", on_delete=django.db.models.deletion.PROTECT, related_name="jobs", to="profiles.businessprofile")),
                ("category", models.ForeignKey(help_text="Job category reference data.", on_delete=django.db.models.deletion.PROTECT, related_name="jobs", to="jobs.jobcategory")),
            ],
            options={
                "verbose_name": "job",
                "verbose_name_plural": "jobs",
                "db_table": "jobs_job",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(fields=["status", "start_date"], name="job_status_start_date_idx"),
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(fields=["business", "status"], name="job_business_status_idx"),
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(fields=["category"], name="job_category_idx"),
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(fields=["payment_type"], name="job_payment_type_idx"),
        ),
        migrations.AddIndex(
            model_name="job",
            index=models.Index(fields=["application_deadline"], name="job_deadline_idx"),
        ),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.CheckConstraint(check=models.Q(end_date__gte=models.F("start_date")), name="job_end_date_after_or_equal_start_date"),
        ),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.CheckConstraint(check=models.Q(end_time__gt=models.F("start_time")), name="job_end_time_after_start_time"),
        ),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.CheckConstraint(check=models.Q(workers_required__gt=0), name="job_workers_required_positive"),
        ),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.CheckConstraint(check=models.Q(payment_amount__gt=0), name="job_payment_amount_positive"),
        ),
    ]
