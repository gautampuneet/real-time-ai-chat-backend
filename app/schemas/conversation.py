"""Pydantic schemas for conversation endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import AppBaseModel


class ConversationCreateRequest(AppBaseModel):
    """Payload for creating a conversation."""

    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, title: str) -> str:
        if not title.strip():
            raise ValueError("Title must not be blank")
        return title


class ConversationUpdateRequest(AppBaseModel):
    """Payload for renaming a conversation."""

    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, title: str) -> str:
        if not title.strip():
            raise ValueError("Title must not be blank")
        return title


class ConversationResponse(AppBaseModel):
    """Conversation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(AppBaseModel):
    """Paginated conversation list response."""

    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        *,
        items: list[ConversationResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> ConversationListResponse:
        pages = max(1, -(-total // page_size))
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
