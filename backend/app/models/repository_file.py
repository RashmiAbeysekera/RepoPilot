"""
SQLAlchemy ORM model for the 'repository_files' table.

Represents a single file discovered and persisted during repository ingestion.
"""

import uuid
from datetime import datetime, timezone

from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.code_chunk import CodeChunk
    from app.models.repository import Repository



class RepositoryFile(Base):
    """
    Represents a file belonging to a Repository.

    Table: repository_files
    """

    __tablename__ = "repository_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Full relative path within repository, e.g. "src/components/Login.jsx"
    path: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Base filename, e.g. "Login.jsx"
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # File extension, e.g. ".jsx"
    extension: Mapped[str] = mapped_column(String(50), nullable=False)

    # File size in bytes
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Category, e.g. "source", "documentation", "configuration"
    file_type: Mapped[str] = mapped_column(String(50), nullable=False, default="source")

    # Raw text content of the file (nullable for oversized or unread files)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # Relationship back to Repository
    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")

    # Relationship to CodeChunk (one-to-many)
    chunks: Mapped[list["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="repository_file",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "path", name="uq_repository_files_repository_id_path"),
    )

    def __repr__(self) -> str:
        return f"<RepositoryFile id={self.id} repository_id={self.repository_id} path={self.path!r}>"
