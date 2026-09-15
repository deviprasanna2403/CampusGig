from django.utils import timezone
from rest_framework import serializers

from apps.applications.models import Application
from apps.communication.models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    application_id = serializers.PrimaryKeyRelatedField(source="application", queryset=Application.objects.all(), write_only=True)
    other_party = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "application_id", "other_party", "is_active", "created_at", "updated_at", "unread_count"]
        read_only_fields = ["id", "other_party", "is_active", "created_at", "updated_at", "unread_count"]

    def validate(self, attrs):
        application = attrs["application"]
        user = self.context["request"].user
        if user.id not in {application.student.user_id, application.job.business.user_id}:
            raise serializers.ValidationError("Only application participants can create a conversation.")
        if application.status not in {Application.Status.SHORTLISTED, Application.Status.INTERVIEW, Application.Status.SELECTED}:
            raise serializers.ValidationError("Chat is only available after an application is shortlisted.")
        if Conversation.objects.filter(application=application).exists():
            raise serializers.ValidationError("A conversation already exists for this application.")
        attrs["_user"] = user
        return attrs

    def create(self, validated_data):
        user = validated_data.pop("_user")
        application = validated_data["application"]
        validated_data["student_id"] = application.student.user_id
        validated_data["business_id"] = application.job.business.user_id
        return super().create(validated_data)

    def get_other_party(self, obj):
        user = self.context["request"].user
        return obj.business.email if obj.student_id == user.id else obj.student.email

    def get_unread_count(self, obj):
        return obj.messages.exclude(sender=self.context["request"].user).filter(read_at__isnull=True).count()


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "body", "read_at", "created_at"]
        read_only_fields = ["id", "conversation", "sender", "read_at", "created_at"]

    def validate_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message body cannot be blank.")
        return value.strip()

    def create(self, validated_data):
        validated_data["sender"] = self.context["request"].user
        return super().create(validated_data)
