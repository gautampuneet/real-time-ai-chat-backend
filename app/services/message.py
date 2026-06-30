"""Message business logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import NotFoundError
from app.models.message import Message
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.schemas.common import PaginationParams
from app.services.base import BaseService


@dataclass(frozen=True, slots=True)
class MessagePage:
    """Paginated message result."""

    items: list[Message]
    total: int
    page: int
    page_size: int


class MessageService(BaseService):
    """Business logic for message history reads."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def list_conversation_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        owner_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> MessagePage:
        exists = await self.conversations.exists_for_owner(
            conversation_id=conversation_id,
            owner_id=owner_id,
        )
        if not exists:
            raise NotFoundError("conversation", str(conversation_id))

        items = await self.messages.list_by_conversation(
            conversation_id=conversation_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        total = await self.messages.count_by_conversation(conversation_id)
        return MessagePage(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
