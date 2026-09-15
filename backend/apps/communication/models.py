import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.applications.models import Application
from apps.core.models import TimeStampedModel
from apps.accounts.models import User


class Conversation(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="conversation")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_conversations")
    business = models.ForeignKey(User, on_delete=models.CASCADE, related_name="business_conversations")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "communication_conversation"
        indexes = [models.Index(fields=["student", "is_active"], name="conversation_student_idx"), models.Index(fields=["business", "is_active"], name="conversation_business_idx")]

    def clean(self):
        if self.student_id == self.business_id:
            raise ValidationError("A conversation requires two different participants.")
        if self.application_id:
            if self.application.student.user_id != self.student_id or self.application.job.business.user_id != self.business_id:
                raise ValidationError("Conversation participants must match the application.")
            if self.application.status not in {Application.Status.SHORTLISTED, Application.Status.INTERVIEW, Application.Status.SELECTED}:
                raise ValidationError("Chat is only available after an application is shortlisted.")


class Message(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(max_length=5000)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "communication_message"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"], name="message_conversation_idx"), models.Index(fields=["conversation", "read_at"], name="message_unread_idx")]

    def clean(self):
        if self.sender_id not in {self.conversation.student_id, self.conversation.business_id}:
            raise ValidationError("Only conversation participants can send messages.")
        if not self.body.strip():
            raise ValidationError("Message body cannot be blank.")
