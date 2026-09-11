"""
Pydantic schemas for the Day 8 RAG (Retrieval-Augmented Generation) API.
"""

import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentTraceStep(BaseModel):
    """
    Chronological record of a tool action performed by the agent.
    Safe for developer display with zero sensitive credentials or internal prompts.
    """

    tool: str = Field(..., description="Name of the repository tool executed")
    input: dict[str, Any] | str = Field(..., description="Safe input parameters passed to the tool")
    result_summary: str = Field(..., description="Developer-safe summary of tool results")
    status: str = Field(default="success", description="Tool execution status: success, error, or blocked")
    duration_ms: int = Field(default=0, description="Duration of tool execution in milliseconds")

    model_config = ConfigDict(from_attributes=True)


class RAGQuestionRequest(BaseModel):
    """
    Request payload for asking a question about an indexed repository.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language question about the repository codebase",
        examples=["How does user authentication work in this repository?"],
    )
    top_k: int = Field(
        default=5,
        description="Number of top relevant chunks to retrieve as context (1-10)",
        ge=1,
        le=10,
    )
    use_agent: bool = Field(
        default=False,
        description="Whether to use the agentic investigation workflow (default: False)",
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty or whitespace only.")
        return cleaned


class RAGSourceReference(BaseModel):
    """
    Metadata tracing an answer back to a retrieved repository chunk.
    """

    chunk_id: uuid.UUID | None = None
    repository_file_id: uuid.UUID | None = None
    file_path: str
    chunk_index: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    similarity: float = Field(
        ...,
        description="Vector cosine similarity score bounded between 0.0 and 1.0",
    )
    score: float = Field(
        ...,
        description="Vector relevance score (preserved for backward compatibility)",
    )
    content: str | None = Field(
        default=None,
        description="Actual code chunk content retrieved from repository",
    )

    model_config = ConfigDict(from_attributes=True)


class RAGFileSource(BaseModel):
    """
    Deduplicated source summary grouped by repository file.
    Consolidates multiple chunks from the same file into combined line ranges.
    """

    file_path: str
    repository_file_id: uuid.UUID | None = None
    line_ranges: list[str] = Field(
        default_factory=list,
        description="Consolidated line ranges (e.g. ['18-42', '50-75'])",
    )
    max_similarity: float = Field(
        ...,
        description="Highest similarity score among retrieved chunks in this file",
    )
    chunks_count: int = Field(
        ...,
        description="Number of relevant chunks retrieved from this file",
    )

    model_config = ConfigDict(from_attributes=True)


class RAGAnswerResponse(BaseModel):
    """
    Response payload containing the grounded AI answer and source code references.
    """

    repository_id: uuid.UUID
    query: str
    answer: str
    sources: list[RAGSourceReference] = Field(
        default_factory=list,
        description="Chunk-level source references with line numbers and content",
    )
    file_sources: list[RAGFileSource] = Field(
        default_factory=list,
        description="Deduplicated file-level sources with consolidated line ranges",
    )
    model_name: str = Field(
        ...,
        description="Gemini model identifier used for generation",
    )
    chunks_retrieved: int = Field(
        default=0,
        description="Total number of chunks passing the relevance threshold",
    )
    confidence_warning: str | None = Field(
        default=None,
        description="Optional warning if retrieved context had low similarity",
    )
    trace: list[AgentTraceStep] = Field(
        default_factory=list,
        description="Safe chronological audit trail of agent actions and tools invoked",
    )
    duration_ms: int | None = Field(
        default=None,
        description="Total duration of retrieval and generation in milliseconds",
    )

    model_config = ConfigDict(from_attributes=True)
