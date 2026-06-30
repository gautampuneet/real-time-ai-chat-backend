"""
Central module that re-exports all injectable dependencies and provides
higher-level composed dependencies (e.g., current authenticated user).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database.redis import get_redis
from app.database.session import get_db
from app.exceptions.errors import AuthenticationError
from app.models.user import User
from app.repositories.user import UserRepository
from app.security import get_user_id_from_token

# ── Primitive dependencies ────────────────────────────────────────────────────

DatabaseDep = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Auth dependencies ─────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DatabaseDep,
    settings: SettingsDep,
) -> User:
    """Return the active authenticated user for a valid Bearer access token."""
    if token is None:
        raise AuthenticationError("Authentication token is missing")

    user_id = get_user_id_from_token(token, "access", settings)
    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("Token subject no longer exists")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = CurrentUser


# ── Pagination dependency ─────────────────────────────────────────────────────

from app.schemas.common import PaginationParams  # noqa: E402


async def pagination_params(page: int = 1, page_size: int = 20) -> PaginationParams:
    """Inject standardised pagination query parameters."""
    return PaginationParams(page=page, page_size=page_size)


PaginationDep = Annotated[PaginationParams, Depends(pagination_params)]
