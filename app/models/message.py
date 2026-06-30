"""Message ORM model."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class MessageRole(StrEnum):
    """
    Allowed sender roles for chat messages.
    """

    USER = "user"
    ASSISTANT = "assistant"


class Message(TimestampMixin, Base):
    """
        Message model.
    """

    __tablename__ = "messages"

    __table_args__ = (
        Index("ix_messages_conversation_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="message_role",
            values_callable=lambda enum_cls: [role.value for role in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(
        "Conversation",
        back_populates="messages",
        lazy="raise",
    )
    sender: Mapped[User | None] = relationship(
        "User",
        back_populates="messages",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"Message(id={self.id!r}, conversation_id={self.conversation_id!r}, "
            f"sender_id={self.sender_id!r}, role={self.role!r})"
        )
