"""Global FastAPI exception handlers.
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.exceptions.errors import AppError
from app.logging_config import get_logger
from app.schemas.common import ErrorDetail, ErrorResponse

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return request.headers.get("X-Request-ID")


def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach all exception handlers to the FastAPI application.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "application error",
            error_code=exc.error_code,
            status_code=exc.status_code,
            message=exc.message,
            path=request.url.path,
        )
        body = ErrorResponse(
            status_code=exc.status_code,
            message=exc.message,
            request_id=_request_id(request),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            ErrorDetail(
                field=".".join(str(loc) for loc in e["loc"]),
                message=e["msg"],
                code=e["type"],
            )
            for e in exc.errors()
        ]
        logger.info(
            "request validation failed",
            path=request.url.path,
            errors=[e.model_dump() for e in errors],
        )
        body = ErrorResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation failed",
            errors=errors,
            request_id=_request_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body.model_dump(),
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_error_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        errors = [
            ErrorDetail(
                field=".".join(str(loc) for loc in e["loc"]),
                message=e["msg"],
                code=e["type"],
            )
            for e in exc.errors()
        ]
        body = ErrorResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Schema validation failed",
            errors=errors,
            request_id=_request_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled exception",
            path=request.url.path,
            exc_info=traceback.format_exc(),
        )
        body = ErrorResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred",
            request_id=_request_id(request),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(),
        )
