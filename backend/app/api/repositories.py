"""
FastAPI router for the /api/repositories resource.

ROUTER RESPONSIBILITY:
  - Parse and validate HTTP requests (Pydantic does this automatically)
  - Call the service layer to do the actual work
  - Return the correct HTTP status code and response body
  - Handle known errors gracefully (404, 400, etc.)

What the router does NOT do:
  - Write SQL queries directly
  - Contain business rules or duplicate-detection logic
  - Know anything about how data is stored

DEPENDENCY INJECTION:
  FastAPI's `Depends(get_db)` automatically opens a database session before
  each request and closes it after — we don't manage that lifecycle manually.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.chunk_embedding import (
    EmbeddingGenerationResponse,
    EmbeddingStatusResponse,
)
from app.schemas.code_chunk import (
    ChunkGenerationResponse,
    CodeChunkDetailResponse,
    CodeChunkListResponse,
    CodeChunkMetadataResponse,
)
from app.schemas.repository import (
    RepositoryCreate,
    RepositoryImportRequest,
    RepositoryIngestResponse,
    RepositoryResponse,
)
from app.schemas.repository_file import (
    RepositoryFileDetailResponse,
    RepositoryFileListResponse,
    RepositoryFileResponse,
)
from app.services import (
    chunking_service,
    embedding_service,
    github_service,
    repository_ingestion_service,
    repository_service,
)

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


@router.post(
    "/import",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a public GitHub repository",
)
def import_repository(
    data: RepositoryImportRequest,
    db: Session = Depends(get_db),
) -> RepositoryResponse:
    """
    Import a public GitHub repository by URL.
    Fetches live repository metadata from GitHub REST API and saves to PostgreSQL.
    """
    try:
        repository = repository_service.import_repository_from_github(db, data.github_url)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return RepositoryResponse.model_validate(repository)


@router.post(
    "/{repository_id}/ingest",
    response_model=RepositoryIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest and persist repository file tree",
)
def ingest_repository(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RepositoryIngestResponse:
    """
    Discover, filter, and inspect source files in a saved repository via GitHub REST API,
    persisting RepositoryFile records into PostgreSQL.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    try:
        summary = repository_ingestion_service.ingest_and_persist_repository(db, repository)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return RepositoryIngestResponse(
        repository_id=repository.id,
        repository=summary["repository"],
        default_branch=repository.default_branch,
        files_discovered=summary["files_discovered"],
        files_stored=summary["files_stored"],
        files_updated=summary["files_updated"],
        files_skipped=summary["files_skipped"],
        skip_reasons=summary["skip_reasons"],
        source_files=summary["source_files"],
        ignored_files=summary["ignored_files"],
        file_paths=summary["file_paths"],
    )


@router.get(
    "/{repository_id}/files",
    response_model=RepositoryFileListResponse,
    status_code=status.HTTP_200_OK,
    summary="List stored files for a repository",
)
def list_repository_files(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RepositoryFileListResponse:
    """
    Return all stored RepositoryFile records for the given repository.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    files = repository_service.list_repository_files(db, repository_id)
    return RepositoryFileListResponse(
        repository_id=repository_id,
        total_files=len(files),
        files=[RepositoryFileResponse.model_validate(f) for f in files],
    )


@router.get(
    "/{repository_id}/files/{file_id}",
    response_model=RepositoryFileDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single stored file with content",
)
def get_repository_file(
    repository_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RepositoryFileDetailResponse:
    """
    Return a single RepositoryFile record by ID, asserting it belongs to repository_id.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    file_record = repository_service.get_repository_file_by_id(db, repository_id, file_id)
    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_id}' not found in repository '{repository_id}'.",
        )

    return RepositoryFileDetailResponse.model_validate(file_record)


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a repository",
)
def create_repository(
    data: RepositoryCreate,
    db: Session = Depends(get_db),
) -> RepositoryResponse:
    """
    Add a new GitHub repository to RepoPilot.

    Returns 201 with the saved repository on success.
    Returns 400 if the repository URL already exists.
    Returns 422 if the request body fails validation (e.g. invalid URL).
    """
    try:
        repository = repository_service.create_repository(db, data)
    except ValueError as error:
        # ValueError from the service means a known business rule violation
        # (e.g. duplicate). Map it to 400 Bad Request.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return RepositoryResponse.model_validate(repository)



