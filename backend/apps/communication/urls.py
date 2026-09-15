from django.urls import path

from apps.communication.views import (
    ConversationDetailView,
    ConversationListCreateView,
    MessageListCreateView,
    MessageReadView,
)

app_name = "communication"

urlpatterns = [
    path("conversations/", ConversationListCreateView.as_view(), name="conversation-list"),
    path("conversations/<uuid:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<uuid:conversation_id>/messages/", MessageListCreateView.as_view(), name="message-list"),
    path("messages/<uuid:pk>/read/", MessageReadView.as_view(), name="message-read"),
]
