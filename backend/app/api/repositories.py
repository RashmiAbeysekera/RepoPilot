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
from app.services import github_service, repository_ingestion_service, repository_service

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
