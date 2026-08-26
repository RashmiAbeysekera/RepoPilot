"""
Database layer — SQLAlchemy engine, session factory, and health check.

Key concepts introduced here:

  ENGINE
    An Engine is the starting point for SQLAlchemy. It holds the connection
    pool and knows how to talk to a specific database (Postgres in our case).
    Think of it as the "connection factory" — it doesn't open a connection
    immediately, it just knows *how* to open one when asked.

  SESSION
    A Session is the unit of work in SQLAlchemy. When you want to query or
    write data, you open a Session, do your work, then commit or rollback.
    We use SessionLocal() to create new session instances.

  get_db (dependency)
    FastAPI's dependency injection system calls get_db() for every request
    that needs a database session. It yields the session, runs the endpoint,
    then always closes the session — even if an exception was raised.
    This ensures we never leak open connections.
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL

logger = logging.getLogger("repopilot.database")


class Base(DeclarativeBase):
    """
    Base class that all SQLAlchemy ORM models inherit from.

    SQLAlchemy uses this class to track which Python classes represent
    database tables. When we call Base.metadata.create_all(engine), it
    looks at every subclass of Base and creates the corresponding tables.
    """
    pass


def _build_engine():
    """
    Creates the SQLAlchemy engine from the DATABASE_URL environment variable.

    pool_pre_ping=True tells SQLAlchemy to test each connection before use.
    This handles cases where the database server closes idle connections —
    without this, the next request after a long idle period would fail.
    """
    if not DATABASE_URL:
        logger.warning("DATABASE_URL is not set. Database operations will fail.")
        return None

    # SQLAlchemy 2.x requires 'postgresql+psycopg2://' for psycopg2 driver.
    # If the URL starts with 'postgresql://', we update it. This keeps
    # the .env file format simple and human-readable.
    url = DATABASE_URL.strip()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return create_engine(url, pool_pre_ping=True)


# Module-level engine — created once when the module is first imported.
engine = _build_engine()

# SessionLocal is a class (a "session factory"). Each call to SessionLocal()
# creates a brand-new session object bound to our engine.
# autocommit=False means changes aren't saved until we explicitly call commit().
# autoflush=False means SQLAlchemy won't automatically sync pending changes to
# the DB before a query — we control that ourselves for clarity.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a router:
        def my_endpoint(db: Session = Depends(get_db)):
            ...

    The 'yield' keyword makes this a generator. FastAPI calls next() to get
    the session, runs the endpoint code, then continues after the yield
    (into the finally block) to close the session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> bool:
    """
    Attempt a lightweight query against the database.
    Returns True if the database is reachable, False otherwise.

    'SELECT 1' is the simplest possible query — it touches no tables and
    costs almost nothing. It's the standard way to test connectivity.

    We never raise from here — a database outage should degrade the health
    response gracefully, not crash the request.
    """
    if engine is None:
        logger.warning("No database engine configured; skipping health check.")
        return False

    try:
        # text() wraps a raw SQL string so SQLAlchemy can handle it safely.
        # engine.connect() opens a short-lived connection just for this check.
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as error:  # noqa: BLE001 - intentionally broad for a health check
        logger.error("Database health check failed: %s", error)
        return False
