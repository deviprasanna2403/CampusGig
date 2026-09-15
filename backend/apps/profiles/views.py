"""
Phase 4 views.

`StudentDiscoveryView` is the one endpoint that consumes
`settings.DEFAULT_DISCOVERY_RADIUS_KM` and PostGIS distance queries: it
finds campuses within `radius_km` of a reference campus, then returns the
students registered at those campuses. It never queries by an individual
student's location, because no such field exists on `StudentProfile` (see
apps/profiles/models.py module docstring).
"""

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, viewsets
from rest_framework.exceptions import ValidationError

from apps.accounts.permissions import IsBusiness, IsStudent
from apps.profiles.models import Availability, BusinessProfile, Campus, Skill, StudentProfile, StudentSkill
from apps.profiles.permissions import IsAdminOrReadOnly
from apps.profiles.serializers import (
    AvailabilitySerializer,
    BusinessProfileSerializer,
    CampusSerializer,
    SkillSerializer,
    StudentDiscoverySerializer,
    StudentProfileSerializer,
    StudentSkillSerializer,
)


class CampusViewSet(viewsets.ModelViewSet):
    """
    /api/v1/profiles/campuses/

    List/retrieve: any authenticated user (students choose their campus
    from here; businesses use it to pick a discovery reference point).
    Create/update/delete: admin role only (`IsAdminOrReadOnly`).

    Optional query params: `city` (exact, case-insensitive).
    """

    queryset = Campus.objects.filter(is_active=True)
    serializer_class = CampusSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__iexact=city)
        return qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class SkillViewSet(viewsets.ModelViewSet):
    """
    /api/v1/profiles/skills/

    List/retrieve: any authenticated user. Create/update/delete: admin
    role only. Optional query param: `category` (exact, case-insensitive).
    """

    queryset = Skill.objects.filter(is_active=True)
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__iexact=category)
        return qs

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class StudentProfileMeView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/v1/profiles/students/me/

    Student-only. The profile row is created on first access
    (get_or_create) rather than at registration time, so `apps.accounts`
    never needs a signal or other Phase 4 awareness.
    """

    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_object(self):
        profile, _created = StudentProfile.objects.select_related(
            "campus", "user"
        ).get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, profile)
        return profile


class BusinessProfileMeView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/v1/profiles/business/me/

    Business-only. Same lazy-creation pattern as `StudentProfileMeView`.
    """

    serializer_class = BusinessProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsBusiness]

    def get_object(self):
        profile, _created = BusinessProfile.objects.select_related(
            "campus", "user"
        ).get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, profile)
        return profile


class StudentSkillListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/profiles/students/me/skills/  — list the caller's own skills.
    POST /api/v1/profiles/students/me/skills/  — add one.
    """

    serializer_class = StudentSkillSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        profile, _created = StudentProfile.objects.get_or_create(user=self.request.user)
        return profile.student_skills.select_related("skill").all()


class StudentSkillDetailView(generics.RetrieveDestroyAPIView):
    """
    GET/DELETE /api/v1/profiles/students/me/skills/<uuid:pk>/

    Scoped to the caller's own StudentSkill rows only — the queryset
    filter (not just the permission class) enforces this, so a student
    cannot delete another student's skill row by guessing its UUID.
    """

    serializer_class = StudentSkillSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return StudentSkill.objects.filter(student__user=self.request.user).select_related("skill")


class AvailabilityListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/profiles/students/me/availability/  — list the caller's own slots.
    POST /api/v1/profiles/students/me/availability/  — add one.
    """

    serializer_class = AvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        profile, _created = StudentProfile.objects.get_or_create(user=self.request.user)
        return profile.availabilities.all()


class AvailabilityDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/profiles/students/me/availability/<uuid:pk>/

    Scoped to the caller's own Availability rows only, same reasoning as
    `StudentSkillDetailView`.
    """

    serializer_class = AvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Availability.objects.filter(student__user=self.request.user)


class StudentDiscoveryView(generics.ListAPIView):
    """
    GET /api/v1/profiles/discover/students/

    Business-only. Returns students whose *registered campus* is within
    `radius_km` (default `settings.DEFAULT_DISCOVERY_RADIUS_KM`, i.e. 20)
    of a reference campus. Results are paginated by the project default
    (`PageNumberPagination`, 20/page).

    Query params:
    - `campus_id` (optional): UUID of the reference campus. Defaults to
      the requesting business's own registered campus.
    - `radius_km` (optional): overrides the default radius. Must be
      between 1 and 100.
    - `skill` (optional): filter to students who have this skill
      (case-insensitive exact match on skill name).
    """

    serializer_class = StudentDiscoverySerializer
    permission_classes = [permissions.IsAuthenticated, IsBusiness]

    def get_queryset(self):
        origin_campus = self._resolve_origin_campus()
        radius_km = self._resolve_radius()

        nearby_campus_ids = Campus.objects.filter(
            is_active=True,
            location__distance_lte=(origin_campus.location, D(km=radius_km)),
        ).values_list("id", flat=True)

        queryset = (
            StudentProfile.objects.filter(campus_id__in=nearby_campus_ids)
            .select_related("campus", "user")
            .prefetch_related("student_skills__skill")
            .annotate(distance=Distance("campus__location", origin_campus.location))
        )

        skill = self.request.query_params.get("skill")
        if skill:
            queryset = queryset.filter(student_skills__skill__name__iexact=skill).distinct()

        return queryset.order_by("distance")

    def _resolve_origin_campus(self):
        campus_id = self.request.query_params.get("campus_id")
        if campus_id:
            try:
                return get_object_or_404(Campus, pk=campus_id, is_active=True)
            except (DjangoValidationError, ValueError) as exc:
                raise ValidationError({"campus_id": "Must be a valid campus UUID."}) from exc
            except Http404 as exc:
                raise ValidationError({"campus_id": "No active campus found with this id."}) from exc

        business_profile = getattr(self.request.user, "business_profile", None)
        if business_profile is None or business_profile.campus_id is None:
            raise ValidationError(
                {
                    "campus_id": (
                        "Provide campus_id, or set a campus on your business "
                        "profile first (PATCH /api/v1/profiles/business/me/)."
                    )
                }
            )
        return business_profile.campus

    def _resolve_radius(self):
        default_radius = getattr(settings, "DEFAULT_DISCOVERY_RADIUS_KM", 20)
        raw = self.request.query_params.get("radius_km")
        if raw is None:
            return default_radius
        try:
            radius = float(raw)
        except ValueError:
            raise ValidationError({"radius_km": "Must be a number."})
        if not (1 <= radius <= 100):
            raise ValidationError({"radius_km": "Must be between 1 and 100 km."})
        return radius
