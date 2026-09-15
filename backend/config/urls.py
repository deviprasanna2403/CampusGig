from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls", namespace="core")),
    path("api/v1/auth/", include("apps.accounts.urls", namespace="accounts")),
    # StudentProfile/BusinessProfile/Campus/Skill/StudentSkill/Availability (Phase 4)
    path("api/v1/profiles/", include("apps.profiles.urls", namespace="profiles")),
    path("api/v1/jobs/", include("apps.jobs.urls", namespace="jobs")),
        path("api/v1/matching/", include("apps.matching.urls", namespace="matching")),
        path("api/v1/applications/", include("apps.applications.urls", namespace="applications")),
        path("api/v1/communication/", include("apps.communication.urls", namespace="communication")),
        path("api/v1/interviews/", include("apps.interviews.urls", namespace="interviews")),
        path("api/v1/notifications/", include("apps.notifications.urls", namespace="notifications")),
        path("api/v1/safety/", include("apps.safety.urls", namespace="safety")),
    # OpenAPI schema + interactive docs (Phase 3). Publicly viewable — see
    # SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] in config/settings/base.py.
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
