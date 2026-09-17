from django.contrib.gis.geos import Point
from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework import serializers

from apps.jobs.models import Job, JobCategory
from apps.profiles.models import BusinessProfile, Skill


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ["id", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category name cannot be blank.")
        qs = JobCategory.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value


class JobSerializer(serializers.ModelSerializer):
    category = JobCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=JobCategory.objects.filter(is_active=True),
        source="category",
        write_only=True,
        required=False,
    )
    required_skills = serializers.SerializerMethodField(read_only=True)
    required_skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.filter(is_active=True),
        many=True,
        source="required_skills",
        write_only=True,
        required=False,
    )
    business = serializers.SerializerMethodField(read_only=True)
    description = serializers.CharField(required=True, allow_blank=True)
    eligibility_notes = serializers.CharField(required=True, allow_blank=True)
    # Read-write: accepted on input (lat/lon pair -> PostGIS Point in
    # validate()) and echoed on output from the model's derived
    # latitude/longitude properties, so clients get the stored position back.
    location_latitude = serializers.FloatField(
        source="latitude",
        required=False,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
    )
    location_longitude = serializers.FloatField(
        source="longitude",
        required=False,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
    )

    class Meta:
        model = Job
        fields = [
            "id",
            "business",
            # Phase F6 reviews: lets the UI link to /safety/reviews/<id>/ for
            # the business account.
            "business_user_id",
            "viewer_has_history",
            "title",
            "description",
            "category",
            "category_id",
            "job_type",
            "required_skills",
            "required_skill_ids",
            "location_latitude",
            "location_longitude",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "payment_amount",
            "payment_type",
            "workers_required",
            "application_deadline",
            "eligibility_notes",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "business", "status", "created_at", "updated_at"]

    business_user_id = serializers.CharField(source="business.user_id", read_only=True)
    # F6: true when the requesting student has an application or engagement
    # on this job — the signal for showing the taken-down/unavailable banner
    # instead of a bare 404 once the job leaves discovery.
    viewer_has_history = serializers.SerializerMethodField()

    def get_viewer_has_history(self, obj):
        from apps.applications.models import Application
        from apps.matching.models import StudentJobEngagement

        request = self.context.get("request")
        if request is None or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        if request.user.role != "student":
            return False
        return (
            Application.objects.filter(job=obj, student__user=request.user).exists()
            or StudentJobEngagement.objects.filter(job=obj, student__user=request.user).exists()
        )

    def get_business(self, obj):
        return obj.business.user.email if obj.business else None

    def get_required_skills(self, obj):
        return [{"id": str(skill.id), "name": skill.name} for skill in obj.required_skills.all()]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("title is required.")
        return value

    def validate_description(self, value):
        if value is None:
            raise serializers.ValidationError("description is required.")
        return value.strip()

    def validate_eligibility_notes(self, value):
        if value is None:
            raise serializers.ValidationError("eligibility_notes is required.")
        return value.strip()

    def validate(self, attrs):
        request = self.context.get("request")
        instance = self.instance

        raw_category = self.initial_data.get("category")
        if raw_category and "category" not in attrs and "category_id" not in attrs:
            category_obj = JobCategory.objects.filter(name__iexact=str(raw_category), is_active=True).first()
            if category_obj is None:
                raise serializers.ValidationError({"category": "Category is invalid or inactive."})
            attrs["category"] = category_obj

        if "category" in self.initial_data and self.initial_data["category"] in (None, ""):
            raise serializers.ValidationError({"category": "Category is required."})

        if "start_date" in attrs and "end_date" in attrs:
            start = attrs["start_date"]
            end = attrs["end_date"]
            if end < start:
                raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        elif instance is not None:
            start = attrs.get("start_date", instance.start_date)
            end = attrs.get("end_date", instance.end_date)
            if end < start:
                raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})

        if "start_time" in attrs and "end_time" in attrs:
            start = attrs["start_time"]
            end = attrs["end_time"]
            if end <= start:
                raise serializers.ValidationError({"end_time": "end_time must be after start_time."})
        elif instance is not None:
            start = attrs.get("start_time", instance.start_time)
            end = attrs.get("end_time", instance.end_time)
            if end <= start:
                raise serializers.ValidationError({"end_time": "end_time must be after start_time."})

        deadline = attrs.get("application_deadline", getattr(instance, "application_deadline", None))
        start_date = attrs.get("start_date", getattr(instance, "start_date", None))
        if deadline and start_date and deadline > start_date:
            raise serializers.ValidationError({"application_deadline": "application_deadline must be on or before start_date."})

        if "payment_amount" in attrs:
            amount = attrs["payment_amount"]
            if amount is not None and amount <= 0:
                raise serializers.ValidationError({"payment_amount": "payment_amount must be positive."})

        if "workers_required" in attrs:
            workers = attrs["workers_required"]
            if workers is not None and workers <= 0:
                raise serializers.ValidationError({"workers_required": "workers_required must be positive."})
            if instance and instance.status not in {Job.Status.DRAFT, None} and workers < instance.workers_required:
                raise serializers.ValidationError({"workers_required": "workers_required may only increase after publication."})

        if instance and instance.status not in {Job.Status.DRAFT, None}:
            deadline_field = "application_deadline"
            if deadline_field in self.initial_data:
                incoming = self.initial_data[deadline_field]
                incoming_date = None
                try:
                    incoming_date = serializers.DateField().run_validation(incoming)
                except serializers.ValidationError:
                    incoming_date = None
                if incoming_date is not None and incoming_date < instance.application_deadline:
                    raise serializers.ValidationError({"application_deadline": "application_deadline may only be extended after publication."})

        if request and request.user.is_authenticated:
            if request.user.role != "business" and not self.instance:
                raise serializers.ValidationError("Only business accounts can create jobs.")

        # Bound under their source names ("latitude"/"longitude") because
        # the fields declare source= — neither is a real model column, so
        # both must be popped and folded into the location Point.
        lat = attrs.pop("latitude", None)
        lon = attrs.pop("longitude", None)
        if lat is not None or lon is not None:
            lat = lat if lat is not None else getattr(instance, "latitude", None)
            lon = lon if lon is not None else getattr(instance, "longitude", None)
            if lat is None or lon is None:
                raise serializers.ValidationError({"location": "Both latitude and longitude are required for a job location."})
            attrs["location"] = Point(lon, lat, srid=4326)
        elif instance is None:
            raise serializers.ValidationError({"location": "A valid job location is required."})

        # Value-based protection, evaluated AFTER the lat/lon fold so a
        # changed location submitted via location_latitude/location_longitude
        # is caught too: a protected field may be *submitted* on a published
        # job as long as its value is unchanged — only a real change is
        # rejected. (Previously this check was presence-based, which 400'd
        # unchanged resubmissions from clients that PATCH full objects.)
        if instance and instance.status not in {Job.Status.DRAFT, None}:
            protected_fields = [
                "title",
                "category",
                "job_type",
                "payment_type",
                "payment_amount",
                "start_date",
                "end_date",
                "location",
            ]
            for field in protected_fields:
                if field in attrs and attrs[field] != getattr(instance, field, None):
                    raise serializers.ValidationError({field: f"{field} is protected after publication."})

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        business_profile = getattr(request.user, "business_profile", None)
        if not business_profile:
            raise serializers.ValidationError("Business profile is required before creating jobs.")

        validated_data["business"] = business_profile
        # Defensive: latitude/longitude are folded into the location Point
        # in validate(); pop anyway so they can never reach Model.create().
        validated_data.pop("latitude", None)
        validated_data.pop("longitude", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Same defensive pop as create() — see validate().
        validated_data.pop("latitude", None)
        validated_data.pop("longitude", None)
        return super().update(instance, validated_data)
