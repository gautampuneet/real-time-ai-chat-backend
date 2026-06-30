"""Base service class.

Services orchestrate one or more repositories and contain business logic.
They receive an ``AsyncSession`` at construction time; the session lifecycle
(commit / rollback) is managed by the repository layer and ultimately by the
``get_db`` dependency in the request handler.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger


class BaseService:
    """Thin base that wires a logger and session into every service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logger = get_logger(self.__class__.__module__)
