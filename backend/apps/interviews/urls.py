from django.urls import path

from apps.interviews.views import InterviewDetailView, InterviewListCreateView

app_name = "interviews"

urlpatterns = [
    path("", InterviewListCreateView.as_view(), name="list"),
    path("<uuid:pk>/", InterviewDetailView.as_view(), name="detail"),
]
