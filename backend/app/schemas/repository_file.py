"""
Pydantic schemas for RepositoryFile resources.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel


class RepositoryFileResponse(BaseModel):
    """
    Lightweight schema for listing repository files. Excludes full text content.
    """

    id: uuid.UUID
    repository_id: uuid.UUID
    path: str
    name: str
    extension: str
    size: int
    file_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryFileDetailResponse(RepositoryFileResponse):
    """
    Detailed schema for a single file, including text content.
    """

    content: str | None = None


class RepositoryFileListResponse(BaseModel):
    """
    Container schema for file list responses.
    """

    repository_id: uuid.UUID
    total_files: int
    files: list[RepositoryFileResponse]
