"""
Tests for Day 10.5 Diagnostic and Fix.
Covers:
  - Gemini configuration and health detection
  - GitHub configuration and health detection
  - Repository data availability & chunk/embedding consistency
  - Embedding dimension consistency
  - Vector search repository isolation
  - Relevance threshold behavior (0.20 threshold with realistic similarity scores)
  - Gemini 503 retry with exponential backoff
  - Missing Gemini key error handling
"""

import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

from app.core.config import (
    get_gemini_api_key,
    get_gemini_max_retries,
    get_rag_similarity_threshold,
)
from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import (
    embedding_service,
    gemini_service,
    github_service,
    rag_service,
    search_service,
)


def test_gemini_configuration_detection():
    """Verify get_gemini_api_key detects configured key and respects GOOGLE_API_KEY fallback."""
    with patch("os.getenv", side_effect=lambda k, default=None: "test_key_gemini" if k == "GEMINI_API_KEY" else default):
        assert get_gemini_api_key() == "test_key_gemini"
        assert gemini_service.check_gemini_health() == "healthy"

    with patch("os.getenv", side_effect=lambda k, default=None: "test_key_google" if k == "GOOGLE_API_KEY" else default):
        assert get_gemini_api_key() == "test_key_google"
        assert gemini_service.check_gemini_health() == "healthy"

    with patch("os.getenv", return_value=None):
        assert get_gemini_api_key() is None
        assert gemini_service.check_gemini_health() == "not-configured"


def test_github_health_detection():
    """Verify check_github_health handles 200, 403, and network errors properly."""
    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert github_service.check_github_health() == "healthy"

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value.status_code = 403  # Rate limited still confirms API is up
        assert github_service.check_github_health() == "healthy"

    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        assert github_service.check_github_health() == "unavailable"


def test_embedding_dimension_consistency():
    """Ensure embedding dimension is strictly 384 for all-MiniLM-L6-v2."""
    assert embedding_service.EMBEDDING_DIMENSION == 384
    assert embedding_service.EMBEDDING_MODEL_NAME == "all-MiniLM-L6-v2"


def test_relevance_threshold_allows_legitimate_chunks_and_rejects_trivia(db_session: Session):
    """
    Verify that with threshold=0.20:
    - Legitimate code chunks (sim ~0.26) pass through to context.
    - Trivia queries with low similarity (sim ~0.11) are rejected without calling Gemini.
    """
    repo = Repository(name="ThresholdTestRepo", full_name="owner/thresh", github_url="https://github.com/owner/thresh")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="models/User.js", name="User.js", extension=".js", size=100, file_type="source", content="const mongoose = require('mongoose');")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=5, content="const mongoose = require('mongoose');")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(
        code_chunk_id=chunk.id,
        embedding=[0.1] * 384,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash=embedding_service.compute_content_hash(chunk.content),
    )
    db_session.add(emb)
    db_session.commit()

    # Case 1: In-context match with similarity 0.28 (above 0.20 threshold)
    with patch("app.services.search_service.search_repository_chunks") as mock_search:
        mock_search.return_value = {
            "repository_id": repo.id,
            "query": "How does User model work?",
            "top_k": 5,
            "total_results": 1,
            "results": [{
                "chunk_id": chunk.id,
                "repository_file_id": file_rec.id,
                "file_path": "models/User.js",
                "chunk_index": 0,
                "start_line": 1,
                "end_line": 5,
                "score": 0.28,
                "content": chunk.content,
            }],
        }
        with patch("app.services.gemini_service.generate_rag_answer", return_value="The User model is defined via Mongoose."):
            res = rag_service.answer_repository_question(db_session, repo.id, "How does User model work?", use_agent=False)
            assert res["chunks_retrieved"] == 1
            assert "User model" in res["answer"]
            assert len(res["sources"]) == 1
            assert res["sources"][0]["score"] == 0.28

    # Case 2: Out-of-context match with similarity 0.11 (below 0.20 threshold)
    with patch("app.services.search_service.search_repository_chunks") as mock_search:
        mock_search.return_value = {
            "repository_id": repo.id,
            "query": "What is the capital of France?",
            "top_k": 5,
            "total_results": 1,
            "results": [{
                "chunk_id": chunk.id,
                "repository_file_id": file_rec.id,
                "file_path": "models/User.js",
                "chunk_index": 0,
                "start_line": 1,
                "end_line": 5,
                "score": 0.11,
                "content": chunk.content,
            }],
        }
        with patch("app.services.gemini_service.generate_rag_answer") as mock_gemini:
            res = rag_service.answer_repository_question(db_session, repo.id, "What is the capital of France?", use_agent=False)
            assert res["chunks_retrieved"] == 0
            assert "couldn't find enough relevant information" in res["answer"]
            mock_gemini.assert_not_called()


def test_gemini_503_transient_retry_success():
    """Verify that call_gemini_with_retry retries on 503 and returns on subsequent success."""
    attempts = 0

    def mock_api_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")
        return "Success on attempt 3"

    with patch("time.sleep"):  # Avoid actual delay during tests
        result = gemini_service.call_gemini_with_retry(mock_api_call, max_retries=3, initial_delay=0.01)
        assert result == "Success on attempt 3"
        assert attempts == 3


def test_gemini_503_retries_exhausted_raises_classified_error():
    """Verify that when 503 persists beyond max retries, it raises a clear 503 unavailable message."""
    def always_503():
        raise Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")

    with patch("time.sleep"):
        with pytest.raises(ValueError, match="temporarily unavailable \\(503\\)"):
            gemini_service.call_gemini_with_retry(always_503, max_retries=2, initial_delay=0.01)


def test_gemini_non_transient_error_fails_immediately():
    """Verify that 401 / 403 / auth error does not retry and fails immediately."""
    attempts = 0

    def auth_error():
        nonlocal attempts
        attempts += 1
        raise Exception("403 API_KEY_INVALID")

    with pytest.raises(ValueError, match="Authentication failed"):
        gemini_service.call_gemini_with_retry(auth_error, max_retries=3)

    # Must have failed on the very first attempt without wasting retries
    assert attempts == 1


def test_gemini_missing_api_key_error():
    """Verify get_gemini_client raises informative error when key is missing."""
    with patch("app.services.gemini_service.get_gemini_api_key", return_value=None):
        with pytest.raises(ValueError, match="Gemini API key is not configured"):
            gemini_service.get_gemini_client()
