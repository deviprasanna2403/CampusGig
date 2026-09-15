import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager
from apps.core.models import TimeStampedModel


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """
    Custom user model for CampusGig.

    Design decisions (see Phase 1, sections 2.2 and 5):
    - Email is the login identifier; there is no separate username.
    - `role` is fixed per account (student/business/admin) and drives
      which profile (StudentProfile/BusinessProfile, added in Phase 4)
      and which permission classes apply.
    - Primary key is a UUID, not an auto-incrementing integer, so user
      IDs are not sequentially enumerable via the API.
    - `is_verified` is generic on purpose: for students it will mean
      "email/campus verified" (Phase 4); for businesses it means KYC
      verification completed (Phase 9, `verification` app).
    """

    class Role(models.TextChoices):
        STUDENT = "student", _("Student")
        BUSINESS = "business", _("Business")
        ADMIN = "admin", _("Admin")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    phone = models.CharField(_("phone number"), max_length=20, blank=True, null=True)
    role = models.CharField(_("role"), max_length=20, choices=Role.choices, default=Role.STUDENT)

    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Unselect this instead of deleting accounts."),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can access the Django admin site."),
    )
    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        help_text=_(
            "For students: email/campus verified. For businesses: KYC "
            "verification completed (see the verification app, Phase 9)."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # email + password are always required by Django itself

    class Meta:
        db_table = "accounts_user"
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_business(self):
        return self.role == self.Role.BUSINESS

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN
