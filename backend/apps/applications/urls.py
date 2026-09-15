from django.urls import path

from apps.applications.views import (
    BusinessApplicationDetailView,
    BusinessApplicationListView,
    StudentApplicationDetailView,
    StudentApplicationListCreateView,
    StudentApplicationWithdrawView,
)

app_name = "applications"

urlpatterns = [
    path("student/", StudentApplicationListCreateView.as_view(), name="student-list"),
    path("student/<uuid:pk>/", StudentApplicationDetailView.as_view(), name="student-detail"),
    path("student/<uuid:pk>/withdraw/", StudentApplicationWithdrawView.as_view(), name="student-withdraw"),
    path("business/", BusinessApplicationListView.as_view(), name="business-list"),
    path("business/<uuid:pk>/", BusinessApplicationDetailView.as_view(), name="business-detail"),
]
