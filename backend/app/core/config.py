"""
Centralized application configuration.

We load all environment variables in ONE place instead of scattering
os.getenv() calls across the codebase. This makes it obvious what
configuration the app depends on, and makes it easy to see what is
missing if something breaks.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Explicitly resolve the backend directory to ensure .env is found
# regardless of current working directory.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"
load_dotenv(dotenv_path=_ENV_FILE)

# The connection string for our Supabase PostgreSQL database.
# This is intentionally NOT hardcoded — it is read from the environment
# so that real credentials never end up in source control.
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# Comma-separated list of frontend origins allowed to call this API.
# Defaults to the local Next.js dev server if not explicitly set.
_default_origin = "http://localhost:3000"
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", _default_origin)

# Dynamic helper functions to ensure edits to .env take effect immediately
# without requiring a full server process restart.
def get_gemini_api_key() -> str | None:
    """Read GEMINI_API_KEY (or fallback GOOGLE_API_KEY) from environment."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return key.strip() if key else None


def get_gemini_model() -> str:
    """Read GEMINI_MODEL from environment, refreshing from .env file if updated."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    return model.strip() if model else "gemini-3.5-flash"


def get_gemini_max_retries() -> int:
    """Read GEMINI_MAX_RETRIES from environment, defaulting to 3."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    raw = os.getenv("GEMINI_MAX_RETRIES")
    if raw:
        try:
            val = int(raw.strip())
            if 0 <= val <= 10:
                return val
        except ValueError:
            pass
    return 3


def get_github_webhook_secret() -> str | None:
    """Read GITHUB_WEBHOOK_SECRET from environment, refreshing from .env file if updated."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    return secret.strip() if secret else None


def get_rag_similarity_threshold() -> float:
    """
    Read RAG_SIMILARITY_THRESHOLD from environment, defaulting to 0.20.

    Empirically measured for all-MiniLM-L6-v2:
      - Legitimate code matches cluster between 0.24 and 0.32.
      - Out-of-context queries (e.g. general trivia) score < 0.15.
    """
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    raw = os.getenv("RAG_SIMILARITY_THRESHOLD")
    if raw:
        try:
            val = float(raw.strip())
            if 0.0 <= val <= 1.0:
                return val
        except ValueError:
            pass
    return 0.20


def get_max_agent_iterations() -> int:
    """Read MAX_AGENT_ITERATIONS from environment, defaulting to 5."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    raw = os.getenv("MAX_AGENT_ITERATIONS")
    if raw:
        try:
            val = int(raw.strip())
            if 1 <= val <= 20:
                return val
        except ValueError:
            pass
    return 5


def get_rate_limit_enabled() -> bool:
    """Read RATE_LIMIT_ENABLED from environment, defaulting to True."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    val = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower()
    return val in ("1", "true", "yes", "on")


def get_ai_rate_limit_per_minute() -> int:
    """Read AI_RATE_LIMIT_PER_MINUTE from environment, defaulting to 15."""
    load_dotenv(dotenv_path=_ENV_FILE, override=True)
    raw = os.getenv("AI_RATE_LIMIT_PER_MINUTE")
    if raw:
        try:
            val = int(raw.strip())
            if 1 <= val <= 300:
                return val
        except ValueError:
            pass
    return 15


# Module-level references for backwards compatibility
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
GITHUB_WEBHOOK_SECRET: str | None = os.getenv("GITHUB_WEBHOOK_SECRET")
RAG_SIMILARITY_THRESHOLD: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.20"))
MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "5"))
RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
AI_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "15"))





