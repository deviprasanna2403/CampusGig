from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "event", "title", "body", "payload", "read_at", "email_sent_at", "created_at"]
        read_only_fields = ["id", "event", "title", "body", "payload", "email_sent_at", "created_at"]
