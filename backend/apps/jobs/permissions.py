from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsBusinessOwnerOrAdmin(BasePermission):
    """Allow a business to manage only its own jobs, or an admin to manage all jobs."""

    message = "You do not have permission to manage this job."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == User.Role.ADMIN:
            return True
        if user.role == User.Role.BUSINESS:
            return bool(obj.business and obj.business.user_id == user.pk)
        return False
