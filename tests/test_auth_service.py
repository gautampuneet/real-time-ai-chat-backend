"""Unit tests for authentication business logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from app.config import Settings
from app.exceptions.errors import AlreadyExistsError, AuthenticationError
from app.security import create_refresh_token, decode_token, hash_password, verify_password
from app.services.auth import AuthService


@dataclass
class FakeUser:
    id: uuid.UUID
    email: str
    password_hash: str
    is_active: bool = True


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeUserRepository:
    def __init__(self, _session: Any) -> None:
        self.users_by_email: dict[str, FakeUser] = {}
        self.users_by_id: dict[uuid.UUID, FakeUser] = {}
        self.created_password_hash: str | None = None

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        is_active: bool = True,
        is_superuser: bool = False,
    ) -> FakeUser:
        del is_superuser
        user = FakeUser(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=is_active,
        )
        self.created_password_hash = password_hash
        self.users_by_email[email] = user
        self.users_by_id[user.id] = user
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> FakeUser | None:
        return self.users_by_id.get(user_id)

    async def get_by_email(self, email: str) -> FakeUser | None:
        return self.users_by_email.get(email)

    async def exists_by_email(self, email: str) -> bool:
        return email in self.users_by_email


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret_key="test-secret-key-not-for-production",  # type: ignore[arg-type]
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def auth_service(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> tuple[AuthService, FakeUserRepository, FakeSession]:
    session = FakeSession()
    repository = FakeUserRepository(session)
    monkeypatch.setattr("app.services.auth.UserRepository", lambda _session: repository)
    return AuthService(session, settings), repository, session


async def test_register_user_hashes_password_and_returns_tokens(
    auth_service: tuple[AuthService, FakeUserRepository, FakeSession],
    settings: Settings,
) -> None:
    service, repository, session = auth_service

    tokens = await service.register_user(email="USER@Example.COM ", password="secret-password")

    assert session.commits == 1
    assert await repository.exists_by_email("user@example.com")
    assert repository.created_password_hash is not None
    assert repository.created_password_hash != "secret-password"
    assert verify_password("secret-password", repository.created_password_hash)
    assert decode_token(tokens.access_token, "access", settings)["type"] == "access"
    assert decode_token(tokens.refresh_token, "refresh", settings)["type"] == "refresh"


async def test_register_user_rejects_duplicate_email(
    auth_service: tuple[AuthService, FakeUserRepository, FakeSession],
) -> None:
    service, repository, session = auth_service
    await repository.create(email="taken@example.com", password_hash=hash_password("secret"))

    with pytest.raises(AlreadyExistsError):
        await service.register_user(email="TAKEN@example.com", password="new-secret")

    assert session.commits == 0


async def test_login_rejects_invalid_credentials(
    auth_service: tuple[AuthService, FakeUserRepository, FakeSession],
) -> None:
    service, repository, _session = auth_service
    await repository.create(email="user@example.com", password_hash=hash_password("secret"))

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await service.login(email="user@example.com", password="wrong")


async def test_login_rejects_inactive_user(
    auth_service: tuple[AuthService, FakeUserRepository, FakeSession],
) -> None:
    service, repository, _session = auth_service
    await repository.create(
        email="user@example.com",
        password_hash=hash_password("secret"),
        is_active=False,
    )

    with pytest.raises(AuthenticationError, match="inactive"):
        await service.login(email="user@example.com", password="secret")


async def test_refresh_access_token_requires_active_existing_user(
    auth_service: tuple[AuthService, FakeUserRepository, FakeSession],
    settings: Settings,
) -> None:
    service, repository, _session = auth_service
    user = await repository.create(email="user@example.com", password_hash=hash_password("secret"))
    refresh_token = create_refresh_token(user.id, settings)

    access_token = await service.refresh_access_token(refresh_token)

    payload = decode_token(access_token, "access", settings)
    assert payload["sub"] == str(user.id)


async def test_refresh_access_token_rejects_missing_user(
    auth_service: tuple[AuthService, FakeUserRepository, FakeSession],
    settings: Settings,
) -> None:
    service, _repository, _session = auth_service
    refresh_token = create_refresh_token(uuid.uuid4(), settings)

    with pytest.raises(AuthenticationError, match="no longer exists"):
        await service.refresh_access_token(refresh_token)
