"""
Minimal PostgreSQL connectivity layer.

For Day 1 we only need to prove that FastAPI can talk to our Supabase
PostgreSQL database. We use psycopg2 directly (no ORM) because:

  1. The only thing we need to do today is open a connection and run
     "SELECT 1" — an ORM would add complexity with no benefit yet.
  2. It keeps the concept clear: a "database connection" is just a
     network connection to a Postgres server, authenticated with a
     connection string.

A tool like SQLAlchemy will likely be introduced later once we have
real tables, models, and queries to manage — at that point an ORM
starts paying for itself. Introducing it today would be over-engineering.
"""

import logging

import psycopg2

from app.config import DATABASE_URL

logger = logging.getLogger("repopilot.database")


def check_database_health() -> bool:
    """
    Attempt a short-lived connection to PostgreSQL and run a trivial
    query. Returns True if the database is reachable and responsive,
    False otherwise.

    We deliberately never raise this error up to the API layer — a
    database outage should degrade the health response, not crash
    the request.
    """
    if not DATABASE_URL:
        logger.warning("DATABASE_URL is not set; skipping database check.")
        return False

    connection = None
    try:
        # A short connect_timeout prevents a slow/unreachable database
        # from hanging the health check indefinitely.
        connection = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return True
    except Exception as error:  # noqa: BLE001 - intentionally broad for a health check
        # Log the real error for developers, but never let it leak
        # to the client (see main.py's error handling).
        logger.error("Database health check failed: %s", error)
        return False
    finally:
        if connection is not None:
            connection.close()
