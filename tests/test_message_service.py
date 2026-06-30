"""Unit tests for message history business logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from app.exceptions.errors import NotFoundError
from app.models.message import MessageRole
from app.schemas.common import PaginationParams
from app.services.message import MessageService


@dataclass
class FakeMessage:
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeConversationRepository:
    def __init__(self, _session: object) -> None:
        self.owned_conversations: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def exists_for_owner(self, *, conversation_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
        return (conversation_id, owner_id) in self.owned_conversations


class FakeMessageRepository:
    def __init__(self, _session: object) -> None:
        self.messages: list[FakeMessage] = []
        self.last_limit: int | None = None
        self.last_offset: int | None = None

    async def list_by_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[FakeMessage]:
        self.last_limit = limit
        self.last_offset = offset
        return [message for message in self.messages if message.conversation_id == conversation_id]

    async def count_by_conversation(self, conversation_id: uuid.UUID) -> int:
        return sum(1 for message in self.messages if message.conversation_id == conversation_id)


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MessageService, FakeConversationRepository, FakeMessageRepository]:
    conversation_repository = FakeConversationRepository(object())
    message_repository = FakeMessageRepository(object())
    monkeypatch.setattr(
        "app.services.message.ConversationRepository",
        lambda _session: conversation_repository,
    )
    monkeypatch.setattr(
        "app.services.message.MessageRepository",
        lambda _session: message_repository,
    )
    return MessageService(object()), conversation_repository, message_repository


async def test_list_conversation_messages_requires_owned_conversation(
    service: tuple[MessageService, FakeConversationRepository, FakeMessageRepository],
) -> None:
    message_service, _conversation_repository, _message_repository = service

    with pytest.raises(NotFoundError):
        await message_service.list_conversation_messages(
            conversation_id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
            pagination=PaginationParams(),
        )


async def test_list_conversation_messages_returns_paginated_messages(
    service: tuple[MessageService, FakeConversationRepository, FakeMessageRepository],
) -> None:
    message_service, conversation_repository, message_repository = service
    owner_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    conversation_repository.owned_conversations.add((conversation_id, owner_id))
    message_repository.messages.extend(
        [
            FakeMessage(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                sender_id=owner_id,
                role=MessageRole.USER,
                content="Hello",
            ),
            FakeMessage(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                sender_id=None,
                role=MessageRole.ASSISTANT,
                content="Hi",
            ),
        ]
    )

    page = await message_service.list_conversation_messages(
        conversation_id=conversation_id,
        owner_id=owner_id,
        pagination=PaginationParams(page=2, page_size=10),
    )

    assert [message.content for message in page.items] == ["Hello", "Hi"]
    assert page.total == 2
    assert page.page == 2
    assert page.page_size == 10
    assert message_repository.last_limit == 10
    assert message_repository.last_offset == 10
