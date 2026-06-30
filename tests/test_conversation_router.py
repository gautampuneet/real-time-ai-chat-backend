"""Tests for conversation REST endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from app.database.session import get_db
from app.dependencies import get_current_user
from app.main import create_app
from app.models.message import MessageRole
from app.services.conversation import ConversationPage
from app.services.message import MessagePage
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@dataclass
class FakeUser:
    id: uuid.UUID


@dataclass
class FakeConversation:
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class FakeMessage:
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeConversationService:
    def __init__(self, _db: Any) -> None:
        pass

    async def create_conversation(self, *, owner_id: uuid.UUID, title: str) -> FakeConversation:
        assert owner_id == USER.id
        assert title == "New chat"
        return FakeConversation(id=uuid.uuid4(), owner_id=owner_id, title=title)

    async def list_conversations(self, *, owner_id: uuid.UUID, pagination: Any) -> ConversationPage:
        assert owner_id == USER.id
        assert pagination.page == 2
        conversation = FakeConversation(id=uuid.uuid4(), owner_id=owner_id, title="Chat")
        return ConversationPage(items=[conversation], total=1, page=2, page_size=20)

    async def rename_conversation(
        self,
        *,
        conversation_id: uuid.UUID,
        owner_id: uuid.UUID,
        title: str,
    ) -> FakeConversation:
        assert owner_id == USER.id
        assert title == "Renamed"
        return FakeConversation(id=conversation_id, owner_id=owner_id, title=title)

    async def delete_conversation(self, *, conversation_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        assert owner_id == USER.id
        assert isinstance(conversation_id, uuid.UUID)


class FakeMessageService:
    def __init__(self, _db: Any) -> None:
        pass

    async def list_conversation_messages(
        self,
        *,
        conversation_id: uuid.UUID,
        owner_id: uuid.UUID,
        pagination: Any,
    ) -> MessagePage:
        assert owner_id == USER.id
        assert pagination.page == 2
        messages = [
            FakeMessage(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                sender_id=USER.id,
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
        return MessagePage(items=messages, total=2, page=2, page_size=20)


USER = FakeUser(id=uuid.uuid4())


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    test_app = create_app()
    monkeypatch.setattr("app.routers.conversations.ConversationService", FakeConversationService)
    monkeypatch.setattr("app.routers.conversations.MessageService", FakeMessageService)

    async def override_get_db() -> AsyncGenerator[object, None]:
        yield object()

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = lambda: USER
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def test_create_conversation(client: AsyncClient) -> None:
    response = await client.post("/conversations", json={"title": "New chat"})

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New chat"
    assert body["owner_id"] == str(USER.id)


async def test_list_conversations(client: AsyncClient) -> None:
    response = await client.get("/conversations", params={"page": 2, "page_size": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 2
    assert body["items"][0]["title"] == "Chat"


async def test_rename_conversation(client: AsyncClient) -> None:
    conversation_id = uuid.uuid4()

    response = await client.patch(f"/conversations/{conversation_id}", json={"title": "Renamed"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(conversation_id)
    assert body["title"] == "Renamed"


async def test_delete_conversation(client: AsyncClient) -> None:
    response = await client.delete(f"/conversations/{uuid.uuid4()}")

    assert response.status_code == 204
    assert response.content == b""


async def test_list_conversation_messages(client: AsyncClient) -> None:
    conversation_id = uuid.uuid4()

    response = await client.get(
        f"/conversations/{conversation_id}/messages",
        params={"page": 2, "page_size": 20},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 2
    assert [message["content"] for message in body["items"]] == ["Hello", "Hi"]
    assert [message["role"] for message in body["items"]] == ["user", "assistant"]
