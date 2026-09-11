"""
Standardized error classification and custom exceptions for RepoPilot.

RESPONSIBILITIES:
  - Define uniform error categories across all application layers
  - Provide domain-specific exception types
  - Ensure zero leaking of internal stack traces, database credentials, or API keys
  - Standardize error response payloads with correlation IDs
"""

import logging
from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("repopilot.errors")


class ErrorCategory:
    """Standard error categories for predictable API consumers and clients."""
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    EXTERNAL_API_UNAVAILABLE = "external_api_unavailable"
    DATABASE_ERROR = "database_error"
    EMBEDDING_FAILURE = "embedding_failure"
    VECTOR_SEARCH_FAILURE = "vector_search_failure"
    GEMINI_FAILURE = "gemini_failure"
    TOOL_FAILURE = "tool_failure"
    RATE_LIMIT = "rate_limit"
    INTERNAL_ERROR = "internal_error"


class RepoPilotError(Exception):
    """Base exception for all domain-specific RepoPilot failures."""

    def __init__(
        self,
        message: str,
        category: str = ErrorCategory.INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = status_code
        self.details = details or {}


class RepositoryNotFoundError(RepoPilotError):
    """Raised when an operation references a nonexistent repository."""

    def __init__(self, repository_id: Any) -> None:
        super().__init__(
            message=f"Repository '{repository_id}' not found.",
            category=ErrorCategory.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class RepositoryFileNotFoundError(RepoPilotError):
    """Raised when an operation references a nonexistent repository file."""

    def __init__(self, file_id: Any, repository_id: Any) -> None:
        super().__init__(
            message=f"File '{file_id}' not found in repository '{repository_id}'.",
            category=ErrorCategory.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(RepoPilotError):
    """Raised when user input violates validation boundaries."""

    def __init__(self, message: str, field: str | None = None) -> None:
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class RateLimitExceededError(RepoPilotError):
    """Raised when a request exceeds configured throughput ceilings."""

    def __init__(self, message: str = "Rate limit exceeded. Please wait before retrying.", retry_after: int = 60) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after": retry_after},
        )
        self.retry_after = retry_after


class ExternalServiceError(RepoPilotError):
    """Raised when an upstream external API (GitHub, Gemini) fails or is unavailable."""

    def __init__(
        self,
        service: str,
        message: str,
        category: str = ErrorCategory.EXTERNAL_API_UNAVAILABLE,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ) -> None:
        super().__init__(
            message=f"{service} failure: {message}",
            category=category,
            status_code=status_code,
            details={"service": service},
        )


def format_error_response(
    request: Request | None,
    category: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """
    Format a uniform JSON error envelope for clients without leaking stack traces or secrets.
    """
    request_id = getattr(request.state, "request_id", None) if request and hasattr(request, "state") else None

    payload: dict[str, Any] = {
        "error": {
            "category": category,
            "message": message,
        }
    }
    # Keep top-level 'detail' string for FastAPI backward-compatibility with existing frontend/tests
    payload["detail"] = message

    if request_id:
        payload["error"]["request_id"] = request_id
    if details:
        payload["error"]["details"] = details

    return JSONResponse(status_code=status_code, content=payload, headers=headers)
