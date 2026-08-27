"""
Chunking Service — Line-based code chunking and persistence.

RESPONSIBILITIES:
  - Divide source/documentation files into smaller text chunks
  - Deterministic line-based chunking with configurable size & overlap
  - Preserve start_line and end_line line numbers for future RAG citations
  - Handle empty, small (<= CHUNK_SIZE_LINES), and large files gracefully
  - Perform safe, idempotent derived-data regeneration (delete old, insert new)
  - Ensure zero external network calls (pure PostgreSQL <-> memory operation)
"""

import uuid
from typing import Any
from sqlalchemy.orm import Session

from app.models.code_chunk import CodeChunk
from app.models.repository_file import RepositoryFile

CHUNK_SIZE_LINES = 100
CHUNK_OVERLAP_LINES = 10


def split_text_into_chunks(
    content: str | None,
    chunk_size: int = CHUNK_SIZE_LINES,
    chunk_overlap: int = CHUNK_OVERLAP_LINES,
) -> list[dict[str, Any]]:
    """
    Split raw file content into line-based chunks.

    Args:
        content: Raw text content of the file.
        chunk_size: Target number of lines per chunk (default 100).
        chunk_overlap: Number of overlapping lines between consecutive chunks (default 10).

    Returns:
        A list of dicts containing chunk metadata and text content:
        [
            {
                "chunk_index": 0,
                "start_line": 1,
                "end_line": 100,
                "content": "..."
            },
            ...
        ]
    """
    if not content or not content.strip():
        return []

    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return []

    # Small files: if file has fewer or equal lines to chunk_size, return 1 single chunk
    if total_lines <= chunk_size:
        return [
            {
                "chunk_index": 0,
                "start_line": 1,
                "end_line": total_lines,
                "content": "\n".join(lines),
            }
        ]

    # Large files: chunk with overlap
    chunks: list[dict[str, Any]] = []
    step = max(1, chunk_size - chunk_overlap)
    chunk_idx = 0
    start_idx = 0

    while start_idx < total_lines:
        end_idx = min(start_idx + chunk_size, total_lines)
        chunk_lines = lines[start_idx:end_idx]

        chunks.append({
            "chunk_index": chunk_idx,
            "start_line": start_idx + 1,  # 1-indexed
            "end_line": end_idx,          # 1-indexed inclusive
            "content": "\n".join(chunk_lines),
        })

        chunk_idx += 1
        start_idx += step

    return chunks


def generate_chunks_for_file(db: Session, file_record: RepositoryFile) -> list[CodeChunk]:
    """
    Idempotently generate and save code chunks for a single RepositoryFile.

    Existing chunks for this file are deleted before inserting new chunks.
    """
    # Delete existing chunks for this file
    db.query(CodeChunk).filter(CodeChunk.repository_file_id == file_record.id).delete()

    raw_chunks = split_text_into_chunks(file_record.content)
    created_chunks: list[CodeChunk] = []

    for raw in raw_chunks:
        chunk = CodeChunk(
            repository_file_id=file_record.id,
            chunk_index=raw["chunk_index"],
            start_line=raw["start_line"],
            end_line=raw["end_line"],
            content=raw["content"],
        )
        db.add(chunk)
        created_chunks.append(chunk)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return created_chunks


def generate_chunks_for_repository(
    db: Session,
    repository_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Generate code chunks for all stored files in a repository.

    Returns summary stats:
    {
        "repository_id": repository_id,
        "files_processed": X,
        "chunks_created": Y
    }
    """
    files = (
        db.query(RepositoryFile)
        .filter(RepositoryFile.repository_id == repository_id)
        .all()
    )

    if not files:
        return {
            "repository_id": repository_id,
            "files_processed": 0,
            "chunks_created": 0,
        }

    file_ids = [f.id for f in files]

    # Delete all existing chunks for files in this repository safely
    db.query(CodeChunk).filter(CodeChunk.repository_file_id.in_(file_ids)).delete(
        synchronize_session=False
    )

    total_chunks_created = 0

    for file_record in files:
        raw_chunks = split_text_into_chunks(file_record.content)
        for raw in raw_chunks:
            chunk = CodeChunk(
                repository_file_id=file_record.id,
                chunk_index=raw["chunk_index"],
                start_line=raw["start_line"],
                end_line=raw["end_line"],
                content=raw["content"],
            )
            db.add(chunk)
            total_chunks_created += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "repository_id": repository_id,
        "files_processed": len(files),
        "chunks_created": total_chunks_created,
    }


def list_chunks_for_repository(
    db: Session,
    repository_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Return all code chunks for a repository with file metadata (path, name).
    Excludes full content payload for efficiency.
    """
    results = (
        db.query(CodeChunk, RepositoryFile.path, RepositoryFile.name)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(RepositoryFile.repository_id == repository_id)
        .order_by(RepositoryFile.path.asc(), CodeChunk.chunk_index.asc())
        .all()
    )

    chunks_list: list[dict[str, Any]] = []
    for chunk, path, name in results:
        chunks_list.append({
            "id": chunk.id,
            "repository_file_id": chunk.repository_file_id,
            "file_path": path,
            "file_name": name,
            "chunk_index": chunk.chunk_index,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "created_at": chunk.created_at,
        })

    return chunks_list


def get_chunk_by_id(
    db: Session,
    repository_id: uuid.UUID,
    chunk_id: uuid.UUID,
) -> dict[str, Any] | None:
    """
    Retrieve a single CodeChunk with full text content, verifying ownership by repository_id.
    """
    result = (
        db.query(CodeChunk, RepositoryFile.path, RepositoryFile.name)
        .join(RepositoryFile, CodeChunk.repository_file_id == RepositoryFile.id)
        .filter(
            RepositoryFile.repository_id == repository_id,
            CodeChunk.id == chunk_id,
        )
        .first()
    )

    if result is None:
        return None

    chunk, path, name = result
    return {
        "id": chunk.id,
        "repository_file_id": chunk.repository_file_id,
        "file_path": path,
        "file_name": name,
        "chunk_index": chunk.chunk_index,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "created_at": chunk.created_at,
        "content": chunk.content,
    }
