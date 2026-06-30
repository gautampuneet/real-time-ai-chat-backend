"""Application configuration via pydantic-settings.

All values can be overridden by environment variables or a .env file.
Sensitive fields (secrets, passwords) are typed as SecretStr so they are
never accidentally serialised into logs or responses.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


WEAK_JWT_SECRETS = {
    "CHANGE_ME_IN_PRODUCTION",
    "local-development-secret-change-me",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "Real-Time AI Chat Backend"
    app_version: str = "0.1.0"
    app_env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    # Comma-separated list of allowed CORS origins; defaults to localhost dev
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])

    host: str = "0.0.0.0"
    port: int = 8000

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: PostgresDsn = Field(...)
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: RedisDsn = Field(...)
    redis_max_connections: int = 20

    # ── JWT / Auth ───────────────────────────────────────────────────────────
    jwt_secret_key: SecretStr = Field(...)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: Annotated[int, Field(gt=0)] = 30
    refresh_token_expire_days: Annotated[int, Field(gt=0)] = 7

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = False  # structured JSON logs in production

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        """Enforce stricter requirements when running in production."""
        if self.app_env == Environment.PRODUCTION:
            if self.jwt_secret_key.get_secret_value() in WEAK_JWT_SECRETS:
                raise ValueError("jwt_secret_key must be changed before running in production")
            if self.debug:
                raise ValueError("debug must be False in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.app_env == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        return self.app_env == Environment.TESTING


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Use FastAPI's ``Depends(get_settings)`` for dependency injection.
    """
    return Settings()
