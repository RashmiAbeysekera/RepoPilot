"""
DEPRECATED: This file has moved to app/core/database.py.

This module re-exports everything from the new location for backward compatibility.
The old check_database_health() function is still available here.
"""
from app.core.database import (  # noqa: F401
    Base,
    SessionLocal,
    check_database_health,
    engine,
    get_db,
)
