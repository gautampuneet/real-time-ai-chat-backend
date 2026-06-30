"""Router registry.

``register_routers`` is the single place where all routers are attached to
the FastAPI app. Import and add new routers here as features are built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.routers.auth import router as auth_router
from app.routers.conversations import router as conversations_router
from app.routers.health import router as health_router
from app.routers.ws import router as ws_router

if TYPE_CHECKING:
    from fastapi import FastAPI


def register_routers(app: FastAPI) -> None:
    """Mount all routers onto the FastAPI application."""
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(conversations_router)
    app.include_router(ws_router)
