"""
Security helpers
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypedDict, cast

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.hash import argon2

from app.config import Settings
from app.exceptions.errors import AuthenticationError

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TokenType = Literal["access", "refresh"]


class TokenPayload(TypedDict):
    """Validated claims present in every issued token."""

    sub: str
    type: TokenType
    exp: int
    iat: int


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Return an Argon2id hash of *plain_password*.

    The resulting string is self-contained (algorithm, parameters, and salt
    are all embedded) and safe to store directly in the database.
    """
    return cast(str, argon2.hash(plain_password))  # type: ignore[no-untyped-call]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` when *plain_password* matches *hashed_password*.

    Uses a constant-time comparison internally; safe against timing attacks.
    """
    try:
        return cast(bool, argon2.verify(plain_password, hashed_password))  # type: ignore[no-untyped-call]
    except ValueError:
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    """Return ``True`` if the stored hash was created with outdated parameters.

    Call this after a successful ``verify_password`` and, if ``True``,
    re-hash the plain-text password and persist the new hash.
    """
    return argon2.needs_update(hashed_password)


# ---------------------------------------------------------------------------
# Token helpers (internal)
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _build_token(
    user_id: uuid.UUID,
    token_type: TokenType,
    expire_delta: timedelta,
    settings: Settings,
) -> str:
    """Encode a signed JWT with the standard claims."""
    now = _utc_now()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


# ---------------------------------------------------------------------------
# Public token generation
# ---------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    """Return a signed JWT access token for *user_id*.

    Expiration is controlled by ``Settings.access_token_expire_minutes``.
    """
    return _build_token(
        user_id,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        settings,
    )


def create_refresh_token(user_id: uuid.UUID, settings: Settings) -> str:
    """Return a signed JWT refresh token for *user_id*.

    Expiration is controlled by ``Settings.refresh_token_expire_days``.
    """
    return _build_token(
        user_id,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
        settings,
    )


# ---------------------------------------------------------------------------
# Token decoding & validation
# ---------------------------------------------------------------------------


def decode_token(
    token: str,
    expected_type: TokenType,
    settings: Settings,
) -> TokenPayload:
    """Decode and validate *token*; return its claims as a :class:`TokenPayload`.

    Raises
    ------
    AuthenticationError
        If the token is malformed, expired, has an invalid signature, or its
        ``type`` claim does not match *expected_type*.
    """
    try:
        raw: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except JWTError as exc:
        raise AuthenticationError("Token is invalid or tampered") from exc

    token_type = _get_token_type(raw)
    if token_type != expected_type:
        raise AuthenticationError(f"Expected a {expected_type!r} token but received {token_type!r}")

    sub = _get_subject(raw)
    exp = _get_int_claim(raw, "exp")
    iat = _get_int_claim(raw, "iat")

    return TokenPayload(
        sub=sub,
        type=token_type,
        exp=exp,
        iat=iat,
    )


def _get_subject(payload: dict[str, Any]) -> str:
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthenticationError("Token is missing the 'sub' claim")
    return sub


def _get_token_type(payload: dict[str, Any]) -> TokenType:
    token_type = payload.get("type")
    if token_type not in ("access", "refresh"):
        raise AuthenticationError("Token has an invalid 'type' claim")
    return cast(TokenType, token_type)


def _get_int_claim(payload: dict[str, Any], claim: str) -> int:
    value = payload.get(claim)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuthenticationError(f"Token is missing the '{claim}' claim")
    return value


# ---------------------------------------------------------------------------
# User ID extraction helpers
# ---------------------------------------------------------------------------


def get_user_id_from_token(
    token: str,
    expected_type: TokenType,
    settings: Settings,
) -> uuid.UUID:
    """Decode *token* and return the authenticated user's UUID.

    Combines :func:`decode_token` and :func:`get_user_id_from_payload` for
    callers that only need the user ID and do not require the full payload.

    Raises
    ------
    AuthenticationError
        Propagated from :func:`decode_token`, or if ``sub`` is not a valid UUID.
    """
    payload = decode_token(token, expected_type, settings)
    return get_user_id_from_payload(payload)


def get_user_id_from_payload(payload: TokenPayload) -> uuid.UUID:
    """Extract and parse the user UUID from an already-decoded *payload*.

    Useful when the payload has already been validated (e.g. in a dependency
    that caches the decoded token) and only the user ID is needed downstream.

    Raises
    ------
    AuthenticationError
        If ``sub`` is absent or cannot be parsed as a UUID.
    """
    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError("Token payload is missing the 'sub' claim")
    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise AuthenticationError(f"Token 'sub' claim is not a valid UUID: {sub!r}") from exc
