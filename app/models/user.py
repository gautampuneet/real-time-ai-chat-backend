"""User ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message


class User(TimestampMixin, Base):
    """
        User ORM model.
    """

    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_email_active", "email", postgresql_where="is_active = true"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation",
        back_populates="owner",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="sender",
        lazy="raise",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r}, is_active={self.is_active!r})"
