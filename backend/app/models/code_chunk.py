"""
SQLAlchemy ORM model for the 'code_chunks' table.

Represents a text chunk created from a RepositoryFile.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CodeChunk(Base):
    """
    Represents a code/documentation chunk belonging to a RepositoryFile.

    Table: code_chunks
    """

    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    repository_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 0-indexed position of chunk within the file
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Actual text content of the chunk
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 1-indexed line numbers in the original file
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)

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

    # Relationship back to RepositoryFile
    repository_file: Mapped["RepositoryFile"] = relationship(
        "RepositoryFile",
        back_populates="chunks",
    )

    __table_args__ = (
        UniqueConstraint(
            "repository_file_id",
            "chunk_index",
            name="uq_code_chunks_file_id_chunk_index",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CodeChunk id={self.id} "
            f"repository_file_id={self.repository_file_id} "
            f"index={self.chunk_index} "
            f"lines={self.start_line}-{self.end_line}>"
        )
