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
