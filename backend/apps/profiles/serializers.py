"""
Phase 4 serializers.

Two API-shape decisions worth calling out:

1. `Campus.location` (a PostGIS geography Point) is never serialized as raw
   WKT/GeoJSON. `CampusSerializer` accepts/returns plain `latitude` /
   `longitude` floats and builds/reads the `Point` internally, so API
   clients never need to know PostGIS exists.

2. `StudentDiscoverySerializer` is a deliberately different, narrower
   serializer from `StudentProfileSerializer`. It is what businesses see
   in discovery results: no email, no phone, no raw campus coordinates,
   and — because the field doesn't exist on the model at all — no
   personal GPS location. Only `StudentProfileSerializer` (the student's
   own "me" view) sees the full profile.
"""

from django.contrib.gis.geos import Point
from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework import serializers

from apps.profiles.models import (
    Availability,
    BusinessProfile,
    Campus,
    Skill,
    StudentProfile,
    StudentSkill,
)


class CampusSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text="Decimal-degree latitude, WGS84 (e.g. 12.9716).",
    )
    longitude = serializers.FloatField(
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
        help_text="Decimal-degree longitude, WGS84 (e.g. 77.5946).",
    )

    class Meta:
        model = Campus
        fields = [
            "id",
            "name",
            "city",
            "state",
            "country",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Campus name cannot be blank.")
        qs = Campus.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A campus with this name already exists.")
        return value

    def create(self, validated_data):
        lat = validated_data.pop("latitude")
        lon = validated_data.pop("longitude")
        validated_data["location"] = Point(lon, lat, srid=4326)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        lat = validated_data.pop("latitude", None)
        lon = validated_data.pop("longitude", None)
        if lat is not None or lon is not None:
            lat = lat if lat is not None else instance.latitude
            lon = lon if lon is not None else instance.longitude
            validated_data["location"] = Point(lon, lat, srid=4326)
        return super().update(instance, validated_data)


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "category", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Skill name cannot be blank.")
        qs = Skill.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A skill with this name already exists.")
        return value


class StudentSkillSerializer(serializers.ModelSerializer):
    """
    Manages one row of the authenticated student's own skill list.
    `skill_id` (write) / `skill` (read, nested) split mirrors the
    write-vs-read asymmetry already used elsewhere (`CampusSerializer`'s
    latitude/longitude), so the client posts a plain UUID but reads back a
    full nested object.
    """

    skill = SkillSerializer(read_only=True)
    skill_id = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.filter(is_active=True), source="skill", write_only=True
    )

    class Meta:
        model = StudentSkill
        fields = ["id", "skill", "skill_id", "proficiency", "years_of_experience", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_years_of_experience(self, value):
        if value is not None and value > 50:
            raise serializers.ValidationError("years_of_experience must be 50 or fewer.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        student_profile, _created = StudentProfile.objects.get_or_create(user=request.user)
        skill = attrs.get("skill") or getattr(self.instance, "skill", None)

        qs = StudentSkill.objects.filter(student=student_profile, skill=skill)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"skill_id": "You have already added this skill to your profile."}
            )

        attrs["_student_profile"] = student_profile
        return attrs

    def create(self, validated_data):
        validated_data["student"] = validated_data.pop("_student_profile")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("_student_profile", None)
        return super().update(instance, validated_data)


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ["id", "day_of_week", "start_time", "end_time", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        day = attrs.get("day_of_week", getattr(self.instance, "day_of_week", None))

        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError({"end_time": "end_time must be after start_time."})

        request = self.context["request"]
        student_profile, _created = StudentProfile.objects.get_or_create(user=request.user)

        qs = Availability.objects.filter(student=student_profile, day_of_week=day)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        for slot in qs:
            if start < slot.end_time and slot.start_time < end:
                raise serializers.ValidationError(
                    "This availability slot overlaps with an existing slot for the same day."
                )

        attrs["_student_profile"] = student_profile
        return attrs

    def create(self, validated_data):
        validated_data["student"] = validated_data.pop("_student_profile")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("_student_profile", None)
        return super().update(instance, validated_data)


class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Full self-facing representation — GET/PATCH /api/v1/profiles/students/me/.
    This is the "profile completion" surface: the client PATCHes fields
    over one or more calls and reads `completion_percentage` / `is_complete`
    back to know what's left.
    """

    email = serializers.EmailField(source="user.email", read_only=True)
    campus = CampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.filter(is_active=True),
        source="campus",
        write_only=True,
        required=False,
        allow_null=True,
    )
    skills = StudentSkillSerializer(source="student_skills", many=True, read_only=True)
    availability = AvailabilitySerializer(source="availabilities", many=True, read_only=True)
    completion_percentage = serializers.ReadOnlyField()
    is_complete = serializers.ReadOnlyField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "email",
            "full_name",
            "campus",
            "campus_id",
            "year_of_study",
            "bio",
            "resume_headline",
            "skills",
            "availability",
            "completion_percentage",
            "is_complete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "created_at", "updated_at"]

    def validate_full_name(self, value):
        value = value.strip()
        if value and len(value) < 2:
            raise serializers.ValidationError("full_name looks too short.")
        return value


class BusinessProfileSerializer(serializers.ModelSerializer):
    """Full self-facing representation — GET/PATCH /api/v1/profiles/business/me/."""

    email = serializers.EmailField(source="user.email", read_only=True)
    campus = CampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.filter(is_active=True),
        source="campus",
        write_only=True,
        required=False,
        allow_null=True,
    )
    completion_percentage = serializers.ReadOnlyField()
    is_complete = serializers.ReadOnlyField()

    class Meta:
        model = BusinessProfile
        fields = [
            "id",
            "email",
            "business_name",
            "description",
            "website",
            "industry",
            "campus",
            "campus_id",
            "completion_percentage",
            "is_complete",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "created_at", "updated_at"]

    def validate_business_name(self, value):
        value = value.strip()
        if value and len(value) < 2:
            raise serializers.ValidationError("business_name looks too short.")
        return value


class StudentDiscoverySerializer(serializers.ModelSerializer):
    """
    Business-facing discovery result. Deliberately narrow: no email, no
    phone, no raw campus coordinates, and no personal GPS field (none
    exists). `distance_km` comes from the `distance` annotation added by
    `StudentDiscoveryView` (a GeoDjango `Distance()` expression measuring
    campus-to-campus distance, never a per-student location).
    """

    campus_name = serializers.CharField(source="campus.name", read_only=True)
    campus_city = serializers.CharField(source="campus.city", read_only=True)
    distance_km = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "full_name",
            "resume_headline",
            "year_of_study",
            "campus_name",
            "campus_city",
            "distance_km",
            "skills",
        ]

    def get_distance_km(self, obj):
        distance = getattr(obj, "distance", None)
        if distance is None:
            return None
        return round(distance.km, 2)

    def get_skills(self, obj):
        return [student_skill.skill.name for student_skill in obj.student_skills.all()]
