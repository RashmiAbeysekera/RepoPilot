"""
Pydantic schemas for ChunkEmbedding API responses.
"""

import uuid
from pydantic import BaseModel


class EmbeddingGenerationResponse(BaseModel):
    """
    Response schema after running embedding generation for a repository.
    """

    repository_id: uuid.UUID
    total_chunks: int
    chunks_processed: int
    embeddings_created: int
    embeddings_updated: int
    embeddings_skipped: int


class EmbeddingStatusResponse(BaseModel):
    """
    Response schema for querying embedding coverage & metadata for a repository.
    """

    repository_id: uuid.UUID
    total_chunks: int
    embedded_chunks: int
    remaining_chunks: int
    model_name: str
    embedding_dimension: int
