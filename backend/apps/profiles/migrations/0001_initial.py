import uuid

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Campus",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, unique=True, verbose_name="campus name")),
                ("city", models.CharField(max_length=100, verbose_name="city")),
                ("state", models.CharField(blank=True, max_length=100, verbose_name="state")),
                ("country", models.CharField(default="India", max_length=100, verbose_name="country")),
                (
                    "location",
                    django.contrib.gis.db.models.fields.PointField(
                        geography=True,
                        srid=4326,
                        help_text=(
                            "Campus coordinates (WGS84). Drives the 20 km "
                            "campus-based discovery radius "
                            "(settings.DEFAULT_DISCOVERY_RADIUS_KM)."
                        ),
                        verbose_name="location",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
            ],
            options={
                "verbose_name": "campus",
                "verbose_name_plural": "campuses",
                "db_table": "profiles_campus",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Skill",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100, unique=True, verbose_name="skill name")),
                ("category", models.CharField(blank=True, max_length=100, verbose_name="category")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
            ],
            options={
                "verbose_name": "skill",
                "verbose_name_plural": "skills",
                "db_table": "profiles_skill",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="StudentProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("full_name", models.CharField(blank=True, max_length=150, verbose_name="full name")),
                (
                    "year_of_study",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        choices=[
                            (1, "1st Year"),
                            (2, "2nd Year"),
                            (3, "3rd Year"),
                            (4, "4th Year"),
                            (5, "5th Year"),
                            (6, "Postgraduate"),
                        ],
                        null=True,
                        verbose_name="year of study",
                    ),
                ),
                ("bio", models.TextField(blank=True, max_length=1000, verbose_name="bio")),
                ("resume_headline", models.CharField(blank=True, max_length=150, verbose_name="headline")),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        help_text=(
                            "The student's registered campus. This — not any "
                            "personal GPS coordinate — is what campus-based "
                            "discovery filters on."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student_profiles",
                        to="profiles.campus",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "student profile",
                "verbose_name_plural": "student profiles",
                "db_table": "profiles_student_profile",
            },
        ),
        migrations.CreateModel(
            name="BusinessProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("business_name", models.CharField(blank=True, max_length=200, verbose_name="business name")),
                ("description", models.TextField(blank=True, max_length=2000, verbose_name="description")),
                ("website", models.URLField(blank=True, verbose_name="website")),
                ("industry", models.CharField(blank=True, max_length=100, verbose_name="industry")),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        help_text="Default reference campus for this business's student discovery searches.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="business_profiles",
                        to="profiles.campus",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "business profile",
                "verbose_name_plural": "business profiles",
                "db_table": "profiles_business_profile",
            },
        ),
        migrations.CreateModel(
            name="StudentSkill",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "proficiency",
                    models.CharField(
                        choices=[
                            ("beginner", "Beginner"),
                            ("intermediate", "Intermediate"),
                            ("advanced", "Advanced"),
                            ("expert", "Expert"),
                        ],
                        default="beginner",
                        max_length=20,
                        verbose_name="proficiency",
                    ),
                ),
                (
                    "years_of_experience",
                    models.PositiveSmallIntegerField(
                        blank=True, null=True, verbose_name="years of experience"
                    ),
                ),
                (
                    "skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_skills",
                        to="profiles.skill",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_skills",
                        to="profiles.studentprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "student skill",
                "verbose_name_plural": "student skills",
                "db_table": "profiles_student_skill",
                "ordering": ["-proficiency", "skill__name"],
            },
        ),
        migrations.CreateModel(
            name="Availability",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "day_of_week",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Monday"),
                            (1, "Tuesday"),
                            (2, "Wednesday"),
                            (3, "Thursday"),
                            (4, "Friday"),
                            (5, "Saturday"),
                            (6, "Sunday"),
                        ],
                        verbose_name="day of week",
                    ),
                ),
                ("start_time", models.TimeField(verbose_name="start time")),
                ("end_time", models.TimeField(verbose_name="end time")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="availabilities",
                        to="profiles.studentprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "availability slot",
                "verbose_name_plural": "availability slots",
                "db_table": "profiles_availability",
                "ordering": ["day_of_week", "start_time"],
            },
        ),
        # --- Indexes -----------------------------------------------------
        migrations.AddIndex(
            model_name="skill",
            index=models.Index(fields=["category"], name="skill_category_idx"),
        ),
        migrations.AddIndex(
            model_name="studentprofile",
            index=models.Index(fields=["campus"], name="student_profile_campus_idx"),
        ),
        migrations.AddIndex(
            model_name="businessprofile",
            index=models.Index(fields=["campus"], name="business_profile_campus_idx"),
        ),
        migrations.AddIndex(
            model_name="studentskill",
            index=models.Index(fields=["skill"], name="student_skill_skill_idx"),
        ),
        migrations.AddIndex(
            model_name="availability",
            index=models.Index(fields=["student", "day_of_week"], name="availability_student_day_idx"),
        ),
        # --- Constraints ---------------------------------------------------
        migrations.AddConstraint(
            model_name="studentskill",
            constraint=models.UniqueConstraint(fields=["student", "skill"], name="uniq_student_skill"),
        ),
        migrations.AddConstraint(
            model_name="availability",
            constraint=models.CheckConstraint(
                check=models.Q(end_time__gt=models.F("start_time")),
                name="availability_end_after_start",
            ),
        ),
    ]
