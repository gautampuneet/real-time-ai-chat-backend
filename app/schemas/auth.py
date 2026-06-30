"""Pydantic schemas for authentication requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import AppBaseModel


class UserRegisterRequest(AppBaseModel):
    """Payload for creating a new user account."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_must_not_be_blank(cls, password: str) -> str:
        if not password.strip():
            raise ValueError("Password must not be blank")
        return password


class UserLoginRequest(AppBaseModel):
    """Payload for email/password login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(AppBaseModel):
    """Payload for refreshing an access token."""

    refresh_token: str = Field(min_length=1)


class TokenResponse(AppBaseModel):
    """JWT pair returned after registration or login."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105


class UserResponse(AppBaseModel):
    """Public user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_active: bool
    created_at: datetime
