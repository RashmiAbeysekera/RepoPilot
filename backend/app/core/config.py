"""
Centralized application configuration.

We load all environment variables in ONE place instead of scattering
os.getenv() calls across the codebase. This makes it obvious what
configuration the app depends on, and makes it easy to see what is
missing if something breaks.
"""

import os

from dotenv import load_dotenv

# Loads variables from a local .env file into the process environment.
# In production (e.g. Cloud Run, Vercel) the platform injects real
# environment variables directly, so this call is a no-op there.
load_dotenv()

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
    """Read GEMINI_API_KEY from environment, refreshing from .env file if updated."""
    load_dotenv(override=True)
    key = os.getenv("GEMINI_API_KEY")
    return key.strip() if key else None


def get_gemini_model() -> str:
    """Read GEMINI_MODEL from environment, refreshing from .env file if updated."""
    load_dotenv(override=True)
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    return model.strip() if model else "gemini-3.5-flash"


def get_github_webhook_secret() -> str | None:
    """Read GITHUB_WEBHOOK_SECRET from environment, refreshing from .env file if updated."""
    load_dotenv(override=True)
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    return secret.strip() if secret else None


# Module-level references for backwards compatibility
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GITHUB_WEBHOOK_SECRET: str | None = os.getenv("GITHUB_WEBHOOK_SECRET")




