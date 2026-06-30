"""Database access for messages."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole


class MessageRepository:
    """
        Query wrapper for message persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        sender_id: uuid.UUID | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            role=role,
            content=content,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def list_by_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_conversation(self, conversation_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
