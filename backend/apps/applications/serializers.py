from rest_framework import serializers

from apps.applications.models import Application
from apps.jobs.models import Job
from apps.profiles.models import StudentProfile


class ApplicationSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(source="job", queryset=Job.objects.filter(status__in=[Job.Status.PUBLISHED, Job.Status.OPEN]), write_only=True)
    student = serializers.CharField(source="student.user.email", read_only=True)
    job = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "job_id", "student", "cover_note", "status", "submitted_at", "created_at", "updated_at"]
        read_only_fields = ["id", "student", "status", "submitted_at", "created_at", "updated_at"]

    def validate(self, attrs):
        student, _ = StudentProfile.objects.get_or_create(user=self.context["request"].user)
        job = attrs["job"]
        if Application.objects.filter(student=student, job=job).exists():
            raise serializers.ValidationError({"job_id": "You have already applied to this job."})
        attrs["_student"] = student
        return attrs

    def create(self, validated_data):
        validated_data["student"] = validated_data.pop("_student")
        return super().create(validated_data)


class BusinessApplicationSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student.user.email", read_only=True)
    job = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Application
        fields = ["id", "job", "student", "cover_note", "status", "submitted_at", "created_at", "updated_at"]
        read_only_fields = ["id", "job", "student", "cover_note", "submitted_at", "created_at", "updated_at"]

    def validate_status(self, value):
        if value == Application.Status.WITHDRAWN:
            raise serializers.ValidationError("Businesses cannot withdraw student applications.")
        return value
