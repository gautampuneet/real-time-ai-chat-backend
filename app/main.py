from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import get_settings
from app.database.redis import close_redis, init_redis
from app.database.session import close_db, init_db
from app.exceptions.handlers import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.routers import register_routers
from app.websocket.pubsub import redis_websocket_pubsub

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: initialise and cleanly shut down resources."""
    configure_logging(settings)
    logger.info(
        "starting application",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )

    await init_db()
    await init_redis()
    await redis_websocket_pubsub.start()

    logger.info("application startup complete")
    yield

    logger.info("shutting down application")
    await redis_websocket_pubsub.stop()
    await close_redis()
    await close_db()
    logger.info("application shutdown complete")


def create_app() -> FastAPI:
    """Application factory – returns a configured FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FastAPI chat backend with PostgreSQL, Redis, and WebSockets",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    register_routers(app)

    return app


app = create_app()
