"""Redis async client lifecycle management."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_redis_client: Redis | None = None


async def init_redis() -> None:
    """
    Create async Redis connection pool.
    """
    global _redis_client

    settings = get_settings()
    redis_url = str(settings.redis_url)

    logger.info("initialising Redis connection pool", url=_redact_url(redis_url))

    _redis_client = aioredis.from_url(
        redis_url,
        max_connections=settings.redis_max_connections,
        encoding="utf-8",
        decode_responses=True,
    )

    # Verify connectivity
    await _redis_client.ping()
    logger.info("Redis connection pool ready")


async def close_redis() -> None:
    """
    Close all connections in the Redis pool.
    """
    global _redis_client

    if _redis_client is not None:
        logger.info("closing Redis connection pool")
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection pool closed")


def get_redis_client() -> Redis:
    """
    Return the initialised Redis client; raises RuntimeError if ``init_redis`` was not called.
    """
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialised. Call init_redis() first.")
    return _redis_client


async def get_redis() -> Redis:
    """
    FastAPI dependency – yields a Redis client for the duration of a request.
    """
    return get_redis_client()


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.password:
        netloc = parsed.netloc.replace(parsed.password, "****")
        return urlunparse(parsed._replace(netloc=netloc))
    return url
