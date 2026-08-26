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
from app.schemas.repository import RepositoryCreate, RepositoryResponse
from app.services import repository_service

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


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
