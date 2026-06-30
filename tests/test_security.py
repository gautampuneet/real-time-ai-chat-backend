"""Unit tests for stateless security helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.config import Settings
from app.exceptions.errors import AuthenticationError
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_id_from_payload,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from jose import jwt


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret_key="test-secret-key-not-for-production",  # type: ignore[arg-type]
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )


def test_hash_and_verify_password() -> None:
    hashed_password = hash_password("correct horse battery staple")

    assert hashed_password != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed_password)
    assert not verify_password("wrong password", hashed_password)
    assert not verify_password("correct horse battery staple", "not-a-valid-hash")


def test_create_and_decode_access_token(settings: Settings) -> None:
    user_id = uuid.uuid4()

    token = create_access_token(user_id, settings)
    payload = decode_token(token, "access", settings)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]
    assert get_user_id_from_token(token, "access", settings) == user_id


def test_access_and_refresh_tokens_use_different_expiration(settings: Settings) -> None:
    user_id = uuid.uuid4()

    access_payload = decode_token(create_access_token(user_id, settings), "access", settings)
    refresh_payload = decode_token(create_refresh_token(user_id, settings), "refresh", settings)

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["exp"] > access_payload["exp"]


def test_decode_token_rejects_wrong_token_type(settings: Settings) -> None:
    token = create_access_token(uuid.uuid4(), settings)

    with pytest.raises(AuthenticationError, match="Expected a 'refresh' token"):
        decode_token(token, "refresh", settings)


def test_decode_token_rejects_missing_required_claim(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": int(now.timestamp()),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AuthenticationError, match="'exp' claim"):
        decode_token(token, "access", settings)


def test_decode_token_rejects_expired_token(settings: Settings) -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": int((now - timedelta(minutes=10)).timestamp()),
            "exp": int((now - timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AuthenticationError, match="expired"):
        decode_token(token, "access", settings)


def test_get_user_id_from_payload_rejects_invalid_uuid(settings: Settings) -> None:
    token = create_access_token(uuid.uuid4(), settings)
    payload = decode_token(token, "access", settings)
    payload["sub"] = "not-a-uuid"

    with pytest.raises(AuthenticationError, match="not a valid UUID"):
        get_user_id_from_payload(payload)
