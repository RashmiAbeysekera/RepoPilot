"""
DEPRECATED: This file has moved to app/core/config.py.

This module re-exports everything from the new location so that any
existing code that imports from 'app.config' still works without modification.
"""
from app.core.config import DATABASE_URL, FRONTEND_ORIGIN  # noqa: F401
