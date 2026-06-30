from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AppBaseModel(BaseModel):
    """
    Base for all application schemas.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorDetail(AppBaseModel):
    """error detail included in error responses."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(AppBaseModel):
    """error response returned by exception handlers."""

    status_code: int
    message: str
    errors: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


class PaginationParams(AppBaseModel):
    """Query-parameter schema for paginated list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=200, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class HealthResponse(AppBaseModel):
    """Schema for the /health endpoint."""

    status: str
    version: str
    environment: str
    checks: dict[str, Any] = Field(default_factory=dict)
