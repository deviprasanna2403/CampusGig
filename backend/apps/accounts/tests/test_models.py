import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user_defaults_to_student_role(self):
        user = User.objects.create_user(email="student@example.com", password="Str0ngPass!23")

        self.assertEqual(user.email, "student@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_verified)
        self.assertTrue(user.check_password("Str0ngPass!23"))
        self.assertIsInstance(user.id, uuid.UUID)

    def test_create_user_with_explicit_role(self):
        user = User.objects.create_user(
            email="business@example.com",
            password="Str0ngPass!23",
            role=User.Role.BUSINESS,
        )
        self.assertTrue(user.is_business)
        self.assertFalse(user.is_student)

    def test_email_is_normalized(self):
        user = User.objects.create_user(email="Student@EXAMPLE.com", password="Str0ngPass!23")
        self.assertEqual(user.email, "Student@example.com")

    def test_email_must_be_unique(self):
        User.objects.create_user(email="dup@example.com", password="Str0ngPass!23")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="dup@example.com", password="Str0ngPass!23")

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="Str0ngPass!23")

    def test_create_superuser_sets_admin_role_and_flags(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="Str0ngPass!23")

        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_verified)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_create_superuser_rejects_is_staff_false(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="admin2@example.com", password="Str0ngPass!23", is_staff=False
            )

    def test_str_representation(self):
        user = User.objects.create_user(email="student2@example.com", password="Str0ngPass!23")
        self.assertEqual(str(user), "student2@example.com (student)")
