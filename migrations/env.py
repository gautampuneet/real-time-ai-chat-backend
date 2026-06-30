"""Alembic environment configuration.

Supports async engine (asyncpg) via ``run_async_migrations``.
The database URL is pulled from the application's ``Settings`` object so
the same ``.env`` file used by the app also drives migrations.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

# Import models module to ensure all ORM models are registered on Base.metadata.
import app.models  # noqa: F401
from alembic import context
from app.config import get_settings

# Import the declarative base so Alembic can discover all mapped models.
from app.database.base import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url with the value from our Settings object so
# the same .env / environment variables drive both the app and migrations.
settings = get_settings()
config.set_main_option("sqlalchemy.url", str(settings.database_url))

target_metadata = Base.metadata


# ── Helpers ───────────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine (asyncpg)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
