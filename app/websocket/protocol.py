"""WebSocket protocol models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from app.models.message import MessageRole
from app.schemas.common import AppBaseModel


class WebSocketMessageType(StrEnum):
    """Supported WebSocket message types."""

    MESSAGE_SEND = "message.send"
    MESSAGE_CREATED = "message.created"
    ASSISTANT_MESSAGE = "assistant.message"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class MessageSendPayload(AppBaseModel):
    """Client payload for sending a user message."""

    content: str = Field(min_length=1, max_length=16_000)


class MessageCreatedPayload(AppBaseModel):
    """Server payload for a persisted user message."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    role: Literal[MessageRole.USER] = MessageRole.USER
    content: str
    created_at: datetime


class AssistantMessagePayload(AppBaseModel):
    """Server payload for a persisted assistant message."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal[MessageRole.ASSISTANT] = MessageRole.ASSISTANT
    content: str
    created_at: datetime


class ErrorPayload(AppBaseModel):
    """Server payload for protocol or processing errors."""

    code: str
    message: str


class PingPayload(AppBaseModel):
    """Optional ping metadata."""

    nonce: str | None = None


class PongPayload(AppBaseModel):
    """Optional pong metadata."""

    nonce: str | None = None


class MessageSend(AppBaseModel):
    """Inbound client request to send a message."""

    type: Literal[WebSocketMessageType.MESSAGE_SEND] = WebSocketMessageType.MESSAGE_SEND
    payload: MessageSendPayload


class MessageCreated(AppBaseModel):
    """Outbound notification for a persisted user message."""

    type: Literal[WebSocketMessageType.MESSAGE_CREATED] = WebSocketMessageType.MESSAGE_CREATED
    payload: MessageCreatedPayload


class AssistantMessage(AppBaseModel):
    """Outbound notification for a persisted assistant message."""

    type: Literal[WebSocketMessageType.ASSISTANT_MESSAGE] = WebSocketMessageType.ASSISTANT_MESSAGE
    payload: AssistantMessagePayload


class ErrorMessage(AppBaseModel):
    """Outbound protocol error."""

    type: Literal[WebSocketMessageType.ERROR] = WebSocketMessageType.ERROR
    payload: ErrorPayload


class PingMessage(AppBaseModel):
    """Inbound or outbound ping."""

    type: Literal[WebSocketMessageType.PING] = WebSocketMessageType.PING
    payload: PingPayload = Field(default_factory=PingPayload)


class PongMessage(AppBaseModel):
    """Inbound or outbound pong."""

    type: Literal[WebSocketMessageType.PONG] = WebSocketMessageType.PONG
    payload: PongPayload = Field(default_factory=PongPayload)


InboundMessage = Annotated[
    MessageSend | PingMessage | PongMessage,
    Field(discriminator="type"),
]
OutboundMessage = MessageCreated | AssistantMessage | ErrorMessage | PingMessage | PongMessage
