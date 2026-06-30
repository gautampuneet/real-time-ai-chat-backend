"""Authentication business logic."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.exceptions.errors import AlreadyExistsError, AuthenticationError
from app.repositories.user import UserRepository
from app.security import (
    create_access_token,
    create_refresh_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)
from app.services.base import BaseService


@dataclass(frozen=True, slots=True)
class AuthTokens:
    """Access and refresh tokens returned after successful authentication."""

    access_token: str
    refresh_token: str


class AuthService(BaseService):
    """Business logic for registration and token-based authentication."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        super().__init__(session)
        self.settings = settings
        self.users = UserRepository(session)

    async def register_user(self, *, email: str, password: str) -> AuthTokens:
        normalized_email = self._normalize_email(email)
        if await self.users.exists_by_email(normalized_email):
            raise AlreadyExistsError("user", "email", normalized_email)

        try:
            user = await self.users.create(
                email=normalized_email,
                password_hash=hash_password(password),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AlreadyExistsError("user", "email", normalized_email) from exc
        return self._issue_tokens(user.id)

    async def login(self, *, email: str, password: str) -> AuthTokens:
        user = await self.users.get_by_email(self._normalize_email(email))
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        return self._issue_tokens(user.id)

    async def refresh_access_token(self, refresh_token: str) -> str:
        user_id = get_user_id_from_token(refresh_token, "refresh", self.settings)
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("Token subject no longer exists")

        if not user.is_active:
            raise AuthenticationError("User account is inactive")

        return create_access_token(user.id, self.settings)

    def _issue_tokens(self, user_id: UUID) -> AuthTokens:
        return AuthTokens(
            access_token=create_access_token(user_id, self.settings),
            refresh_token=create_refresh_token(user_id, self.settings),
        )

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()
