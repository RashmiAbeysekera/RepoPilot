"""
Pydantic schemas for CodeChunk API requests and responses.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class CodeChunkMetadataResponse(BaseModel):
    """
    Lightweight schema for listing code chunks. Excludes full chunk content.
    """

    id: uuid.UUID
    repository_file_id: uuid.UUID
    file_path: str = ""
    file_name: str = ""
    chunk_index: int
    start_line: int
    end_line: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CodeChunkDetailResponse(CodeChunkMetadataResponse):
    """
    Detailed schema for a single code chunk, including full text content.
    """

    content: str


class CodeChunkListResponse(BaseModel):
    """
    Container schema for chunk list responses.
    """

    repository_id: uuid.UUID
    total_chunks: int
    chunks: list[CodeChunkMetadataResponse]


class ChunkGenerationResponse(BaseModel):
    """
    Response schema after triggering chunk generation for a repository or file.
    """

    repository_id: uuid.UUID
    files_processed: int
    chunks_created: int
