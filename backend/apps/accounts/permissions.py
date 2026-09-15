"""
Reusable DRF permission classes for CampusGig.

`accounts` owns these (rather than each domain app defining its own role
checks) because role is a property of the User model itself. Domain apps
added from Phase 4 onward (jobs, applications, chat, ...) import these
directly instead of re-implementing role checks.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class IsStudent(BasePermission):
    """Allows access only to authenticated users with the student role."""

    message = "This action is only available to student accounts."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.STUDENT)


class IsBusiness(BasePermission):
    """Allows access only to authenticated users with the business role."""

    message = "This action is only available to business accounts."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.BUSINESS)


class IsAdminRole(BasePermission):
    """
    Allows access only to authenticated users with the admin role.

    Distinct from DRF's built-in IsAdminUser (which checks `is_staff`):
    this checks CampusGig's own `role` field, which is what determines
    admin-only business logic (e.g. business verification review).
    """

    message = "This action is only available to platform administrators."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)


class IsVerified(BasePermission):
    """
    Allows access only to verified accounts. Wired in Phase 5 to the jobs
    publish action ("only verified businesses can publish") and synced in
    Phase 9 from BusinessVerification status via VerificationService
    (apps.safety) — VERIFIED sets it, REJECTED/REVOKED clears it.
    """

    message = "Your account must be verified to perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_verified)


class IsSelf(BasePermission):
    """
    Object-level permission: the request's user must be the object itself
    (or, for objects with a `user` FK, the owner). Used by MeView and
    intended for reuse by Phase 4's StudentProfile/BusinessProfile views.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        owner = obj if isinstance(obj, User) else getattr(obj, "user", None)
        return owner == request.user
