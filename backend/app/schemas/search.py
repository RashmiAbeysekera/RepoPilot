"""
Pydantic schemas for the Semantic Search API.
"""

import uuid
from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """
    Request body for repository semantic search.
    """

    query: str = Field(
        ...,
        description="Natural language query string",
        examples=["Where is user authentication implemented?"],
    )
    top_k: int = Field(
        default=5,
        description="Maximum number of relevant chunks to return (1-20)",
        ge=1,
        le=20,
    )


class SearchResultItem(BaseModel):
    """
    A single code chunk search result with similarity score and developer metadata.
    """

    chunk_id: uuid.UUID
    repository_file_id: uuid.UUID
    file_path: str
    chunk_index: int
    start_line: int
    end_line: int
    content: str
    score: float = Field(
        ...,
        description="Cosine similarity score bounded between 0.0 and 1.0 (higher means more relevant)",
    )

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """
    Response body returned by the semantic search endpoint.
    """

    repository_id: uuid.UUID
    query: str
    top_k: int
    total_results: int
    results: list[SearchResultItem]
