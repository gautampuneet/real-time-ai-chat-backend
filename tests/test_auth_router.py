"""Tests for authentication REST endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from app.config import Settings, get_settings
from app.database.session import get_db
from app.dependencies import get_current_user
from app.main import create_app
from app.services.auth import AuthTokens
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@dataclass
class FakeUser:
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: datetime


class FakeAuthService:
    def __init__(self, _db: Any, _settings: Settings) -> None:
        pass

    async def register_user(self, *, email: str, password: str) -> AuthTokens:
        assert email == "USER@example.com"
        assert password == "strong-password"
        return AuthTokens(access_token="registered-access", refresh_token="registered-refresh")

    async def login(self, *, email: str, password: str) -> AuthTokens:
        assert email == "user@example.com"
        assert password == "secret"
        return AuthTokens(access_token="login-access", refresh_token="login-refresh")

    async def refresh_access_token(self, refresh_token: str) -> str:
        assert refresh_token == "refresh-token"
        return "new-access"


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    test_app = create_app()
    monkeypatch.setattr("app.routers.auth.AuthService", FakeAuthService)

    async def override_get_db() -> AsyncGenerator[object, None]:
        yield object()

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_settings] = lambda: Settings(
        jwt_secret_key="test-secret-key-not-for-production"  # type: ignore[arg-type]
    )
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def test_register_returns_tokens(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "USER@example.com", "password": "strong-password"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "access_token": "registered-access",
        "refresh_token": "registered-refresh",
        "token_type": "bearer",
    }


async def test_login_returns_tokens(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "login-access",
        "refresh_token": "login-refresh",
        "token_type": "bearer",
    }


async def test_refresh_returns_new_access_token(client: AsyncClient) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": "refresh-token"})

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "new-access",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
    }


async def test_me_returns_current_user(app: FastAPI, client: AsyncClient) -> None:
    user = FakeUser(
        id=uuid.uuid4(),
        email="user@example.com",
        is_active=True,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_current_user] = lambda: user

    response = await client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["is_active"] is True
    assert "password_hash" not in body
