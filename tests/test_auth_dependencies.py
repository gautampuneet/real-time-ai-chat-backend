"""Tests for authentication dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from app.config import Settings
from app.dependencies import get_current_user
from app.exceptions.errors import AuthenticationError
from app.security import create_access_token, create_refresh_token


@dataclass
class FakeUser:
    id: uuid.UUID
    is_active: bool = True


class FakeUserRepository:
    def __init__(self, _db: object) -> None:
        pass

    async def get_by_id(self, user_id: uuid.UUID) -> FakeUser | None:
        return USERS.get(user_id)


USERS: dict[uuid.UUID, FakeUser] = {}


@pytest.fixture(autouse=True)
def clear_users(monkeypatch: pytest.MonkeyPatch) -> None:
    USERS.clear()
    monkeypatch.setattr("app.dependencies.UserRepository", FakeUserRepository)


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret_key="test-secret-key-not-for-production")  # type: ignore[arg-type]


async def test_get_current_user_returns_active_user(settings: Settings) -> None:
    user = FakeUser(id=uuid.uuid4())
    USERS[user.id] = user
    token = create_access_token(user.id, settings)

    current_user = await get_current_user(token=token, db=object(), settings=settings)

    assert current_user is user


async def test_get_current_user_rejects_missing_token(settings: Settings) -> None:
    with pytest.raises(AuthenticationError, match="missing"):
        await get_current_user(token=None, db=object(), settings=settings)


async def test_get_current_user_rejects_refresh_token(settings: Settings) -> None:
    token = create_refresh_token(uuid.uuid4(), settings)

    with pytest.raises(AuthenticationError, match="Expected a 'access' token"):
        await get_current_user(token=token, db=object(), settings=settings)


async def test_get_current_user_rejects_missing_user(settings: Settings) -> None:
    token = create_access_token(uuid.uuid4(), settings)

    with pytest.raises(AuthenticationError, match="no longer exists"):
        await get_current_user(token=token, db=object(), settings=settings)


async def test_get_current_user_rejects_inactive_user(settings: Settings) -> None:
    user = FakeUser(id=uuid.uuid4(), is_active=False)
    USERS[user.id] = user
    token = create_access_token(user.id, settings)

    with pytest.raises(AuthenticationError, match="inactive"):
        await get_current_user(token=token, db=object(), settings=settings)
