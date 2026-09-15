"""
Phase 4 permission classes.

Role checks themselves (`IsStudent`, `IsBusiness`, `IsAdminRole`, `IsSelf`)
already exist in `apps.accounts.permissions` and are imported directly by
`apps/profiles/views.py` rather than redefined here — see that module's
docstring: "domain apps added from Phase 4 onward ... import these
directly instead of re-implementing role checks." Only the permission
that's genuinely new to this domain (shared reference data being
read-only for everyone but admins) lives here.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import User


class IsAdminOrReadOnly(BasePermission):
    """
    Campus and Skill are shared reference data: every authenticated role
    needs to read them (students pick a campus, everyone browses skills),
    but only platform admins may create/update/delete them.
    """

    message = "Only platform administrators can modify this resource."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
