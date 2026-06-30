"""Pydantic schemas for message endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict

from app.models.message import MessageRole
from app.schemas.common import AppBaseModel


class MessageResponse(AppBaseModel):
    """Message returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    role: MessageRole
    content: str
    created_at: datetime


class MessageListResponse(AppBaseModel):
    """Paginated message history response."""

    items: list[MessageResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        *,
        items: list[MessageResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> MessageListResponse:
        pages = max(1, -(-total // page_size))
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
