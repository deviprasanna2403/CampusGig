from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from apps.communication.models import Conversation, Message
from apps.communication.serializers import ConversationSerializer, MessageSerializer
from apps.notifications.services import create_notification
from apps.notifications.models import Notification
from apps.communication.broadcast import broadcast_message


class ConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(student=self.request.user) | Conversation.objects.filter(business=self.request.user)


class ConversationDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(student=self.request.user) | Conversation.objects.filter(business=self.request.user)


class MessageListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer

    def get_conversation(self):
        return get_object_or_404(
            Conversation.objects.filter(student=self.request.user) | Conversation.objects.filter(business=self.request.user),
            pk=self.kwargs["conversation_id"],
            is_active=True,
        )

    def get_queryset(self):
        return self.get_conversation().messages.select_related("sender").all()

    def perform_create(self, serializer):
        message = serializer.save(conversation=self.get_conversation())
        broadcast_message(message)
        recipient = message.conversation.business if message.sender_id == message.conversation.student_id else message.conversation.student
        create_notification(
            recipient=recipient,
            event=Notification.Event.INTERVIEW_RESPONSE,
            title="New chat message",
            body=f"You have a new message about {message.conversation.application.job.title}.",
            payload={"conversation_id": str(message.conversation_id), "message_id": str(message.id)},
        )


class MessageReadView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    http_method_names = ["patch"]

    def get_queryset(self):
        return Message.objects.filter(conversation__student=self.request.user) | Message.objects.filter(conversation__business=self.request.user)

    def patch(self, request, *args, **kwargs):
        message = get_object_or_404(self.get_queryset(), pk=kwargs["pk"])
        message.read_at = timezone.now()
        message.save(update_fields=["read_at", "updated_at"])
        return Response(self.get_serializer(message).data)
