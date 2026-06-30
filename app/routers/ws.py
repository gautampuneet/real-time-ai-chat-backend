"""WebSocket chat endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import session as db_session
from app.exceptions.errors import AuthenticationError
from app.logging_config import get_logger
from app.repositories.conversation import ConversationRepository
from app.repositories.user import UserRepository
from app.security import get_user_id_from_token
from app.services.chat import ChatWebSocketService
from app.websocket.manager import websocket_manager
from app.websocket.pubsub import redis_websocket_pubsub

router = APIRouter(tags=["WebSocket"])
logger = get_logger(__name__)


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_websocket(websocket: WebSocket, conversation_id: uuid.UUID) -> None:
    token = websocket.query_params.get("token")
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    session_factory = db_session.AsyncSessionLocal
    if session_factory is None:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Database unavailable")
        return

    async with session_factory() as session:
        user_id = await _authenticate(websocket, token, session)
        if user_id is None:
            return

        if not await _owns_conversation(session, conversation_id, user_id):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Conversation not found",
            )
            return

    await websocket_manager.connect(conversation_id=conversation_id, websocket=websocket)
    try:
        await redis_websocket_pubsub.subscribe_conversation(conversation_id)
    except Exception as exc:
        await websocket_manager.disconnect(conversation_id=conversation_id, websocket=websocket)
        await redis_websocket_pubsub.unsubscribe_conversation(conversation_id, force=True)
        logger.error(
            "failed to subscribe websocket to Redis channel",
            conversation_id=str(conversation_id),
            user_id=str(user_id),
            exc_info=exc,
        )
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Message fan-out unavailable",
        )
        return

    logger.info(
        "websocket connected",
        conversation_id=str(conversation_id),
        user_id=str(user_id),
    )
    try:
        await ChatWebSocketService(
            session_factory=session_factory,
            publisher=redis_websocket_pubsub,
        ).run(
            websocket=websocket,
            conversation_id=conversation_id,
            user_id=user_id,
        )
    except WebSocketDisconnect:
        logger.info(
            "websocket disconnected",
            conversation_id=str(conversation_id),
            user_id=str(user_id),
        )
    finally:
        await websocket_manager.disconnect(
            conversation_id=conversation_id,
            websocket=websocket,
        )
        await redis_websocket_pubsub.unsubscribe_conversation(conversation_id)


async def _authenticate(
    websocket: WebSocket,
    token: str,
    session: AsyncSession,
) -> uuid.UUID | None:
    settings = get_settings()
    try:
        user_id = get_user_id_from_token(token, "access", settings)
    except AuthenticationError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return None

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return None

    return user.id


async def _owns_conversation(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    return await ConversationRepository(session).exists_for_owner(
        conversation_id=conversation_id,
        owner_id=user_id,
    )
