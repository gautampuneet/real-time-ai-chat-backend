"""Database access for users."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """
    Query wrapper for user persistence.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        is_active: bool = True,
        is_superuser: bool = False,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            is_active=is_active,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(exists().where(User.email == email))
        result = await self.session.execute(stmt)
        return result.scalar_one()
