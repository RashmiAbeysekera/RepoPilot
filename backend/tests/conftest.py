"""
Pytest configuration and shared fixtures.

FIXTURES:
  Fixtures are functions that pytest calls automatically before each test
  that requests them. They set up the environment the test needs, then
  clean up after the test completes.

  The 'client' fixture provides an httpx test client that sends real HTTP
  requests to our FastAPI app — without needing a running server process.
  This is the standard way to test FastAPI applications.

  The 'db_session' fixture provides a database session that automatically
  rolls back after each test — so tests don't pollute each other's data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.config import DATABASE_URL


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

def _build_test_url() -> str | None:
    """Return the same DATABASE_URL as production (we use a real test DB here)."""
    if not DATABASE_URL:
        return None
    url = DATABASE_URL.strip()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


TEST_DATABASE_URL = _build_test_url()

# We only set up the test engine if a DATABASE_URL is available.
# If it's missing, tests that need the DB will be skipped.
test_engine = (
    create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    if TEST_DATABASE_URL
    else None
)

TestSessionLocal = (
    sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    if test_engine
    else None
)


@pytest.fixture()
def db_session():
    """
    Provide a database session that rolls back after each test.

    Rolling back means every INSERT/DELETE done during the test is undone
    automatically — tests don't leave data behind in the real database.
    """
    if TestSessionLocal is None:
        pytest.skip("DATABASE_URL not configured — skipping database test.")

    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """
    Provide an httpx TestClient that uses the rolled-back test DB session.

    We override the get_db dependency so every request during a test uses
    the same session — the one that will be rolled back after the test.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # session cleanup is handled by the db_session fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def client_no_db():
    """
    Provide a TestClient with no database dependency override.
    Used for health check tests that test real connectivity.
    """
    with TestClient(app) as c:
        yield c
