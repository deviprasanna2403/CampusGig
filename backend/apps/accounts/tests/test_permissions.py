from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.permissions import IsAdminRole, IsBusiness, IsSelf, IsStudent, IsVerified

User = get_user_model()


class RolePermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.student = User.objects.create_user(
            email="student@example.com", password="Str0ngPass!23", role=User.Role.STUDENT
        )
        self.business = User.objects.create_user(
            email="business@example.com", password="Str0ngPass!23", role=User.Role.BUSINESS
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.com", password="Str0ngPass!23"
        )

    def _request_as(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_is_student_allows_only_students(self):
        perm = IsStudent()
        self.assertTrue(perm.has_permission(self._request_as(self.student), None))
        self.assertFalse(perm.has_permission(self._request_as(self.business), None))
        self.assertFalse(perm.has_permission(self._request_as(self.admin), None))

    def test_is_business_allows_only_businesses(self):
        perm = IsBusiness()
        self.assertFalse(perm.has_permission(self._request_as(self.student), None))
        self.assertTrue(perm.has_permission(self._request_as(self.business), None))
        self.assertFalse(perm.has_permission(self._request_as(self.admin), None))

    def test_is_admin_role_allows_only_admins(self):
        perm = IsAdminRole()
        self.assertFalse(perm.has_permission(self._request_as(self.student), None))
        self.assertFalse(perm.has_permission(self._request_as(self.business), None))
        self.assertTrue(perm.has_permission(self._request_as(self.admin), None))

    def test_is_verified_checks_flag_not_role(self):
        self.student.is_verified = True
        self.student.save(update_fields=["is_verified"])
        perm = IsVerified()
        self.assertTrue(perm.has_permission(self._request_as(self.student), None))
        self.assertFalse(perm.has_permission(self._request_as(self.business), None))

    def test_is_self_object_permission(self):
        perm = IsSelf()
        request = self._request_as(self.student)
        self.assertTrue(perm.has_object_permission(request, None, self.student))
        self.assertFalse(perm.has_object_permission(request, None, self.business))

    def test_role_permissions_deny_anonymous_users(self):
        request = self._request_as(AnonymousUser())
        self.assertFalse(IsStudent().has_permission(request, None))
        self.assertFalse(IsBusiness().has_permission(request, None))
        self.assertFalse(IsAdminRole().has_permission(request, None))
        self.assertFalse(IsVerified().has_permission(request, None))
