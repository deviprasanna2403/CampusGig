import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.communication.models import Conversation, Message
from apps.communication.broadcast import abroadcast_message


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated or not await self.user_can_access():
            await self.close(code=4403)
            return
        self.group_name = f"conversation_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        body = str(content.get("body", "")).strip()
        if not body:
            await self.send_json({"error": "Message body cannot be blank."})
            return
        message = await self.create_message(body)
        await abroadcast_message(message)

    async def chat_message(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def user_can_access(self):
        return Conversation.objects.filter(pk=self.conversation_id).filter(student=self.user).exists() or Conversation.objects.filter(pk=self.conversation_id, business=self.user).exists()

    @database_sync_to_async
    def create_message(self, body):
        conversation = Conversation.objects.get(pk=self.conversation_id)
        return Message.objects.create(conversation=conversation, sender=self.user, body=body)
