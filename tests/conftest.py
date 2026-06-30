"""Pytest configuration and fixtures.

Shared fixtures for the entire test suite:
  - ``settings``           – Settings overridden for testing
  - ``engine``             – in-memory / test-DB async engine
  - ``db``                 – per-test transactional session (rolled back after)
  - ``redis``              – fakeredis async client
  - ``client``             – AsyncClient wired to the test app
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from app.config import Environment, Settings, get_settings
from app.database.base import Base
from app.database.redis import get_redis
from app.database.session import get_db
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ── Settings override ─────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return Settings configured for the test environment."""
    return Settings(
        app_env=Environment.TESTING,
        debug=True,
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/chatdb_test",  # type: ignore[arg-type]
        redis_url="redis://localhost:6379/15",  # type: ignore[arg-type]
        jwt_secret_key="test-secret-key-not-for-production",  # type: ignore[arg-type]
        log_level="DEBUG",
        db_echo=False,
    )


# ── Event loop ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


# ── Database ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def engine(test_settings: Settings) -> AsyncGenerator[Any, None]:
    """Create all tables once per test session; drop them afterwards."""
    _engine = create_async_engine(
        str(test_settings.database_url),
        echo=False,
        pool_pre_ping=True,
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield _engine

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture
async def db(engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Yield a per-test session wrapped in a savepoint.

    The savepoint is rolled back after each test so tests remain isolated
    without re-creating the schema.
    """
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── Redis (fakeredis) ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator[Any, None]:
    """Yield a fakeredis async client (no real Redis needed)."""
    try:
        import fakeredis.aioredis as fakeredis_async  # type: ignore[import]

        server = fakeredis_async.FakeRedis()
        yield server
        await server.aclose()
    except ImportError:
        pytest.skip("fakeredis not installed – skipping Redis-dependent tests")


# ── FastAPI test client ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(
    test_settings: Settings,
    db: AsyncSession,
    fake_redis: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient pointing at the test app.

    Overrides ``get_db``, ``get_redis``, and ``get_settings`` so tests never
    touch a real database or Redis.
    """
    from app.main import create_app

    test_app: FastAPI = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    async def override_get_redis() -> Any:
        return fake_redis

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_redis] = override_get_redis
    test_app.dependency_overrides[get_settings] = lambda: test_settings

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as ac:
        yield ac
