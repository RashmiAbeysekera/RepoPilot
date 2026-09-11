"""
RepoPilot AI — FastAPI backend entry point.

This file is the application root. Its responsibilities are:
  - Create the FastAPI app instance
  - Register security filters and structured logging
  - Register middleware (CORS, Request-ID, Latency tracking)
  - Register global error handlers (uniform JSON envelopes, zero leaked secrets)
  - Mount routers (health, repositories, webhooks)
  - Provide a basic root endpoint
"""

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import FRONTEND_ORIGIN
from app.core.database import check_database_health
from app.core.errors import (
    ErrorCategory,
    RateLimitExceededError,
    RepoPilotError,
    format_error_response,
)
from app.core.logging_config import SecretScrubbingFilter, log_event
from app.services.gemini_service import check_gemini_health
from app.services.github_service import check_github_health
from app.api import repositories as repositories_router
from app.api import webhooks as webhooks_router

# Configure root logger and attach secret-scrubbing filter
logging.basicConfig(level=logging.INFO)
root_logger = logging.getLogger()
scrubber = SecretScrubbingFilter()
for handler in root_logger.handlers:
    handler.addFilter(scrubber)

logger = logging.getLogger("repopilot.main")

app = FastAPI(
    title="RepoPilot AI API",
    description="Backend API for RepoPilot AI — an AI-powered software engineering assistant.",
    version="0.2.0",
)

# --- CORS ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# --- Request Context & Observability Middleware --------------------------
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """
    Attaches unique X-Request-ID to request.state, measures request duration,
    and logs structured start/complete events without logging credentials.
    """
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    start_time = time.time()

    log_event(
        logger,
        "request_started",
        method=request.method,
        path=request.url.path,
        request_id=request_id,
    )

    try:
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Request-ID"] = request_id

        log_event(
            logger,
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        log_event(
            logger,
            "request_failed",
            level=logging.ERROR,
            method=request.method,
            path=request.url.path,
            error=str(exc),
            duration_ms=duration_ms,
            request_id=request_id,
        )
        raise exc


# --- Global Exception Handlers -------------------------------------------

@app.exception_handler(RepoPilotError)
async def repopilot_error_handler(request: Request, exc: RepoPilotError):
    headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimitExceededError) else None
    return format_error_response(
        request=request,
        category=exc.category,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        headers=headers,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    category = ErrorCategory.INTERNAL_ERROR
    if exc.status_code == 404:
        category = ErrorCategory.NOT_FOUND
    elif exc.status_code in (400, 422):
        category = ErrorCategory.VALIDATION_ERROR
    elif exc.status_code == 401:
        category = ErrorCategory.UNAUTHORIZED
    elif exc.status_code == 403:
        category = ErrorCategory.FORBIDDEN
    elif exc.status_code == 429:
        category = ErrorCategory.RATE_LIMIT
    elif exc.status_code in (502, 503):
        category = ErrorCategory.EXTERNAL_API_UNAVAILABLE

    return format_error_response(
        request=request,
        category=category,
        message=str(exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return format_error_response(
        request=request,
        category=ErrorCategory.VALIDATION_ERROR,
        message=str(exc),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception: %s", exc)
    return format_error_response(
        request=request,
        category=ErrorCategory.INTERNAL_ERROR,
        message="An unexpected server error occurred. Please try again later.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# --- Routers ------------------------------------------------------------
app.include_router(repositories_router.router)
app.include_router(webhooks_router.router)


# --- Endpoints ----------------------------------------------------------

@app.get("/")
def root() -> dict[str, str]:
    """Simple root endpoint so visiting http://localhost:8000 shows something useful."""
    return {"message": "RepoPilot AI backend is running. See /docs for the API reference."}


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """
    Reports whether the backend process, database, AI, and GitHub integrations are healthy.

    Response shape:
        {
          "status": "healthy" | "degraded",
          "backend": "healthy",
          "database": "healthy" | "unavailable",
          "ai": "healthy" | "not-configured",
          "github": "healthy" | "unavailable"
        }
    """
    backend_status = "healthy"
    database_is_healthy = check_database_health()
    database_status = "healthy" if database_is_healthy else "unavailable"
    ai_status = check_gemini_health()
    github_status = check_github_health()
    overall_status = "healthy" if database_is_healthy else "degraded"

    if not database_is_healthy:
        logger.warning("Health check reporting degraded status: database unavailable.")

    return {
        "status": overall_status,
        "backend": backend_status,
        "database": database_status,
        "ai": ai_status,
        "github": github_status,
    }
