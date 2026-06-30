"""Conversation business logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import NotFoundError
from app.models.conversation import Conversation
from app.repositories.conversation import ConversationRepository
from app.schemas.common import PaginationParams
from app.services.base import BaseService


@dataclass(frozen=True, slots=True)
class ConversationPage:
    """Paginated conversation result."""

    items: list[Conversation]
    total: int
    page: int
    page_size: int


class ConversationService(BaseService):
    """Business logic for user-owned conversations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.conversations = ConversationRepository(session)

    async def create_conversation(self, *, owner_id: uuid.UUID, title: str) -> Conversation:
        conversation = await self.conversations.create(owner_id=owner_id, title=title)
        await self.session.commit()
        return conversation

    async def list_conversations(
        self,
        *,
        owner_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> ConversationPage:
        items = await self.conversations.list_by_owner(
            owner_id=owner_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        total = await self.conversations.count_by_owner(owner_id)
        return ConversationPage(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    async def rename_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        owner_id: uuid.UUID,
        title: str,
    ) -> Conversation:
        conversation = await self._get_owned_conversation(conversation_id, owner_id)
        updated = await self.conversations.update_title(conversation=conversation, title=title)
        await self.session.commit()
        return updated

    async def delete_conversation(self, *, conversation_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        conversation = await self._get_owned_conversation(conversation_id, owner_id)
        await self.conversations.delete(conversation)
        await self.session.commit()

    async def _get_owned_conversation(
        self,
        conversation_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Conversation:
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise NotFoundError("conversation", str(conversation_id))
        return conversation
