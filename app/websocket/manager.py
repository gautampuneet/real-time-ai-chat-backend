"""In-memory WebSocket connection manager."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.schemas.common import AppBaseModel


class ConnectionManager:
    """Tracks active local WebSocket connections by conversation."""

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, *, conversation_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[conversation_id].add(websocket)

    async def disconnect(self, *, conversation_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._remove_connection(conversation_id, websocket)

    async def broadcast_to_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        message: AppBaseModel | Mapping[str, Any],
    ) -> None:
        payload = self._json_payload(message)
        async with self._lock:
            connections = list(self._connections.get(conversation_id, set()))

        failed: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except (RuntimeError, WebSocketDisconnect, OSError):
                failed.append(websocket)

        if failed:
            async with self._lock:
                for websocket in failed:
                    self._remove_connection(conversation_id, websocket)

    async def close_conversation_connections(
        self,
        *,
        conversation_id: uuid.UUID,
        code: int = 1000,
        reason: str | None = None,
    ) -> None:
        async with self._lock:
            connections = list(self._connections.pop(conversation_id, set()))

        for websocket in connections:
            with suppress(RuntimeError, WebSocketDisconnect, OSError):
                await websocket.close(code=code, reason=reason)

    async def connection_count(self, conversation_id: uuid.UUID | None = None) -> int:
        async with self._lock:
            if conversation_id is not None:
                return len(self._connections.get(conversation_id, set()))
            return sum(len(connections) for connections in self._connections.values())

    def _remove_connection(self, conversation_id: uuid.UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(conversation_id)
        if connections is None:
            return

        connections.discard(websocket)
        if not connections:
            self._connections.pop(conversation_id, None)

    @staticmethod
    def _json_payload(message: AppBaseModel | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(message, AppBaseModel):
            return message.model_dump(mode="json")
        return dict(message)


websocket_manager = ConnectionManager()
