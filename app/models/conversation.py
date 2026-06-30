"""Conversation ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class Conversation(TimestampMixin, Base):
    """
        Chat Conversation model.
    """

    __tablename__ = "conversations"

    __table_args__ = (
        Index("ix_conversations_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner: Mapped[User] = relationship(
        "User",
        back_populates="conversations",
        lazy="raise",
    )
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id!r}, owner_id={self.owner_id!r}, title={self.title!r})"
