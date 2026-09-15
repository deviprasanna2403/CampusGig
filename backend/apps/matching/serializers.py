from rest_framework import serializers

from apps.jobs.models import Job
from apps.jobs.serializers import JobSerializer
from apps.matching.models import JobMatch, StudentJobEngagement, StudentPreference
from apps.jobs.models import JobCategory
from apps.profiles.models import StudentProfile


class JobMatchSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)
    components = serializers.SerializerMethodField()

    class Meta:
        model = JobMatch
        fields = [
            "id",
            "job",
            "score",
            "components",
            "explanation",
            "strategy",
            "calculated_at",
        ]
        read_only_fields = fields

    def get_components(self, obj):
        return {
            "skill": obj.skill_score,
            "location": obj.location_score,
            "availability": obj.availability_score,
            "experience": obj.experience_score,
        }


class RecommendationSerializer(serializers.Serializer):
    def to_representation(self, instance):
        match = instance["match"]
        return {
            "job": JobSerializer(instance["job"], context=self.context).data,
            "match_score": match.score,
            "recommendation_score": instance["recommendation_score"],
            "match_components": {
                "skill": match.skill_score,
                "location": match.location_score,
                "availability": match.availability_score,
                "experience": match.experience_score,
            },
            "recommendation_reasons": instance["recommendation_reasons"],
        }


class StudentPreferenceSerializer(serializers.ModelSerializer):
    preferred_category_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="preferred_categories",
        queryset=JobCategory.objects.filter(is_active=True),
        required=False,
    )

    class Meta:
        model = StudentPreference
        fields = [
            "id",
            "preferred_category_ids",
            "preferred_job_types",
            "preferred_payment_types",
            "minimum_payment",
            "maximum_payment",
            "maximum_distance_km",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_preferred_job_types(self, value):
        allowed = {choice[0] for choice in Job.JobType.choices}
        invalid = set(value) - allowed
        if invalid:
            raise serializers.ValidationError(f"Unsupported job types: {sorted(invalid)}")
        return value

    def validate_preferred_payment_types(self, value):
        allowed = {choice[0] for choice in Job.PaymentType.choices}
        invalid = set(value) - allowed
        if invalid:
            raise serializers.ValidationError(f"Unsupported payment types: {sorted(invalid)}")
        return value

    def validate(self, attrs):
        minimum = attrs.get("minimum_payment", getattr(self.instance, "minimum_payment", None))
        maximum = attrs.get("maximum_payment", getattr(self.instance, "maximum_payment", None))
        if minimum is not None and maximum is not None and maximum < minimum:
            raise serializers.ValidationError({"maximum_payment": "Must be at least minimum_payment."})
        distance = attrs.get(
            "maximum_distance_km",
            getattr(self.instance, "maximum_distance_km", 20),
        )
        if distance is not None and not 0 < distance <= 20:
            raise serializers.ValidationError(
                {"maximum_distance_km": "Must be between 0 and 20 km."}
            )
        return attrs

    def create(self, validated_data):
        categories = validated_data.pop("preferred_categories", [])
        student, _created = StudentProfile.objects.get_or_create(user=self.context["request"].user)
        preference, _created = StudentPreference.objects.update_or_create(student=student, defaults=validated_data)
        preference.preferred_categories.set(categories)
        return preference

    def update(self, instance, validated_data):
        categories = validated_data.pop("preferred_categories", None)
        instance = super().update(instance, validated_data)
        if categories is not None:
            instance.preferred_categories.set(categories)
        return instance


class StudentJobEngagementSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(source="job", queryset=Job.objects.all(), write_only=True)

    class Meta:
        model = StudentJobEngagement
        fields = ["id", "job_id", "job", "kind", "created_at"]
        read_only_fields = ["id", "job", "created_at"]

    def validate(self, attrs):
        job = attrs["job"]
        if job.status not in {Job.Status.PUBLISHED, Job.Status.OPEN}:
            raise serializers.ValidationError({"job_id": "Only published or open jobs can be engaged with."})
        student, _created = StudentProfile.objects.get_or_create(user=self.context["request"].user)
        if StudentJobEngagement.objects.filter(student=student, job=job, kind=attrs["kind"]).exists():
            raise serializers.ValidationError("This engagement already exists.")
        attrs["student"] = student
        return attrs

    def create(self, validated_data):
        return super().create(validated_data)
