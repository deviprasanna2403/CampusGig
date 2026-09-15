from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

phone_validator = RegexValidator(
    regex=r"^\+?[1-9]\d{7,14}$",
    message="Enter a valid phone number in international format, e.g. +919876543210.",
)

# Registration only ever creates a student or business account — admin
# accounts are provisioned separately (createsuperuser / Django admin),
# never through the public API.
SELF_REGISTERABLE_ROLES = [
    (User.Role.STUDENT, User.Role.STUDENT.label),
    (User.Role.BUSINESS, User.Role.BUSINESS.label),
]


class RegisterSerializer(serializers.ModelSerializer):
    """
    POST /api/v1/auth/register/ request body.

    Runs Django's full password validator chain (length, common-password
    check, similarity-to-user-attributes, not-entirely-numeric) via
    `validate_password`, in addition to requiring the two password fields
    to match.
    """

    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    phone = serializers.CharField(
        required=False, allow_blank=True, validators=[phone_validator]
    )
    role = serializers.ChoiceField(choices=SELF_REGISTERABLE_ROLES)

    class Meta:
        model = User
        fields = ["email", "phone", "role", "password", "password_confirm"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        # Runs Django's configured AUTH_PASSWORD_VALIDATORS (min length,
        # common-password check, not-entirely-numeric) against the raw
        # password before the user object exists.
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        attrs.pop("password_confirm")
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    """
    Safe, self-facing representation of a user. Used for:
    - GET/PATCH /api/v1/auth/me/ (phone is the only writable field)
    - embedded in register/login responses

    Deliberately excludes password, is_staff, is_superuser, and any
    internal flags — this is the shape that reaches the client, not the
    raw model.
    """

    class Meta:
        model = User
        fields = ["id", "email", "phone", "role", "is_verified", "date_joined"]
        read_only_fields = ["id", "email", "role", "is_verified", "date_joined"]

    def validate_phone(self, value):
        if value:
            phone_validator(value)
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends SimpleJWT's default login serializer to:
    - embed `role`, `email`, and `is_verified` as custom claims on the
      access token (so downstream services / the frontend can read role
      without a round trip), and
    - return the authenticated user's profile alongside the token pair.

    `USERNAME_FIELD` is read from the User model dynamically by the base
    class, so this already authenticates against `email`, not a
    `username` field that doesn't exist.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["is_verified"] = user.is_verified
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    """
    POST /api/v1/auth/logout/ request body. Blacklists the given refresh
    token so it can never be used again (see SIMPLE_JWT's
    BLACKLIST_AFTER_ROTATION / the token_blacklist app installed in
    Phase 3).
    """

    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            self._token = RefreshToken(value)
        except TokenError as exc:
            raise serializers.ValidationError("Invalid or expired refresh token.") from exc
        return value

    def save(self, **kwargs):
        self._token.blacklist()
