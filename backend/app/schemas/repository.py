"""
Pydantic schemas for the repositories API.

SCHEMA vs MODEL:
  - SQLAlchemy models (in app/models/) represent database rows.
  - Pydantic schemas (here) represent what the API *accepts* and *returns*.

This separation lets us:
  - Accept only a subset of fields on creation (user doesn't supply timestamps/IDs)
  - Return only safe fields in responses (we could hide internal fields)
  - Validate and coerce incoming data automatically

Pydantic validates every field on instantiation. If the data doesn't match
the declared type or constraints, it raises a 422 Unprocessable Entity error
before our code even runs — we get validation for free.
"""

import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class RepositoryCreate(BaseModel):
    """
    Schema for POST /api/repositories request body.

    The user only needs to provide the GitHub URL. We parse the owner,
    repo name, and full_name from it in the service layer.
    We keep optional fields (description, default_branch) so the user can
    supply them manually if they're not connecting to GitHub's API yet.
    """

    github_url: AnyHttpUrl = Field(
        ...,
        description="Full HTTPS URL to the GitHub repository.",
        examples=["https://github.com/owner/repository"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional description of the repository.",
    )
    default_branch: str = Field(
        default="main",
        max_length=100,
        description="Default branch name (defaults to 'main').",
    )


class RepositoryResponse(BaseModel):
    """
    Schema for repository responses.

    This is what the API returns — a safe, typed snapshot of a repository.
    We include all useful fields but exclude internal implementation details
    (like raw database connection state).

    model_config = {"from_attributes": True} tells Pydantic it can read
    attribute values directly from a SQLAlchemy model instance (which uses
    attribute access, not dict-style access). This makes conversion seamless:
        RepositoryResponse.model_validate(db_repository_instance)
    """

    id: uuid.UUID
    name: str
    full_name: str
    github_url: str
    description: str | None
    default_branch: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
