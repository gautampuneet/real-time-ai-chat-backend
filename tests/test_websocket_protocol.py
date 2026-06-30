"""Tests for WebSocket protocol models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.models.message import MessageRole
from app.websocket.protocol import (
    AssistantMessage,
    InboundMessage,
    MessageCreated,
    MessageSend,
    WebSocketMessageType,
)
from pydantic import TypeAdapter, ValidationError


def test_message_send_validates_payload() -> None:
    adapter = TypeAdapter(InboundMessage)

    message = adapter.validate_python({"type": "message.send", "payload": {"content": "Hello"}})

    assert isinstance(message, MessageSend)
    assert message.type == WebSocketMessageType.MESSAGE_SEND
    assert message.payload.content == "Hello"


def test_message_send_rejects_blank_content() -> None:
    adapter = TypeAdapter(InboundMessage)

    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "message.send", "payload": {"content": ""}})


def test_outbound_message_created_serializes_to_json_shape() -> None:
    message_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    sender_id = uuid.uuid4()
    created_at = datetime.now(UTC)

    message = MessageCreated(
        payload={
            "id": message_id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "role": MessageRole.USER,
            "content": "Hello",
            "created_at": created_at,
        }
    )

    assert message.model_dump(mode="json") == {
        "type": "message.created",
        "payload": {
            "id": str(message_id),
            "conversation_id": str(conversation_id),
            "sender_id": str(sender_id),
            "role": "user",
            "content": "Hello",
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
        },
    }


def test_assistant_message_uses_assistant_type() -> None:
    message = AssistantMessage(
        payload={
            "id": uuid.uuid4(),
            "conversation_id": uuid.uuid4(),
            "content": "Hi",
            "created_at": datetime.now(UTC),
        }
    )

    assert message.type == WebSocketMessageType.ASSISTANT_MESSAGE
    assert message.payload.role == MessageRole.ASSISTANT
