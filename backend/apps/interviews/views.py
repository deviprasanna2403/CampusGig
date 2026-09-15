from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions

from apps.applications.models import Application
from apps.interviews.models import Interview
from apps.interviews.serializers import InterviewSerializer
from apps.notifications.models import Notification
from apps.notifications.services import notify_interview


class InterviewListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InterviewSerializer

    def get_queryset(self):
        return Interview.objects.filter(
            application__student__user=self.request.user
        ) | Interview.objects.filter(application__job__business__user=self.request.user)

    def perform_create(self, serializer):
        interview = serializer.save()
        notify_interview(interview)


class InterviewDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InterviewSerializer

    def get_queryset(self):
        return Interview.objects.filter(
            application__student__user=self.request.user
        ) | Interview.objects.filter(application__job__business__user=self.request.user)

    def perform_update(self, serializer):
        interview = serializer.save()
        notify_interview(interview, Notification.Event.INTERVIEW_UPDATED)
