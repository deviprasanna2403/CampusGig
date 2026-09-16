from rest_framework import serializers

from apps.core.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only rendering of an audit row for the admin-only list API.

    All fields are read-only by construction: the API has no write
    endpoints and `AuditService` is the only writer.
    """

    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_email",
            "actor_role",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor else None
