"""Domain-level exceptions used throughout the application.

All custom exceptions inherit from ``AppError``, making it easy to catch
any application error in a single except clause when needed.
"""

from __future__ import annotations

from http import HTTPStatus


class AppError(Exception):
    """
    Base class for all application exceptions.
    """

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    default_message: str = "An unexpected error occurred"
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


class NotFoundError(AppError):
    """
    Raised when a requested resource does not exist.
    """

    status_code = HTTPStatus.NOT_FOUND
    default_message = "Resource not found"
    error_code = "NOT_FOUND"

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} '{identifier}' was not found")
        self.resource = resource
        self.identifier = identifier


class AlreadyExistsError(AppError):
    """
    Raised when a resource with the same unique key already exists.
    """

    status_code = HTTPStatus.CONFLICT
    default_message = "Resource already exists"
    error_code = "ALREADY_EXISTS"

    def __init__(self, resource: str, field: str, value: str) -> None:
        super().__init__(f"{resource} with {field}='{value}' already exists")
        self.resource = resource
        self.field = field
        self.value = value


class AuthenticationError(AppError):
    """
    Raised when authentication credentials are missing or invalid.
    """

    status_code = HTTPStatus.UNAUTHORIZED
    default_message = "Authentication required"
    error_code = "UNAUTHENTICATED"
