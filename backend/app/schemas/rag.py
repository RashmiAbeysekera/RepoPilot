"""
Pydantic schemas for the Day 8 RAG (Retrieval-Augmented Generation) API.
"""

import uuid
from pydantic import BaseModel, ConfigDict, Field


class RAGQuestionRequest(BaseModel):
    """
    Request payload for asking a question about an indexed repository.
    """

    query: str = Field(
        ...,
        description="Natural language question about the repository codebase",
        examples=["How does user authentication work in this repository?"],
    )
    top_k: int = Field(
        default=5,
        description="Number of top relevant chunks to retrieve as context (1-10)",
        ge=1,
        le=10,
    )


class RAGSourceReference(BaseModel):
    """
    Metadata tracing an answer back to a retrieved repository chunk.
    """

    chunk_id: uuid.UUID
    repository_file_id: uuid.UUID
    file_path: str
    chunk_index: int
    start_line: int
    end_line: int
    score: float = Field(
        ...,
        description="Vector relevance score bounded between 0.0 and 1.0",
    )
    content: str = Field(
        ...,
        description="Actual code chunk content retrieved from repository",
    )

    model_config = ConfigDict(from_attributes=True)


class RAGAnswerResponse(BaseModel):
    """
    Response payload containing the grounded AI answer and source code references.
    """

    repository_id: uuid.UUID
    query: str
    answer: str
    sources: list[RAGSourceReference]
    model_name: str = Field(
        ...,
        description="Gemini model identifier used for generation",
    )

    model_config = ConfigDict(from_attributes=True)
