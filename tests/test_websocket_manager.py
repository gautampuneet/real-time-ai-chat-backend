"""Tests for the in-memory WebSocket connection manager."""

from __future__ import annotations

import uuid
from typing import Any

from app.websocket.manager import ConnectionManager
from app.websocket.protocol import ErrorMessage, ErrorPayload


class FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.accepted = False
        self.closed = False
        self.sent: list[dict[str, Any]] = []
        self.fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.fail_send:
            raise RuntimeError("socket is closed")
        self.sent.append(payload)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason
        self.closed = True


async def test_connect_and_disconnect_tracks_counts() -> None:
    manager = ConnectionManager()
    conversation_id = uuid.uuid4()
    websocket = FakeWebSocket()

    await manager.connect(conversation_id=conversation_id, websocket=websocket)  # type: ignore[arg-type]

    assert websocket.accepted
    assert await manager.connection_count(conversation_id) == 1
    assert await manager.connection_count() == 1

    await manager.disconnect(conversation_id=conversation_id, websocket=websocket)  # type: ignore[arg-type]

    assert await manager.connection_count(conversation_id) == 0
    assert await manager.connection_count() == 0


async def test_broadcast_sends_json_payload_and_removes_failed_connections() -> None:
    manager = ConnectionManager()
    conversation_id = uuid.uuid4()
    healthy = FakeWebSocket()
    failed = FakeWebSocket(fail_send=True)
    message = ErrorMessage(payload=ErrorPayload(code="bad_request", message="Nope"))

    await manager.connect(conversation_id=conversation_id, websocket=healthy)  # type: ignore[arg-type]
    await manager.connect(conversation_id=conversation_id, websocket=failed)  # type: ignore[arg-type]

    await manager.broadcast_to_conversation(conversation_id=conversation_id, message=message)

    assert healthy.sent == [
        {"type": "error", "payload": {"code": "bad_request", "message": "Nope"}}
    ]
    assert await manager.connection_count(conversation_id) == 1


async def test_close_conversation_connections_closes_and_clears() -> None:
    manager = ConnectionManager()
    conversation_id = uuid.uuid4()
    first = FakeWebSocket()
    second = FakeWebSocket()

    await manager.connect(conversation_id=conversation_id, websocket=first)  # type: ignore[arg-type]
    await manager.connect(conversation_id=conversation_id, websocket=second)  # type: ignore[arg-type]

    await manager.close_conversation_connections(conversation_id=conversation_id)

    assert first.closed
    assert second.closed
    assert await manager.connection_count(conversation_id) == 0