@router.get(
    "",
    response_model=list[RepositoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all repositories",
)
def list_repositories(db: Session = Depends(get_db)) -> list[RepositoryResponse]:
    """
    Return all saved repositories, newest first.
    """
    repositories = repository_service.list_repositories(db)
    return [RepositoryResponse.model_validate(r) for r in repositories]


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a repository by ID",
)
def get_repository(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RepositoryResponse:
    """
    Return a single repository by UUID.

    Returns 404 if no repository with that ID exists.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    return RepositoryResponse.model_validate(repository)


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a repository",
)
def delete_repository(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a repository by UUID.

    Returns 204 No Content on success (the resource no longer exists,
    so there is nothing to return).
    Returns 404 if no repository with that ID exists.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )
    repository_service.delete_repository(db, repository)


# --- Code Chunking Endpoints ----------------------------------------------

@router.post(
    "/{repository_id}/chunks/generate",
    response_model=ChunkGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate line-based code chunks for all repository files",
)
def generate_repository_chunks(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ChunkGenerationResponse:
    """
    Generate code chunks for all stored files in a repository.
    Idempotent operation — replaces previous chunks for the repository.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    stats = chunking_service.generate_chunks_for_repository(db, repository_id)
    return ChunkGenerationResponse(
        repository_id=repository_id,
        files_processed=stats["files_processed"],
        chunks_created=stats["chunks_created"],
    )


@router.post(
    "/{repository_id}/files/{file_id}/chunks/generate",
    response_model=ChunkGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate line-based code chunks for a single file",
)
def generate_file_chunks(
    repository_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ChunkGenerationResponse:
    """
    Generate code chunks for a single stored file.
    Verifies file ownership by repository_id.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    file_record = repository_service.get_repository_file_by_id(db, repository_id, file_id)
    if file_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_id}' not found in repository '{repository_id}'.",
        )

    created_chunks = chunking_service.generate_chunks_for_file(db, file_record)
    return ChunkGenerationResponse(
        repository_id=repository_id,
        files_processed=1,
        chunks_created=len(created_chunks),
    )


@router.get(
    "/{repository_id}/chunks",
    response_model=CodeChunkListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all chunks for a repository",
)
def list_repository_chunks(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CodeChunkListResponse:
    """
    Return metadata list of all code chunks generated for the given repository.
    Excludes full chunk text content for performance.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    chunks = chunking_service.list_chunks_for_repository(db, repository_id)
    return CodeChunkListResponse(
        repository_id=repository_id,
        total_chunks=len(chunks),
        chunks=[CodeChunkMetadataResponse.model_validate(c) for c in chunks],
    )


@router.get(
    "/{repository_id}/chunks/{chunk_id}",
    response_model=CodeChunkDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single chunk with full content",
)
def get_chunk_detail(
    repository_id: uuid.UUID,
    chunk_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CodeChunkDetailResponse:
    """
    Return full content and metadata for a single code chunk, asserting ownership by repository_id.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    chunk_dict = chunking_service.get_chunk_by_id(db, repository_id, chunk_id)
    if chunk_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chunk '{chunk_id}' not found in repository '{repository_id}'.",
        )

    return CodeChunkDetailResponse.model_validate(chunk_dict)


# --- Vector Embedding Endpoints -------------------------------------------

@router.post(
    "/{repository_id}/embeddings/generate",
    response_model=EmbeddingGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate vector embeddings for repository code chunks",
)
def generate_repository_embeddings(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EmbeddingGenerationResponse:
    """
    Generate 384-dimensional vector embeddings for all stored CodeChunk records in a repository.
    Idempotent operation — skips unchanged chunks using SHA-256 content hashes.
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    stats = embedding_service.generate_embeddings_for_repository(db, repository_id)
    return EmbeddingGenerationResponse(
        repository_id=repository_id,
        total_chunks=stats["total_chunks"],
        chunks_processed=stats["chunks_processed"],
        embeddings_created=stats["embeddings_created"],
        embeddings_updated=stats["embeddings_updated"],
        embeddings_skipped=stats["embeddings_skipped"],
    )


@router.get(
    "/{repository_id}/embeddings/status",
    response_model=EmbeddingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get embedding coverage status for a repository",
)
def get_embedding_status(
    repository_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EmbeddingStatusResponse:
    """
    Return embedding statistics for a repository (total chunks, embedded chunks, model name, vector dim).
    """
    repository = repository_service.get_repository_by_id(db, repository_id)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repository_id}' not found.",
        )

    stats = embedding_service.get_embedding_status_for_repository(db, repository_id)
    return EmbeddingStatusResponse(
        repository_id=repository_id,
        total_chunks=stats["total_chunks"],
        embedded_chunks=stats["embedded_chunks"],
        remaining_chunks=stats["remaining_chunks"],
        model_name=stats["model_name"],
        embedding_dimension=stats["embedding_dimension"],
    )


