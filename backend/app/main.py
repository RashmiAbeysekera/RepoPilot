"""
RepoPilot AI — FastAPI backend entry point.

Day 1 scope: a single health-check endpoint that proves the
Next.js -> FastAPI -> PostgreSQL chain works end to end.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_ORIGIN
from app.database import check_database_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repopilot.main")

app = FastAPI(
    title="RepoPilot AI API",
    description="Backend API for RepoPilot AI — an AI-powered software engineering assistant.",
    version="0.1.0",
)

# --- CORS -------------------------------------------------------------
# The frontend (http://localhost:3000) and backend (http://localhost:8000)
# are different origins (different ports count as different origins).
# Browsers block cross-origin requests by default for security — this is
# CORS (Cross-Origin Resource Sharing). We must explicitly tell FastAPI
# which origins are allowed to call this API.
#
# We only allow the known frontend origin, never "*" (wildcard), because
# a wildcard would let ANY website in the world send requests to our API
# from a user's browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    """Simple root endpoint so visiting http://localhost:8000 shows something useful."""
    return {"message": "RepoPilot AI backend is running. See /docs for the API reference."}


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """
    Reports whether the backend process and the database are healthy.

    Response shape:
        {
          "status": "healthy" | "degraded",
          "backend": "healthy",
          "database": "healthy" | "unavailable"
        }

    We never expose connection strings, stack traces, or other internal
    details in this response — only a simple status string.
    """
    # If this function is executing at all, the backend process itself
    # is up and able to handle requests.
    backend_status = "healthy"

    database_is_healthy = check_database_health()
    database_status = "healthy" if database_is_healthy else "unavailable"

    overall_status = "healthy" if database_is_healthy else "degraded"

    if not database_is_healthy:
        logger.warning("Health check reporting degraded status: database unavailable.")

    return {
        "status": overall_status,
        "backend": backend_status,
        "database": database_status,
    }
