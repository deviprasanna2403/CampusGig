from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.accounts.permissions import IsStudent
from apps.jobs.models import Job
from apps.matching.models import JobMatch, StudentJobEngagement, StudentPreference
from apps.matching.serializers import (
    JobMatchSerializer,
    RecommendationSerializer,
    StudentJobEngagementSerializer,
    StudentPreferenceSerializer,
)
from apps.matching.services import MatchingService, RecommendationService
from apps.profiles.models import StudentProfile


class StudentOwnedMixin:
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_student(self):
        student, _created = StudentProfile.objects.get_or_create(user=self.request.user)
        return student


class RecommendationListView(StudentOwnedMixin, generics.ListAPIView):
    serializer_class = RecommendationSerializer

    def list(self, request, *args, **kwargs):
        recommendations = RecommendationService().recommend(self.get_student())
        page = self.paginate_queryset(recommendations)
        serializer = self.get_serializer(page if page is not None else recommendations, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class JobMatchListView(StudentOwnedMixin, generics.ListAPIView):
    serializer_class = JobMatchSerializer

    def get_queryset(self):
        queryset = JobMatch.objects.filter(student=self.get_student()).select_related(
            "job__category", "job__business__user"
        ).prefetch_related("job__required_skills")
        job_id = self.request.query_params.get("job_id")
        if job_id:
            queryset = queryset.filter(job_id=job_id)
        minimum_score = self.request.query_params.get("minimum_score")
        if minimum_score:
            queryset = queryset.filter(score__gte=minimum_score)
        return queryset.order_by("-score", "-calculated_at")


class JobMatchCalculateView(StudentOwnedMixin, generics.CreateAPIView):
    serializer_class = JobMatchSerializer

    def create(self, request, *args, **kwargs):
        job = get_object_or_404(
            Job.objects.select_related("category", "business__user").prefetch_related("required_skills"),
            pk=kwargs["job_id"],
            status__in=[Job.Status.PUBLISHED, Job.Status.OPEN],
            is_active=True,
        )
        match = MatchingService().calculate(self.get_student(), job)
        return Response(self.get_serializer(match).data, status=status.HTTP_200_OK)


class StudentPreferenceView(StudentOwnedMixin, generics.RetrieveUpdateAPIView):
    serializer_class = StudentPreferenceSerializer

    def get_object(self):
        preference, _created = StudentPreference.objects.get_or_create(student=self.get_student())
        self.check_object_permissions(self.request, preference)
        return preference


class StudentEngagementListCreateView(StudentOwnedMixin, generics.ListCreateAPIView):
    serializer_class = StudentJobEngagementSerializer

    def get_queryset(self):
        queryset = StudentJobEngagement.objects.filter(student=self.get_student()).select_related("job")
        kind = self.request.query_params.get("kind")
        if kind:
            queryset = queryset.filter(kind=kind.upper())
        return queryset.order_by("-created_at")


class StudentEngagementDetailView(StudentOwnedMixin, generics.DestroyAPIView):
    serializer_class = StudentJobEngagementSerializer

    def get_queryset(self):
        return StudentJobEngagement.objects.filter(student=self.get_student())
