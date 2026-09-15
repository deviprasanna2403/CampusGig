from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.jobs.views import JobCategoryViewSet, JobViewSet

app_name = "jobs"

router = DefaultRouter()
router.register(r"categories", JobCategoryViewSet, basename="category")
router.register(r"jobs", JobViewSet, basename="job")

urlpatterns = [
    path("", include(router.urls)),
]
