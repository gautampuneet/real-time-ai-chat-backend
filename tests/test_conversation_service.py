"""Unit tests for conversation business logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from app.exceptions.errors import NotFoundError
from app.schemas.common import PaginationParams
from app.services.conversation import ConversationService


@dataclass
class FakeConversation:
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeConversationRepository:
    def __init__(self, _session: FakeSession) -> None:
        self.conversations: dict[uuid.UUID, FakeConversation] = {}
        self.last_limit: int | None = None
        self.last_offset: int | None = None

    async def create(self, *, owner_id: uuid.UUID, title: str) -> FakeConversation:
        conversation = FakeConversation(id=uuid.uuid4(), owner_id=owner_id, title=title)
        self.conversations[conversation.id] = conversation
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> FakeConversation | None:
        return self.conversations.get(conversation_id)

    async def list_by_owner(
        self,
        *,
        owner_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[FakeConversation]:
        self.last_limit = limit
        self.last_offset = offset
        return [item for item in self.conversations.values() if item.owner_id == owner_id]

    async def count_by_owner(self, owner_id: uuid.UUID) -> int:
        return len([item for item in self.conversations.values() if item.owner_id == owner_id])

    async def update_title(
        self,
        *,
        conversation: FakeConversation,
        title: str,
    ) -> FakeConversation:
        conversation.title = title
        return conversation

    async def delete(self, conversation: FakeConversation) -> None:
        self.conversations.pop(conversation.id, None)


@pytest.fixture
def service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ConversationService, FakeConversationRepository, FakeSession]:
    session = FakeSession()
    repository = FakeConversationRepository(session)
    monkeypatch.setattr("app.services.conversation.ConversationRepository", lambda _s: repository)
    return ConversationService(session), repository, session


async def test_create_conversation_commits(
    service: tuple[ConversationService, FakeConversationRepository, FakeSession],
) -> None:
    conversation_service, _repository, session = service
    owner_id = uuid.uuid4()

    conversation = await conversation_service.create_conversation(
        owner_id=owner_id, title="New chat"
    )

    assert conversation.owner_id == owner_id
    assert conversation.title == "New chat"
    assert session.commits == 1


async def test_list_conversations_uses_owner_and_pagination(
    service: tuple[ConversationService, FakeConversationRepository, FakeSession],
) -> None:
    conversation_service, repository, _session = service
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    await repository.create(owner_id=owner_id, title="Mine")
    await repository.create(owner_id=other_owner_id, title="Not mine")

    page = await conversation_service.list_conversations(
        owner_id=owner_id,
        pagination=PaginationParams(page=2, page_size=10),
    )

    assert [item.title for item in page.items] == ["Mine"]
    assert page.total == 1
    assert page.page == 2
    assert page.page_size == 10
    assert repository.last_limit == 10
    assert repository.last_offset == 10


async def test_rename_conversation_rejects_missing_or_unowned(
    service: tuple[ConversationService, FakeConversationRepository, FakeSession],
) -> None:
    conversation_service, repository, session = service
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    conversation = await repository.create(owner_id=other_owner_id, title="Nope")

    with pytest.raises(NotFoundError):
        await conversation_service.rename_conversation(
            conversation_id=conversation.id,
            owner_id=owner_id,
            title="Renamed",
        )

    assert conversation.title == "Nope"
    assert session.commits == 0


async def test_rename_and_delete_owned_conversation(
    service: tuple[ConversationService, FakeConversationRepository, FakeSession],
) -> None:
    conversation_service, repository, session = service
    owner_id = uuid.uuid4()
    conversation = await repository.create(owner_id=owner_id, title="Old")

    renamed = await conversation_service.rename_conversation(
        conversation_id=conversation.id,
        owner_id=owner_id,
        title="New",
    )
    await conversation_service.delete_conversation(
        conversation_id=conversation.id, owner_id=owner_id
    )

    assert renamed.title == "New"
    assert conversation.id not in repository.conversations
    assert session.commits == 2
