"""
Embedding Service — Local vector embedding generation and persistence.

RESPONSIBILITIES:
  - Load and cache a local SentenceTransformers embedding model (all-MiniLM-L6-v2)
  - Generate 384-dimensional dense floating-point vector representations for text
  - Process chunks in memory efficient mini-batches
  - Idempotent generation using SHA-256 content hashes (skip unchanged, update modified)
  - Pure local operation (0 external paid APIs, 0 network dependencies)
"""

import hashlib
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository_file import RepositoryFile

logger = logging.getLogger("repopilot.embedding")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Module-level singleton instance for lazy model loading
_model_instance = None


def get_embedding_model():
    """
    Lazily load and cache the SentenceTransformer embedding model.

    Using a singleton pattern prevents reloading model weights from disk
    for every request, drastically improving memory and CPU performance.
    """
    global _model_instance
    if _model_instance is None:
        import os
        import torch
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        try:
            torch.set_num_threads(1)
        except Exception:
            pass
        logger.info("Loading SentenceTransformer model '%s'...", EMBEDDING_MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        _model_instance = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("SentenceTransformer model '%s' loaded successfully.", EMBEDDING_MODEL_NAME)
    return _model_instance


def compute_content_hash(text: str) -> str:
    """
    Compute a SHA-256 hex string for the given text.
    Used for fast change detection to ensure idempotent embedding generation.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate 384-dimensional vector embeddings for a list of text strings.

    Args:
        texts: List of text content strings to embed.

    Returns:
        List of 384-element float lists.
    """
    if not texts:
        return []

    model = get_embedding_model()
    # model.encode returns numpy ndarray of shape (len(texts), 384)
    embeddings_array = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    
    # Convert numpy float arrays to standard Python float lists for pgvector/SQLAlchemy
    return [vec.tolist() for vec in embeddings_array]


def generate_embeddings_for_repository(
    db: Session,
    repository_id: uuid.UUID,
    batch_size: int = 32,
) -> dict[str, Any]:
    """
    Generate and store vector embeddings for all CodeChunk records in a repository.

    Idempotent operation:
      - Unchanged chunks (matching content_hash & model_name) are skipped.
      - Modified chunks have their embedding updated.
      - Chunks without embeddings receive a newly generated ChunkEmbedding row.

    Returns summary stats:
    {
        "repository_id": repository_id,
        "total_chunks": total,
        "chunks_processed": processed,
        "embeddings_created": created,
        "embeddings_updated": updated,
        "embeddings_skipped": skipped,
    }
    """
    chunks = (
        db.query(CodeChunk)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .all()
    )

    total_chunks = len(chunks)
    if total_chunks == 0:
        return {
            "repository_id": repository_id,
            "total_chunks": 0,
            "chunks_processed": 0,
            "embeddings_created": 0,
            "embeddings_updated": 0,
            "embeddings_skipped": 0,
        }

    # Fetch existing embeddings map for these chunks
    chunk_ids = [c.id for c in chunks]
    existing_embeddings = (
        db.query(ChunkEmbedding)
        .filter(ChunkEmbedding.code_chunk_id.in_(chunk_ids))
        .all()
    )
    existing_map = {e.code_chunk_id: e for e in existing_embeddings}

    pending_items: list[tuple[CodeChunk, str, ChunkEmbedding | None]] = []
    skipped_count = 0

    for chunk in chunks:
        # Skip empty chunks
        if not chunk.content or not chunk.content.strip():
            skipped_count += 1
            continue

        c_hash = compute_content_hash(chunk.content)
        existing = existing_map.get(chunk.id)

        # Skip if already embedded with same content and model
        if (
            existing is not None
            and existing.content_hash == c_hash
            and existing.model_name == EMBEDDING_MODEL_NAME
        ):
            skipped_count += 1
        else:
            pending_items.append((chunk, c_hash, existing))

    created_count = 0
    updated_count = 0

    # Process pending items in batches for memory and execution efficiency
    for i in range(0, len(pending_items), batch_size):
        batch = pending_items[i : i + batch_size]
        batch_texts = [item[0].content for item in batch]
        batch_vectors = generate_embeddings_batch(batch_texts)

        for (chunk, c_hash, existing), vector in zip(batch, batch_vectors, strict=True):
            if existing is not None:
                existing.embedding = vector
                existing.content_hash = c_hash
                existing.model_name = EMBEDDING_MODEL_NAME
                existing.embedding_dimension = EMBEDDING_DIMENSION
                updated_count += 1
            else:
                embedding_record = ChunkEmbedding(
                    code_chunk_id=chunk.id,
                    embedding=vector,
                    model_name=EMBEDDING_MODEL_NAME,
                    embedding_dimension=EMBEDDING_DIMENSION,
                    content_hash=c_hash,
                )
                db.add(embedding_record)
                created_count += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "repository_id": repository_id,
        "total_chunks": total_chunks,
        "chunks_processed": len(pending_items),
        "embeddings_created": created_count,
        "embeddings_updated": updated_count,
        "embeddings_skipped": skipped_count,
    }


def get_embedding_status_for_repository(
    db: Session,
    repository_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Get embedding coverage status for a repository.
    """
    total_chunks = (
        db.query(CodeChunk)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .count()
    )

    embedded_chunks = (
        db.query(ChunkEmbedding)
        .join(CodeChunk, ChunkEmbedding.code_chunk_id == CodeChunk.id)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .count()
    )

    return {
        "repository_id": repository_id,
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "remaining_chunks": max(0, total_chunks - embedded_chunks),
        "model_name": EMBEDDING_MODEL_NAME,
        "embedding_dimension": EMBEDDING_DIMENSION,
    }
