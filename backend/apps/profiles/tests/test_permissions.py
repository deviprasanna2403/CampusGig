from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.profiles.permissions import IsAdminOrReadOnly

User = get_user_model()


class IsAdminOrReadOnlyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.student = User.objects.create_user(
            email="student@example.com", password="Str0ngPass!23", role=User.Role.STUDENT
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.com", password="Str0ngPass!23"
        )

    def _request_as(self, user, method="get"):
        request = getattr(self.factory, method)("/")
        request.user = user
        return request

    def test_safe_methods_allowed_for_any_authenticated_user(self):
        perm = IsAdminOrReadOnly()
        self.assertTrue(perm.has_permission(self._request_as(self.student, "get"), None))

    def test_write_methods_denied_for_non_admin(self):
        perm = IsAdminOrReadOnly()
        self.assertFalse(perm.has_permission(self._request_as(self.student, "post"), None))

    def test_write_methods_allowed_for_admin(self):
        perm = IsAdminOrReadOnly()
        self.assertTrue(perm.has_permission(self._request_as(self.admin, "post"), None))

    def test_anonymous_denied_write(self):
        perm = IsAdminOrReadOnly()
        self.assertFalse(perm.has_permission(self._request_as(AnonymousUser(), "post"), None))

    def test_anonymous_allowed_read(self):
        # Note: IsAuthenticated is combined with this permission at the
        # view level (see CampusViewSet.permission_classes) — this class
        # alone only encodes the read/write split.
        perm = IsAdminOrReadOnly()
        self.assertTrue(perm.has_permission(self._request_as(AnonymousUser(), "get"), None))
