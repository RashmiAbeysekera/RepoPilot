"""
Semantic Search Service — Vector similarity search over repository code chunks.

RESPONSIBILITIES:
  - Validate and normalize search queries and top_k bounds
  - Verify repository existence and embedding status
  - Generate 384-dimensional query embedding using the existing local embedding model
  - Execute PostgreSQL + pgvector vector distance query scoped strictly to the requested repository
  - Convert pgvector cosine distance to a clear [0.0, 1.0] similarity score
  - Return developer metadata and relevant source code chunks
"""

import logging
import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import embedding_service

logger = logging.getLogger("repopilot.search")


def search_repository_chunks(
    db: Session,
    repository_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Perform semantic vector similarity search for a query against code chunks of a single repository.

    Args:
        db: Active SQLAlchemy database session.
        repository_id: UUID of the repository to search.
        query: Natural language query string.
        top_k: Maximum number of results to return (1-20).

    Returns:
        Dict containing query metadata and top_k matching results with relevance scores.

    Raises:
        ValueError: If repository does not exist, query is invalid, top_k is out of range,
                   or repository has chunks but no vector embeddings generated yet.
    """
    # 1. Validate query string
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty or whitespace-only.")

    query_clean = query.strip()

    # 2. Validate top_k parameter
    if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
        raise ValueError("top_k must be an integer between 1 and 20.")

    # 3. Verify repository exists
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if repo is None:
        raise ValueError(f"Repository '{repository_id}' not found.")

    # 4. Check chunk and embedding coverage for the repository
    total_chunks = (
        db.query(func.count(CodeChunk.id))
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .scalar()
        or 0
    )

    if total_chunks == 0:
        logger.info("Search requested for repo '%s' with 0 code chunks.", repository_id)
        return {
            "repository_id": repository_id,
            "query": query_clean,
            "top_k": top_k,
            "total_results": 0,
            "results": [],
        }

    total_embeddings = (
        db.query(func.count(ChunkEmbedding.id))
        .join(CodeChunk, ChunkEmbedding.code_chunk_id == CodeChunk.id)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .scalar()
        or 0
    )

    if total_embeddings == 0:
        logger.warning(
            "Search rejected for repo '%s': %d chunks exist but 0 embeddings generated.",
            repository_id,
            total_chunks,
        )
        raise ValueError("Repository has not been embedded yet. Please generate embeddings first.")

    # 5. Generate query vector using local embedding model (all-MiniLM-L6-v2)
    logger.info(
        "Generating query embedding for repo '%s' (query length: %d, top_k: %d)...",
        repository_id,
        len(query_clean),
        top_k,
    )
    query_vectors = embedding_service.generate_embeddings_batch([query_clean])
    if not query_vectors:
        raise ValueError("Failed to generate embedding for the search query.")
    query_vector = query_vectors[0]

    # 6. Perform pgvector cosine distance query database-side with repository scoping
    # pgvector operator <=> computes cosine distance: d in [0, 2]
    # Cosine Similarity S = 1.0 - d (since vectors are L2-normalized)
    distance_col = ChunkEmbedding.embedding.cosine_distance(query_vector).label("distance")

    results_raw = (
        db.query(
            CodeChunk,
            RepositoryFile.id.label("repository_file_id"),
            RepositoryFile.path.label("file_path"),
            distance_col,
        )
        .join(ChunkEmbedding, ChunkEmbedding.code_chunk_id == CodeChunk.id)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .order_by(distance_col)
        .limit(top_k)
        .all()
    )

    # 7. Format results and convert cosine distance to bounded similarity score [0.0, 1.0]
    formatted_results = []
    for chunk, file_id, file_path, distance in results_raw:
        # Distance value from pgvector: lower is closer.
        # Clamp score in range [0.0, 1.0] and round to 4 decimals for precision.
        raw_dist = float(distance) if distance is not None else 1.0
        score = round(max(0.0, min(1.0, 1.0 - raw_dist)), 4)

        formatted_results.append({
            "chunk_id": chunk.id,
            "repository_file_id": file_id,
            "file_path": file_path,
            "chunk_index": chunk.chunk_index,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
            "score": score,
        })

    logger.info(
        "Search completed for repo '%s': retrieved %d chunks (top_k=%d).",
        repository_id,
        len(formatted_results),
        top_k,
    )

    return {
        "repository_id": repository_id,
        "query": query_clean,
        "top_k": top_k,
        "total_results": len(formatted_results),
        "results": formatted_results,
    }
