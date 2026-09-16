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
        read_only_fields = ["id", "proposed_by", "created_at", "updated_at"]

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
        if self.instance is not None and "status" in attrs:
            self._validate_transition(attrs["status"])
        else:
            # Interviews always start SCHEDULED; an incoming status on create
            # is ignored rather than honored.
            attrs.pop("status", None)
        return attrs

    def _validate_transition(self, new_status):
        """Role-aware status transitions (Phase 6 follow-up, wired to the F4 UI):
        the student may Confirm/Decline a SCHEDULED interview; the business may
        Cancel it; either participant may mark a CONFIRMED interview Completed.
        """
        current = self.instance.status
        user = self.context["request"].user
        application = self.instance.application
        is_student = user.id == application.student.user_id
        is_business = user.id == application.job.business.user_id

        allowed: set
        if current == Interview.Status.SCHEDULED:
            allowed = {Interview.Status.CONFIRMED, Interview.Status.DECLINED} if is_student else {Interview.Status.CANCELLED}
        elif current == Interview.Status.CONFIRMED:
            allowed = {Interview.Status.COMPLETED}
        else:
            allowed = set()

        if new_status == current:
            return
        if new_status not in allowed:
            raise serializers.ValidationError({"status": f"Cannot move an interview from {current} to {new_status}."})
        if not (is_student or is_business):
            raise serializers.ValidationError({"status": "Only application participants can update this interview."})

    def create(self, validated_data):
        validated_data["proposed_by"] = self.context["request"].user
        return super().create(validated_data)
