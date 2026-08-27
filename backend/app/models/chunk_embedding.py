"""
SQLAlchemy ORM model for the 'chunk_embeddings' table.

Stores numerical vector embeddings generated from CodeChunk records using pgvector.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.code_chunk import CodeChunk

# Selected embedding model: all-MiniLM-L6-v2 outputs 384-dimensional dense vectors
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIMENSION = 384


class ChunkEmbedding(Base):
    """
    Represents a vector embedding corresponding to a CodeChunk.

    Table: chunk_embeddings
    """

    __tablename__ = "chunk_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    code_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # pgvector 384-dimensional floating point vector column
    embedding: Mapped[list[float]] = mapped_column(
        Vector(DEFAULT_EMBEDDING_DIMENSION),
        nullable=False,
    )

    # Name of the model used to produce the embedding
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default=DEFAULT_EMBEDDING_MODEL,
    )

    # Dimensionality of the vector (384)
    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_EMBEDDING_DIMENSION,
    )

    # SHA-256 hash of the CodeChunk.content string for fast change-detection & idempotency
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

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

    # Relationship back to CodeChunk (one-to-one)
    code_chunk: Mapped["CodeChunk"] = relationship(
        "CodeChunk",
        back_populates="embedding",
    )

    __table_args__ = (
        UniqueConstraint("code_chunk_id", name="uq_chunk_embeddings_code_chunk_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChunkEmbedding id={self.id} "
            f"code_chunk_id={self.code_chunk_id} "
            f"model={self.model_name!r} "
            f"dim={self.embedding_dimension}>"
        )
