"""Tests for WebSocket chat flow orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from app.models.message import MessageRole
from app.services.chat import ChatWebSocketService
from app.websocket.protocol import MessageSend, MessageSendPayload
from starlette.websockets import WebSocketDisconnect


@dataclass
class FakeMessage:
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeMessageRepository:
    def __init__(self, _session: FakeSession) -> None:
        self.created: list[FakeMessage] = []
        self.fail_create = False

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        sender_id: uuid.UUID | None = None,
    ) -> FakeMessage:
        if self.fail_create:
            raise RuntimeError("database failed")
        message = FakeMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_id=sender_id,
            role=role,
            content=content,
        )
        self.created.append(message)
        return message


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[uuid.UUID, dict[str, Any]]] = []
        self.fail_publish = False

    async def publish(self, *, conversation_id: uuid.UUID, message: Any) -> None:
        if self.fail_publish:
            raise RuntimeError("redis failed")
        self.published.append((conversation_id, message.model_dump(mode="json")))


class FakeWebSocket:
    def __init__(self, incoming: list[dict[str, Any]]) -> None:
        self.incoming = incoming
        self.sent: list[dict[str, Any]] = []

    async def receive_json(self) -> dict[str, Any]:
        if not self.incoming:
            raise WebSocketDisconnect()
        return self.incoming.pop(0)

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ChatWebSocketService, FakeSession, FakeMessageRepository, FakePublisher]:
    session = FakeSession()
    repository = FakeMessageRepository(session)
    publisher = FakePublisher()
    monkeypatch.setattr("app.services.chat.MessageRepository", lambda _session: repository)
    chat_service = ChatWebSocketService(
        session_factory=lambda: session,  # type: ignore[arg-type]
        publisher=publisher,
    )
    return chat_service, session, repository, publisher


async def test_run_responds_to_ping(
    service: tuple[ChatWebSocketService, FakeSession, FakeMessageRepository, FakePublisher],
) -> None:
    chat_service, _session, _repository, _publisher = service
    websocket = FakeWebSocket([{"type": "ping", "payload": {"nonce": "abc"}}])

    with pytest.raises(WebSocketDisconnect):
        await chat_service.run(
            websocket=websocket,  # type: ignore[arg-type]
            conversation_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

    assert websocket.sent == [{"type": "pong", "payload": {"nonce": "abc"}}]


async def test_run_sends_error_for_invalid_frame(
    service: tuple[ChatWebSocketService, FakeSession, FakeMessageRepository, FakePublisher],
) -> None:
    chat_service, _session, _repository, _publisher = service
    websocket = FakeWebSocket([{"type": "message.send", "payload": {"content": ""}}])

    with pytest.raises(WebSocketDisconnect):
        await chat_service.run(
            websocket=websocket,  # type: ignore[arg-type]
            conversation_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

    assert websocket.sent[0]["type"] == "error"
    assert websocket.sent[0]["payload"]["code"] == "invalid_message"


async def test_message_send_persists_and_publishes_user_and_assistant_messages(
    service: tuple[ChatWebSocketService, FakeSession, FakeMessageRepository, FakePublisher],
) -> None:
    chat_service, session, repository, publisher = service
    conversation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    websocket = FakeWebSocket([])

    await chat_service._handle_message_send(
        websocket=websocket,  # type: ignore[arg-type]
        conversation_id=conversation_id,
        user_id=user_id,
        message=MessageSend(payload=MessageSendPayload(content="Hello")),
    )

    assert session.commits == 2
    assert [message.role for message in repository.created] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    assert [published[1]["type"] for published in publisher.published] == [
        "message.created",
        "assistant.message",
    ]
    assert publisher.published[1][1]["payload"]["content"] == "Mock AI response: Hello"


async def test_message_send_rolls_back_and_sends_error_on_database_failure(
    service: tuple[ChatWebSocketService, FakeSession, FakeMessageRepository, FakePublisher],
) -> None:
    chat_service, session, repository, publisher = service
    repository.fail_create = True
    websocket = FakeWebSocket([])

    await chat_service._handle_message_send(
        websocket=websocket,  # type: ignore[arg-type]
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        message=MessageSend(payload=MessageSendPayload(content="Hello")),
    )

    assert session.rollbacks == 1
    assert publisher.published == []
    assert websocket.sent[0]["type"] == "error"
    assert websocket.sent[0]["payload"]["code"] == "message_processing_failed"


async def test_message_send_does_not_rollback_when_redis_publish_fails(
    service: tuple[ChatWebSocketService, FakeSession, FakeMessageRepository, FakePublisher],
) -> None:
    chat_service, session, repository, publisher = service
    publisher.fail_publish = True
    websocket = FakeWebSocket([])

    await chat_service._handle_message_send(
        websocket=websocket,  # type: ignore[arg-type]
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        message=MessageSend(payload=MessageSendPayload(content="Hello")),
    )

    assert session.commits == 1
    assert session.rollbacks == 0
    assert len(repository.created) == 1
    assert websocket.sent[0]["type"] == "error"
    assert websocket.sent[0]["payload"]["code"] == "message_publish_failed"
