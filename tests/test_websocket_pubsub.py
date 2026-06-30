"""Tests for Redis WebSocket Pub/Sub fan-out."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.message import MessageRole
from app.websocket.protocol import MessageCreated
from app.websocket.pubsub import RedisWebSocketPubSub, conversation_channel


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))


class FakeManager:
    def __init__(self) -> None:
        self.broadcasts: list[tuple[uuid.UUID, dict[str, Any]]] = []

    async def broadcast_to_conversation(self, *, conversation_id: uuid.UUID, message: Any) -> None:
        self.broadcasts.append((conversation_id, message.model_dump(mode="json")))


def test_conversation_channel_uses_required_format() -> None:
    conversation_id = uuid.uuid4()

    assert conversation_channel(conversation_id) == f"chat:conversation:{conversation_id}"


async def test_publish_serializes_outbound_frame() -> None:
    conversation_id = uuid.uuid4()
    redis = FakeRedis()
    manager = FakeManager()
    pubsub = RedisWebSocketPubSub(
        manager=manager,  # type: ignore[arg-type]
        redis_factory=lambda: redis,  # type: ignore[arg-type]
    )
    frame = MessageCreated(
        payload={
            "id": uuid.uuid4(),
            "conversation_id": conversation_id,
            "sender_id": uuid.uuid4(),
            "role": MessageRole.USER,
            "content": "Hello",
            "created_at": datetime.now(UTC),
        }
    )

    await pubsub.publish(conversation_id=conversation_id, message=frame)

    assert redis.published[0][0] == conversation_channel(conversation_id)
    assert '"type":"message.created"' in redis.published[0][1]


async def test_handle_message_broadcasts_valid_redis_payload() -> None:
    conversation_id = uuid.uuid4()
    manager = FakeManager()
    pubsub = RedisWebSocketPubSub(
        manager=manager,  # type: ignore[arg-type]
        redis_factory=lambda: FakeRedis(),  # type: ignore[arg-type]
    )
    frame = MessageCreated(
        payload={
            "id": uuid.uuid4(),
            "conversation_id": conversation_id,
            "sender_id": uuid.uuid4(),
            "role": MessageRole.USER,
            "content": "Hello",
            "created_at": datetime.now(UTC),
        }
    )

    await pubsub._handle_message(conversation_id, frame.model_dump_json())

    assert manager.broadcasts == [
        (conversation_id, frame.model_dump(mode="json")),
    ]
