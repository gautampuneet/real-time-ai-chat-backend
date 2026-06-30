"""Async SQLAlchemy session factory.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Create the engine and session factory.
    """
    global _engine, AsyncSessionLocal

    settings = get_settings()
    db_url = str(settings.database_url)

    logger.info("initialising database connection pool", url=_redact_url(db_url))

    _engine = create_async_engine(
        db_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    logger.info("database connection pool ready")


async def close_db() -> None:
    """
    dispose the engine.
    """
    global _engine, AsyncSessionLocal

    if _engine is not None:
        logger.info("closing database connection pool")
        await _engine.dispose()
        _engine = None
        AsyncSessionLocal = None
        logger.info("database connection pool closed")


def get_engine() -> AsyncEngine:
    """
    Return the initialised engine; raises if ``init_db`` was not called.
    """
    if _engine is None:
        raise RuntimeError("Database engine is not initialised. Call init_db() first.")
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
        Get DB Session.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("AsyncSessionLocal is not initialised. Call init_db() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def _redact_url(url: str) -> str:
    """
    Replace the password in a DSN string with asterisks for safe logging.
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    if parsed.password:
        netloc = parsed.netloc.replace(parsed.password, "****")
        return urlunparse(parsed._replace(netloc=netloc))
    return url
