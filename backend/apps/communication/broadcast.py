"""Push completed messages to every open conversation socket.

Both send paths (WS consumer and REST create) funnel through this helper
so clients that adopt the WebSocket — or haven't yet — observe identical
updates regardless of which path created the message. Kept in its own
module because the consumer imports it, so it must not import the
consumer (or views) back.
"""

from asgiref.sync import async_to_sync

from channels.layers import get_channel_layer

from apps.communication.models import Message


def _payload(message: Message) -> dict:
    return {
        "type": "chat.message",
        "message": {
            "id": str(message.id),
            "body": message.body,
            "sender_id": str(message.sender_id),
            "created_at": message.created_at.isoformat(),
        },
    }


async def abroadcast_message(message: Message) -> None:
    """Async broadcast — await this from async code (the WS consumer).

    ``async_to_sync`` cannot be called from inside a running event loop,
    so the consumer must use this variant directly.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:  # WSGI-only deployment; nothing to broadcast to
        return
    await channel_layer.group_send(f"conversation_{message.conversation_id}", _payload(message))


def broadcast_message(message: Message) -> None:
    """Sync broadcast — call this from sync code (the REST create view)."""
    channel_layer = get_channel_layer()
    if channel_layer is None:  # WSGI-only deployment; nothing to broadcast to
        return
    async_to_sync(channel_layer.group_send)(f"conversation_{message.conversation_id}", _payload(message))
