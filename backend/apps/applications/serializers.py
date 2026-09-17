from rest_framework import serializers

from apps.applications.models import Application
from apps.jobs.models import Job
from apps.profiles.models import StudentProfile


class ApplicationSerializer(serializers.ModelSerializer):
    job_id = serializers.PrimaryKeyRelatedField(source="job", queryset=Job.objects.filter(status__in=[Job.Status.PUBLISHED, Job.Status.OPEN]), write_only=True)
    student = serializers.CharField(source="student.user.email", read_only=True)
    job = serializers.StringRelatedField(read_only=True)
    # Phase F6 reviews: the UI gates the "Leave review" action on the job
    # being completed (CLOSED/EXPIRED) and needs the counterparty's user id
    # to build POST /safety/reviews/<user_id>/. my_review_rating lets the UI
    # show "you rated X/5" instead of offering a duplicate review (the
    # backend still rejects duplicates — this is display sugar).
    job_status = serializers.CharField(source="job.status", read_only=True)
    counterparty_id = serializers.CharField(source="job.business.user_id", read_only=True)
    my_review_rating = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ["id", "job", "job_id", "student", "cover_note", "status", "job_status", "counterparty_id", "my_review_rating", "submitted_at", "created_at", "updated_at"]
        read_only_fields = ["id", "student", "status", "submitted_at", "created_at", "updated_at"]

    def get_my_review_rating(self, obj):
        from apps.safety.models import Review

        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        return (
            Review.objects.filter(application=obj, reviewer=request.user)
            .values_list("rating", flat=True)
            .first()
        )

    def validate(self, attrs):
        # get_or_create matches the lazy-profile convention used across the
        # project (no signals; profiles appear on first use).
        student, _ = StudentProfile.objects.get_or_create(user=self.context["request"].user)
        # `job` is only present on creation (job_id is write-only and a PATCH
        # omits it). Guarding with .get() instead of attrs["job"] fixes a
        # pre-existing KeyError (HTTP 500) on every student PATCH.
        job = attrs.get("job")
        if job is not None:
            duplicates = Application.objects.filter(student=student, job=job)
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError({"job_id": "You have already applied to this job."})
        if self.instance is None:
            attrs["_student"] = student
        return attrs

    def create(self, validated_data):
        validated_data["student"] = validated_data.pop("_student")
        return super().create(validated_data)


class BusinessApplicationSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student.user.email", read_only=True)
    job = serializers.StringRelatedField(read_only=True)
    # Phase F6 reviews — see ApplicationSerializer for the rationale.
    job_status = serializers.CharField(source="job.status", read_only=True)
    counterparty_id = serializers.CharField(source="student.user_id", read_only=True)
    my_review_rating = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ["id", "job", "student", "cover_note", "status", "job_status", "counterparty_id", "my_review_rating", "submitted_at", "created_at", "updated_at"]
        read_only_fields = ["id", "job", "student", "cover_note", "submitted_at", "created_at", "updated_at"]

    def get_my_review_rating(self, obj):
        from apps.safety.models import Review

        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return None
        return (
            Review.objects.filter(application=obj, reviewer=request.user)
            .values_list("rating", flat=True)
            .first()
        )

    def validate_status(self, value):
        if value == Application.Status.WITHDRAWN:
            raise serializers.ValidationError("Businesses cannot withdraw student applications.")
        return value
