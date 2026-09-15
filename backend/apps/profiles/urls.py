from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.profiles.views import (
    AvailabilityDetailView,
    AvailabilityListCreateView,
    BusinessProfileMeView,
    CampusViewSet,
    SkillViewSet,
    StudentDiscoveryView,
    StudentProfileMeView,
    StudentSkillDetailView,
    StudentSkillListCreateView,
)

app_name = "profiles"

router = DefaultRouter()
router.register("campuses", CampusViewSet, basename="campus")
router.register("skills", SkillViewSet, basename="skill")

urlpatterns = [
    path("students/me/", StudentProfileMeView.as_view(), name="student-me"),
    path(
        "students/me/skills/",
        StudentSkillListCreateView.as_view(),
        name="student-skill-list",
    ),
    path(
        "students/me/skills/<uuid:pk>/",
        StudentSkillDetailView.as_view(),
        name="student-skill-detail",
    ),
    path(
        "students/me/availability/",
        AvailabilityListCreateView.as_view(),
        name="availability-list",
    ),
    path(
        "students/me/availability/<uuid:pk>/",
        AvailabilityDetailView.as_view(),
        name="availability-detail",
    ),
    path("business/me/", BusinessProfileMeView.as_view(), name="business-me"),
    path("discover/students/", StudentDiscoveryView.as_view(), name="discover-students"),
    path("", include(router.urls)),
]
