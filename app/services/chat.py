"""WebSocket chat flow orchestration."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import WebSocket
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.logging_config import get_logger
from app.models.message import Message, MessageRole
from app.repositories.message import MessageRepository
from app.schemas.common import AppBaseModel
from app.websocket.protocol import (
    AssistantMessage,
    AssistantMessagePayload,
    ErrorMessage,
    ErrorPayload,
    InboundMessage,
    MessageCreated,
    MessageCreatedPayload,
    MessageSend,
    PingMessage,
    PongMessage,
    PongPayload,
)

logger = get_logger(__name__)
inbound_adapter: TypeAdapter[InboundMessage] = TypeAdapter(InboundMessage)


class WebSocketFramePublisher(Protocol):
    async def publish(
        self,
        *,
        conversation_id: uuid.UUID,
        message: AppBaseModel | Mapping[str, Any],
    ) -> None: ...


class ChatWebSocketService:
    """Handles the local WebSocket chat message loop."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: WebSocketFramePublisher,
    ) -> None:
        self.session_factory = session_factory
        self.publisher = publisher

    async def run(
        self,
        *,
        websocket: WebSocket,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        while True:
            try:
                raw_message = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except ValueError:
                logger.info("malformed websocket JSON", conversation_id=str(conversation_id))
                await self._send_error(
                    websocket,
                    code="invalid_json",
                    message="Message must be valid JSON",
                )
                continue

            try:
                inbound = inbound_adapter.validate_python(raw_message)
            except ValidationError as exc:
                logger.info("invalid websocket frame", conversation_id=str(conversation_id))
                await self._send_error(
                    websocket,
                    code="invalid_message",
                    message=self._validation_message(exc),
                )
                continue

            if isinstance(inbound, MessageSend):
                await self._handle_message_send(
                    websocket=websocket,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message=inbound,
                )
            elif isinstance(inbound, PingMessage):
                await websocket.send_json(
                    PongMessage(payload=PongPayload(nonce=inbound.payload.nonce)).model_dump(
                        mode="json"
                    )
                )
            else:
                await self._send_error(
                    websocket,
                    code="unsupported_message",
                    message="Unsupported WebSocket message type",
                )

    async def _handle_message_send(
        self,
        *,
        websocket: WebSocket,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        message: MessageSend,
    ) -> None:
        user_message: Message
        try:
            async with self.session_factory() as session:
                try:
                    messages = MessageRepository(session)
                    user_message = await messages.create(
                        conversation_id=conversation_id,
                        sender_id=user_id,
                        role=MessageRole.USER,
                        content=message.payload.content,
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception as exc:
            logger.error(
                "failed to persist user websocket message",
                conversation_id=str(conversation_id),
                user_id=str(user_id),
                exc_info=exc,
            )
            await self._send_error(
                websocket,
                code="message_processing_failed",
                message="Unable to process message",
            )
            return

        user_frame = self._message_created(user_message)
        if not await self._publish_frame(
            websocket=websocket,
            conversation_id=conversation_id,
            message=user_frame,
        ):
            return

        assistant_message: Message
        try:
            async with self.session_factory() as session:
                try:
                    messages = MessageRepository(session)
                    assistant_message = await messages.create(
                        conversation_id=conversation_id,
                        sender_id=None,
                        role=MessageRole.ASSISTANT,
                        content=self._mock_assistant_reply(message.payload.content),
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception as exc:
            logger.error(
                "failed to persist assistant websocket message",
                conversation_id=str(conversation_id),
                user_id=str(user_id),
                exc_info=exc,
            )
            await self._send_error(
                websocket,
                code="message_processing_failed",
                message="Unable to process message",
            )
            return

        await self._publish_frame(
            websocket=websocket,
            conversation_id=conversation_id,
            message=self._assistant_message(assistant_message),
        )

    async def _publish_frame(
        self,
        *,
        websocket: WebSocket,
        conversation_id: uuid.UUID,
        message: AppBaseModel | Mapping[str, Any],
    ) -> bool:
        try:
            await self.publisher.publish(
                conversation_id=conversation_id,
                message=message,
            )
            return True
        except Exception as exc:
            message_id = self._message_id(message)
            logger.error(
                "failed to publish websocket frame to Redis",
                conversation_id=str(conversation_id),
                message_id=message_id,
                exc_info=exc,
            )
            await self._send_error(
                websocket,
                code="message_publish_failed",
                message="Message was saved but could not be delivered",
            )
            return False

    @staticmethod
    def _message_created(message: Message) -> MessageCreated:
        if message.sender_id is None:
            raise ValueError("User message must have a sender_id")
        return MessageCreated(
            payload=MessageCreatedPayload(
                id=message.id,
                conversation_id=message.conversation_id,
                sender_id=message.sender_id,
                role=MessageRole.USER,
                content=message.content,
                created_at=message.created_at,
            )
        )

    @staticmethod
    def _assistant_message(message: Message) -> AssistantMessage:
        return AssistantMessage(
            payload=AssistantMessagePayload(
                id=message.id,
                conversation_id=message.conversation_id,
                role=MessageRole.ASSISTANT,
                content=message.content,
                created_at=message.created_at,
            )
        )

    @staticmethod
    def _mock_assistant_reply(user_content: str) -> str:
        return f"Mock AI response: {user_content}"

    @staticmethod
    def _message_id(message: AppBaseModel | Mapping[str, Any]) -> str | None:
        payload: Any
        if isinstance(message, AppBaseModel):
            payload = message.model_dump(mode="json").get("payload")
        else:
            payload = message.get("payload")
        if isinstance(payload, dict):
            message_id = payload.get("id")
            if message_id is not None:
                return str(message_id)
        return None

    @staticmethod
    async def _send_error(websocket: WebSocket, *, code: str, message: str) -> None:
        await websocket.send_json(
            ErrorMessage(payload=ErrorPayload(code=code, message=message)).model_dump(mode="json")
        )

    @staticmethod
    def _validation_message(exc: ValidationError) -> str:
        first_error = exc.errors()[0]
        return str(first_error.get("msg", "Invalid WebSocket message"))
