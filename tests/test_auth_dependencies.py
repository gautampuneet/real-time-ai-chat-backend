"""Tests for authentication dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from app.config import Settings, get_settings
from app.database.session import get_db
from app.dependencies import get_current_user
from app.exceptions.errors import AuthenticationError
from app.security import create_access_token, create_refresh_token
from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient


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


def bearer_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


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

    current_user = await get_current_user(
        credentials=bearer_credentials(token),
        db=object(),
        settings=settings,
    )

    assert current_user is user


async def test_get_current_user_rejects_missing_token(settings: Settings) -> None:
    with pytest.raises(AuthenticationError, match="missing"):
        await get_current_user(credentials=None, db=object(), settings=settings)


async def test_get_current_user_rejects_non_bearer_scheme(settings: Settings) -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="token")

    with pytest.raises(AuthenticationError, match="Bearer"):
        await get_current_user(credentials=credentials, db=object(), settings=settings)


async def test_get_current_user_rejects_refresh_token(settings: Settings) -> None:
    token = create_refresh_token(uuid.uuid4(), settings)

    with pytest.raises(AuthenticationError, match="Expected a 'access' token"):
        await get_current_user(
            credentials=bearer_credentials(token),
            db=object(),
            settings=settings,
        )


async def test_get_current_user_rejects_missing_user(settings: Settings) -> None:
    token = create_access_token(uuid.uuid4(), settings)

    with pytest.raises(AuthenticationError, match="no longer exists"):
        await get_current_user(
            credentials=bearer_credentials(token),
            db=object(),
            settings=settings,
        )


async def test_get_current_user_rejects_inactive_user(settings: Settings) -> None:
    user = FakeUser(id=uuid.uuid4(), is_active=False)
    USERS[user.id] = user
    token = create_access_token(user.id, settings)

    with pytest.raises(AuthenticationError, match="inactive"):
        await get_current_user(
            credentials=bearer_credentials(token),
            db=object(),
            settings=settings,
        )


async def test_protected_endpoint_accepts_bearer_access_token(settings: Settings) -> None:
    app = FastAPI()
    user = FakeUser(id=uuid.uuid4())
    USERS[user.id] = user
    token = create_access_token(user.id, settings)

    async def override_get_db() -> object:
        return object()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/protected")
    async def protected(current_user: FakeUser = Depends(get_current_user)) -> dict[str, str]:
        return {"id": str(current_user.id)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id)}


def test_openapi_uses_http_bearer_scheme() -> None:
    app = FastAPI()

    @app.get("/protected")
    async def protected(_current_user: FakeUser = Depends(get_current_user)) -> dict[str, str]:
        return {"ok": "true"}

    schema = app.openapi()

    assert schema["components"]["securitySchemes"] == {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
        }
    }
    assert schema["paths"]["/protected"]["get"]["security"] == [{"HTTPBearer": []}]
