from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/

    Public endpoint. Creates a `student` or `business` account (never
    `admin` — see RegisterSerializer.SELF_REGISTERABLE_ROLES) and returns
    a JWT pair immediately, so the client doesn't need a separate login
    call right after signup.
    """

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = CustomTokenObtainPairSerializer.get_token(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/

    Body: {"email": "...", "password": "..."}
    Returns: {"access": "...", "refresh": "...", "user": {...}}
    """

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"


class RefreshView(TokenRefreshView):
    """
    POST /api/v1/auth/token/refresh/

    Body: {"refresh": "..."}
    Returns a new access token and, because ROTATE_REFRESH_TOKENS=True and
    BLACKLIST_AFTER_ROTATION=True (see SIMPLE_JWT settings), a new refresh
    token — the old refresh token is blacklisted and can't be reused.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = "auth"


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Body: {"refresh": "..."}
    Requires a valid access token (Authorization: Bearer <access>).
    Blacklists the supplied refresh token — this is CampusGig's
    logout/token-invalidation strategy: access tokens are short-lived
    (15 min default) and are not individually revocable, but the refresh
    token that would otherwise mint new ones is invalidated immediately,
    so the session cannot be silently extended after logout.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/v1/auth/me/  — the authenticated user's own profile.
    PATCH /api/v1/auth/me/  — update the mutable subset of the profile.
                              Only `phone` is writable; `email`, `role`,
                              and `is_verified` are read-only on
                              UserSerializer, so submitting them is
                              silently ignored rather than erroring, per
                              DRF's normal read_only_fields behaviour.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj = self.request.user
        self.check_object_permissions(self.request, obj)
        return obj
