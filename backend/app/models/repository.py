"""
SQLAlchemy ORM model for the 'repositories' table.

A MODEL is a Python class that mirrors a database table.
Each attribute maps to a column. SQLAlchemy reads this class
definition to know how to generate SQL for inserts, selects, etc.

Alembic also reads this model (through Base.metadata) to generate
migration scripts — so the model is the single source of truth for
the database schema.
"""

import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.repository_file import RepositoryFile


class Repository(Base):
    """
    Represents a GitHub repository that a user has added to RepoPilot.

    Table: repositories
    """

    __tablename__ = "repositories"

    # UUID primary key — better than auto-increment integers for distributed
    # systems and future-proofing. gen_random_uuid() is a PostgreSQL function
    # that generates a UUID on the database side.
    # We also provide a Python-side default (uuid.uuid4) so tests that don't
    # go through the database can still create model instances.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # The short repository name, e.g. "RepoPilot"
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # The GitHub "owner/repo" identifier, e.g. "RashmiAbeysekera/RepoPilot"
    # UNIQUE ensures the same repository can't be added twice.
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # The full HTTPS URL, e.g. "https://github.com/RashmiAbeysekera/RepoPilot"
    # Also UNIQUE to prevent duplicates from a different angle.
    github_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)

    # Optional human-readable description from GitHub.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Default branch name, typically "main" or "master".
    default_branch: Mapped[str] = mapped_column(
        String(100), nullable=False, default="main"
    )

    # Timestamps — server_default means the database sets these automatically
    # when a row is inserted. onupdate tells SQLAlchemy to refresh updated_at
    # whenever the record is modified via the ORM.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship to RepositoryFile (one-to-many)
    files: Mapped[list["RepositoryFile"]] = relationship(
        "RepositoryFile",
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Repository id={self.id} full_name={self.full_name!r}>"
