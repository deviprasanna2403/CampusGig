from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import IsBusiness, IsStudent
from apps.applications.models import Application
from apps.applications.serializers import ApplicationSerializer, BusinessApplicationSerializer
from apps.notifications.services import notify_application_status, notify_application_submitted, notify_application_withdrawn
from apps.profiles.models import StudentProfile


class StudentApplicationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        student, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        return Application.objects.filter(student=student).select_related("job", "job__business__user")

    @transaction.atomic
    def perform_create(self, serializer):
        application = serializer.save()
        notify_application_submitted(application)


class StudentApplicationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        student, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        return Application.objects.filter(student=student).select_related("job", "job__business__user")

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status in {Application.Status.SELECTED, Application.Status.REJECTED, Application.Status.WITHDRAWN}:
            raise serializers.ValidationError("This application can no longer be changed.")
        old_status = instance.status
        application = serializer.save()
        if application.status == Application.Status.WITHDRAWN:
            notify_application_withdrawn(application)
        elif application.status != old_status:
            notify_application_status(application, old_status)


class StudentApplicationWithdrawView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        student, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        return Application.objects.filter(student=student)

    def update(self, request, *args, **kwargs):
        application = self.get_object()
        if application.status in {Application.Status.SELECTED, Application.Status.REJECTED, Application.Status.WITHDRAWN}:
            raise ValidationError("This application can no longer be withdrawn.")
        application.status = Application.Status.WITHDRAWN
        application.save(update_fields=["status", "updated_at"])
        notify_application_withdrawn(application)
        return Response(self.get_serializer(application).data)


class BusinessApplicationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsBusiness]
    serializer_class = BusinessApplicationSerializer

    def get_queryset(self):
        queryset = Application.objects.filter(job__business__user=self.request.user).select_related("student__user", "job")
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value.upper())
        return queryset


class BusinessApplicationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsBusiness]
    serializer_class = BusinessApplicationSerializer

    def get_queryset(self):
        return Application.objects.filter(job__business__user=self.request.user).select_related("student__user", "job")

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status
        application = serializer.save()
        if application.status != old_status:
            notify_application_status(application, old_status)
