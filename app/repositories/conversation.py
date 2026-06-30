"""Database access for conversations."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:
    """
         Query wrapper for conversation.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, owner_id: uuid.UUID, title: str) -> Conversation:
        conversation = Conversation(owner_id=owner_id, title=title)
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def list_by_owner(
        self,
        *,
        owner_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_owner(self, owner_id: uuid.UUID) -> int:
        stmt = (
            select(func.count()).select_from(Conversation).where(Conversation.owner_id == owner_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update_title(self, *, conversation: Conversation, title: str) -> Conversation:
        conversation.title = title
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def delete(self, conversation: Conversation) -> None:
        await self.session.delete(conversation)
        await self.session.flush()

    async def exists_for_owner(self, *, conversation_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        stmt = select(
            exists().where(
                Conversation.id == conversation_id,
                Conversation.owner_id == owner_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
