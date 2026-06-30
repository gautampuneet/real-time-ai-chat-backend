"""Tests for authentication Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from pydantic import ValidationError


def test_user_register_request_validates_email_and_password() -> None:
    request = UserRegisterRequest(email="User@Example.com", password="strong-password")

    assert request.email == "User@example.com"
    assert request.password == "strong-password"


def test_user_register_request_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(email="not-an-email", password="strong-password")


def test_user_register_request_rejects_short_or_blank_password() -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(email="user@example.com", password="short")

    with pytest.raises(ValidationError):
        UserRegisterRequest(email="user@example.com", password=" " * 8)


def test_user_login_request_validates_basic_shape() -> None:
    request = UserLoginRequest(email="user@example.com", password="x")

    assert request.email == "user@example.com"
    assert request.password == "x"


def test_refresh_token_request_rejects_empty_token() -> None:
    with pytest.raises(ValidationError):
        RefreshTokenRequest(refresh_token="")


def test_token_response_defaults_to_bearer_type() -> None:
    response = TokenResponse(access_token="access", refresh_token="refresh")

    assert response.model_dump() == {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_type": "bearer",
    }


def test_user_response_uses_orm_attributes_without_password_hash() -> None:
    class UserLike:
        id = uuid.uuid4()
        email = "user@example.com"
        is_active = True
        created_at = datetime.now(UTC)
        password_hash = "must-not-leak"

    response = UserResponse.model_validate(UserLike())
    data = response.model_dump()

    assert data["id"] == UserLike.id
    assert data["email"] == UserLike.email
    assert data["is_active"] is True
    assert "password_hash" not in data
