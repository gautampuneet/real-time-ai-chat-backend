"""
Health check endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database.redis import get_redis
from app.database.session import get_db
from app.logging_config import get_logger
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])
logger = get_logger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    status_code=status.HTTP_200_OK,
)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Lightweight liveness probe – returns 200 if the application is running."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=str(settings.app_env),
    )


@router.get(
    "/health/live",
    response_model=HealthResponse,
    summary="Kubernetes liveness probe",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def liveness(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=str(settings.app_env),
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    status_code=status.HTTP_200_OK,
)
async def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
    """Deep readiness probe – checks database and Redis connectivity."""
    checks: dict[str, str] = {}
    overall_status = "ok"

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("database health check failed", exc_info=exc)
        checks["database"] = "error"
        overall_status = "degraded"

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("redis health check failed", exc_info=exc)
        checks["redis"] = "error"
        overall_status = "degraded"

    if overall_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=str(settings.app_env),
        checks=checks,
    )
