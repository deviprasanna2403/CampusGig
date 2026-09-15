from django.urls import path

from apps.matching.views import (
    JobMatchCalculateView,
    JobMatchListView,
    RecommendationListView,
    StudentEngagementDetailView,
    StudentEngagementListCreateView,
    StudentPreferenceView,
)

app_name = "matching"

urlpatterns = [
    path("recommendations/", RecommendationListView.as_view(), name="recommendations"),
    path("matches/", JobMatchListView.as_view(), name="match-list"),
    path("matches/calculate/<uuid:job_id>/", JobMatchCalculateView.as_view(), name="match-calculate"),
    path("preferences/", StudentPreferenceView.as_view(), name="preferences"),
    path("engagements/", StudentEngagementListCreateView.as_view(), name="engagement-list"),
    path("engagements/<uuid:pk>/", StudentEngagementDetailView.as_view(), name="engagement-detail"),
]
