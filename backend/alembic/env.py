"""
Alembic environment file — tells Alembic how to connect to the database
and where to find our SQLAlchemy models.

HOW ALEMBIC WORKS:
  1. You define your database schema using SQLAlchemy models (app/models/).
  2. Alembic reads those models through Base.metadata.
  3. When you run 'alembic revision --autogenerate', Alembic compares
     Base.metadata (what your code says the schema should be) with the
     actual database schema, and generates a migration script with the diff.
  4. When you run 'alembic upgrade head', Alembic runs all pending
     migration scripts against the real database.

This means you never manually write CREATE TABLE or ALTER TABLE SQL —
you just update your Python model, generate a migration, and apply it.
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Make sure 'backend/' is on the Python path so we can import 'app.*'
# This is needed because Alembic runs from backend/, not the project root.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our config so load_dotenv() runs and DATABASE_URL is available
from app.core.config import DATABASE_URL  # noqa: E402

# Import Base — Alembic uses Base.metadata to know which tables exist in
# our models. We also import the model itself so SQLAlchemy registers it.
from app.core.database import Base  # noqa: E402
import app.models.repository  # noqa: F401, E402 — registers Repository with Base.metadata

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Set up Python logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Give Alembic our model metadata — this is how autogenerate knows what tables
# should exist based on our SQLAlchemy models.
target_metadata = Base.metadata

# Override the SQLAlchemy URL from our environment variable.
# This means alembic.ini doesn't need (and should not have) a hardcoded URL.
if DATABASE_URL:
    url = DATABASE_URL.strip()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    # configparser interprets % as an interpolation marker.
    # We escape it as %% so the URL is stored literally.
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL without a live DB connection.
    Useful for reviewing migration SQL before running it.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the real database and applies changes.
    This is what 'alembic upgrade head' uses.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
