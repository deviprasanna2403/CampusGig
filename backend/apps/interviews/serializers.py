from django.utils import timezone
from rest_framework import serializers

from apps.applications.models import Application
from apps.interviews.models import Interview


class InterviewSerializer(serializers.ModelSerializer):
    application_id = serializers.PrimaryKeyRelatedField(source="application", queryset=Application.objects.all(), write_only=True)
    proposed_by = serializers.CharField(source="proposed_by.email", read_only=True)

    class Meta:
        model = Interview
        fields = ["id", "application_id", "proposed_by", "starts_at", "ends_at", "timezone_name", "meeting_url", "notes", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "proposed_by", "status", "created_at", "updated_at"]

    def validate(self, attrs):
        application = attrs.get("application", getattr(self.instance, "application", None))
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": "ends_at must be after starts_at."})
        if starts and starts <= timezone.now() and self.instance is None:
            raise serializers.ValidationError({"starts_at": "Interview must be scheduled in the future."})
        user = self.context["request"].user
        if application and user.id not in {application.student.user_id, application.job.business.user_id}:
            raise serializers.ValidationError("Only application participants can access this interview.")
        if application and application.status not in {Application.Status.SHORTLISTED, Application.Status.INTERVIEW}:
            raise serializers.ValidationError("Interview requires a shortlisted or interview-stage application.")
        return attrs

    def create(self, validated_data):
        validated_data["proposed_by"] = self.context["request"].user
        return super().create(validated_data)
