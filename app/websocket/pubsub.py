"""Redis Pub/Sub fan-out for WebSocket messages."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import Field, TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.database.redis import get_redis_client
from app.logging_config import get_logger
from app.schemas.common import AppBaseModel
from app.websocket.manager import ConnectionManager, websocket_manager
from app.websocket.protocol import OutboundMessage

logger = get_logger(__name__)
outbound_adapter: TypeAdapter[OutboundMessage] = TypeAdapter(
    Annotated[OutboundMessage, Field(discriminator="type")]
)


@dataclass(slots=True)
class SubscriptionState:
    task: asyncio.Task[None]
    ready: asyncio.Event = field(default_factory=asyncio.Event)


def conversation_channel(conversation_id: uuid.UUID) -> str:
    """Return the Redis channel name for a conversation."""
    return f"chat:conversation:{conversation_id}"


class RedisWebSocketPubSub:
    """Publishes and subscribes WebSocket frames through Redis Pub/Sub."""

    def __init__(
        self,
        *,
        manager: ConnectionManager,
        redis_factory: Callable[[], Redis] = get_redis_client,
    ) -> None:
        self.manager = manager
        self.redis_factory = redis_factory
        self._subscriptions: dict[uuid.UUID, SubscriptionState] = {}
        self._lock = asyncio.Lock()
        self._started = False
        self._stopping = False

    async def start(self) -> None:
        async with self._lock:
            self._started = True
            self._stopping = False
        logger.info("Redis WebSocket Pub/Sub manager started")

    async def stop(self) -> None:
        async with self._lock:
            self._stopping = True
            states = list(self._subscriptions.values())
            self._subscriptions.clear()

        for state in states:
            state.task.cancel()
        if states:
            await asyncio.gather(*(state.task for state in states), return_exceptions=True)

        async with self._lock:
            self._started = False
        logger.info("Redis WebSocket Pub/Sub manager stopped")

    async def publish(
        self,
        *,
        conversation_id: uuid.UUID,
        message: AppBaseModel | Mapping[str, Any],
    ) -> None:
        redis = self.redis_factory()
        await redis.publish(conversation_channel(conversation_id), self._serialize(message))

    async def subscribe_conversation(self, conversation_id: uuid.UUID) -> None:
        async with self._lock:
            if self._stopping:
                return
            if not self._started:
                self._started = True
            state = self._subscriptions.get(conversation_id)
            if state is None or state.task.done():
                state = SubscriptionState(
                    task=asyncio.create_task(
                        self._subscription_loop(conversation_id),
                        name=f"redis-ws-subscription-{conversation_id}",
                    )
                )
                self._subscriptions[conversation_id] = state

        try:
            await asyncio.wait_for(state.ready.wait(), timeout=5.0)
        except TimeoutError as exc:
            await self.unsubscribe_conversation(conversation_id, force=True)
            raise RuntimeError("Timed out subscribing to Redis conversation channel") from exc

    async def unsubscribe_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        force: bool = False,
    ) -> None:
        async with self._lock:
            if not force and await self.manager.connection_count(conversation_id) > 0:
                return
            state = self._subscriptions.pop(conversation_id, None)

        if state is not None:
            state.task.cancel()
            with suppress(asyncio.CancelledError):
                await state.task

    async def active_subscription_count(self) -> int:
        async with self._lock:
            return len(self._subscriptions)

    async def _subscription_loop(self, conversation_id: uuid.UUID) -> None:
        channel = conversation_channel(conversation_id)
        backoff_seconds = 1.0

        while await self._is_subscribed(conversation_id):
            pubsub = None
            try:
                redis = self.redis_factory()
                pubsub = redis.pubsub()
                await pubsub.subscribe(channel)
                await self._mark_ready(conversation_id)
                logger.info(
                    "subscribed to Redis conversation channel",
                    conversation_id=str(conversation_id),
                )
                backoff_seconds = 1.0

                while await self._is_subscribed(conversation_id):
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message is None:
                        continue
                    await self._handle_message(conversation_id, message.get("data"))
            except asyncio.CancelledError:
                raise
            except (RedisError, OSError) as exc:
                await self._mark_not_ready(conversation_id)
                logger.error(
                    "Redis WebSocket subscription failed",
                    conversation_id=str(conversation_id),
                    exc_info=exc,
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30.0)
            except Exception as exc:
                await self._mark_not_ready(conversation_id)
                logger.exception(
                    "unexpected Redis WebSocket subscription failure",
                    conversation_id=str(conversation_id),
                    exc_info=exc,
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30.0)
            finally:
                if pubsub is not None:
                    with suppress(Exception):
                        await pubsub.unsubscribe(channel)
                        await pubsub.aclose()  # type: ignore[no-untyped-call]

    async def _mark_ready(self, conversation_id: uuid.UUID) -> None:
        async with self._lock:
            state = self._subscriptions.get(conversation_id)
            if state is not None:
                state.ready.set()

    async def _mark_not_ready(self, conversation_id: uuid.UUID) -> None:
        async with self._lock:
            state = self._subscriptions.get(conversation_id)
            if state is not None:
                state.ready.clear()

    async def _handle_message(self, conversation_id: uuid.UUID, raw_data: Any) -> None:
        try:
            data = self._decode(raw_data)
            message = outbound_adapter.validate_python(data)
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            logger.warning(
                "invalid Redis WebSocket payload",
                conversation_id=str(conversation_id),
                exc_info=exc,
            )
            return

        await self.manager.broadcast_to_conversation(
            conversation_id=conversation_id,
            message=message,
        )

    async def _is_subscribed(self, conversation_id: uuid.UUID) -> bool:
        async with self._lock:
            return conversation_id in self._subscriptions and not self._stopping

    @staticmethod
    def _serialize(message: AppBaseModel | Mapping[str, Any]) -> str:
        if isinstance(message, AppBaseModel):
            return message.model_dump_json()
        return json.dumps(message, default=str)

    @staticmethod
    def _decode(raw_data: Any) -> Any:
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        if isinstance(raw_data, str):
            return json.loads(raw_data)
        return raw_data


redis_websocket_pubsub = RedisWebSocketPubSub(manager=websocket_manager)
