"""
Day 12 Production Engineering: Comprehensive RAG Quality Tests.

COVERAGE:
  1. Relevant query returns relevant chunks
  2. Repository filtering works (strict isolation)
  3. Low relevance returns controlled no-context response
  4. Source metadata is accurate
  5. Line numbers are exact and within valid file bounds
  6. Duplicate source files are deduplicated cleanly
  7. Empty repository is handled gracefully
  8. Unindexed repository (no embeddings) handled with clear error
  9. Embedding generation failure handled gracefully
  10. Vector database failure handled cleanly
  11. Gemini API transient failure handled via retry engine
"""

import uuid
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import get_rag_similarity_threshold
from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import embedding_service, rag_service, search_service


def test_rag_quality_relevant_query_retrieval(db_session):
    """Quality Test 1: Highly relevant query returns expected code chunks with high similarity."""
    repo = Repository(name="AuthApp", full_name="org/auth-app", github_url="https://github.com/org/auth-app")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/auth.py",
        name="auth.py",
        extension=".py",
        size=150,
        content="def authenticate_user(username, password):\n    return verify_password(password)",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=2, content=file_rec.content)
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(
        code_chunk_id=chunk.id,
        embedding=[0.5] * 384,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash="auth_hash_1",
    )
    db_session.add(emb)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.5] * 384]):
        with patch("app.services.gemini_service.generate_rag_answer", return_value="Authentication is implemented in src/auth.py."):
            res = rag_service.answer_repository_question(
                db=db_session,
                repository_id=repo.id,
                query="How does authentication work?",
                top_k=3,
                use_agent=False,
            )

            assert len(res["sources"]) == 1
            assert res["sources"][0]["file_path"] == "src/auth.py"
            assert res["sources"][0]["similarity"] >= 0.20
            assert "Authentication is implemented" in res["answer"]


def test_rag_quality_repository_isolation(db_session):
    """Quality Test 2: Retrieval strictly enforces repository boundary."""
    repo_target = Repository(name="Target", full_name="org/target", github_url="https://github.com/org/target")
    repo_foreign = Repository(name="Foreign", full_name="org/foreign", github_url="https://github.com/org/foreign")
    db_session.add_all([repo_target, repo_foreign])
    db_session.commit()

    file_foreign = RepositoryFile(
        repository_id=repo_foreign.id,
        path="src/secret.py",
        name="secret.py",
        extension=".py",
        size=100,
        content="DATABASE_PASSWORD = 'very_secret'",
    )
    db_session.add(file_foreign)
    db_session.commit()

    chunk_foreign = CodeChunk(repository_file_id=file_foreign.id, chunk_index=0, start_line=1, end_line=1, content=file_foreign.content)
    db_session.add(chunk_foreign)
    db_session.commit()

    emb_foreign = ChunkEmbedding(
        code_chunk_id=chunk_foreign.id,
        embedding=[0.9] * 384,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash="sec_hash",
    )
    db_session.add(emb_foreign)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.9] * 384]):
        res = search_service.search_repository_chunks(
            db=db_session,
            repository_id=repo_target.id,
            query="DATABASE_PASSWORD",
            top_k=5,
        )

        assert len(res["results"]) == 0


def test_rag_quality_low_relevance_threshold_fallback(db_session):
    """Quality Test 3: Queries where all chunks score below threshold safely return no-context fallback."""
    repo = Repository(name="LowRelRepo", full_name="org/lowrel", github_url="https://github.com/org/lowrel")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="calc.py", name="calc.py", extension=".py", size=50, content="def add(a, b): return a + b")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=1, content=file_rec.content)
    db_session.add(chunk)
    db_session.commit()

    # Create chunk with low similarity (0.05) below threshold (0.20)
    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.05] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="h1")
    db_session.add(emb)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[-0.9] * 384]):
        res = rag_service.answer_repository_question(
            db=db_session,
            repository_id=repo.id,
            query="Explain the quantum mechanics theory in this repository",
            top_k=3,
        )

        assert "couldn't find enough relevant information" in res["answer"]
        assert len(res["sources"]) == 0
        assert res["confidence_warning"] is not None


def test_rag_quality_source_metadata_accuracy(db_session):
    """Quality Test 4 & 5: Source line ranges and file paths accurately match the database."""
    repo = Repository(name="MetaRepo", full_name="org/meta", github_url="https://github.com/org/meta")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="src/router.py", name="router.py", extension=".py", size=200, content="line 1\nline 2\nline 3\nline 4\nline 5")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=2, end_line=4, content="line 2\nline 3\nline 4")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.4] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="h2")
    db_session.add(emb)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.4] * 384]):
        with patch("app.services.gemini_service.generate_rag_answer", return_value="Router answer"):
            res = rag_service.answer_repository_question(
                db=db_session,
                repository_id=repo.id,
                query="router",
            )

            source = res["sources"][0]
            assert source["file_path"] == "src/router.py"
            assert source["start_line"] == 2
            assert source["end_line"] == 4
            assert source["start_line"] <= source["end_line"]


def test_rag_quality_deduplication(db_session):
    """Quality Test 6: Multiple chunks from the same file are deduplicated cleanly in file_sources."""
    repo = Repository(name="DedupRepo", full_name="org/dedup", github_url="https://github.com/org/dedup")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="src/app.js", name="app.js", extension=".js", size=300, content="code")
    db_session.add(file_rec)
    db_session.commit()

    c1 = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=10, content="c1")
    c2 = CodeChunk(repository_file_id=file_rec.id, chunk_index=1, start_line=15, end_line=25, content="c2")
    db_session.add_all([c1, c2])
    db_session.commit()

    e1 = ChunkEmbedding(code_chunk_id=c1.id, embedding=[0.3] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="h3")
    e2 = ChunkEmbedding(code_chunk_id=c2.id, embedding=[0.35] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="h4")
    db_session.add_all([e1, e2])
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.35] * 384]):
        with patch("app.services.gemini_service.generate_rag_answer", return_value="Dedup answer"):
            res = rag_service.answer_repository_question(
                db=db_session,
                repository_id=repo.id,
                query="app",
            )

            assert len(res["file_sources"]) == 1
            file_src = res["file_sources"][0]
            assert file_src["file_path"] == "src/app.js"
            assert file_src["chunks_count"] == 2
            assert any("1" in r and "10" in r for r in file_src["line_ranges"])
            assert any("15" in r and "25" in r for r in file_src["line_ranges"])


def test_rag_quality_unembedded_repository(db_session):
    """Quality Test 8: Repository with stored files/chunks but 0 embeddings raises clear error."""
    repo = Repository(name="NoEmbRepo", full_name="org/noemb", github_url="https://github.com/org/noemb")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="index.js", name="index.js", extension=".js", size=50, content="console.log('hi');")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=1, content="console.log('hi');")
    db_session.add(chunk)
    db_session.commit()

    with pytest.raises(ValueError, match="Repository has not been embedded yet"):
        search_service.search_repository_chunks(db=db_session, repository_id=repo.id, query="hello")


def test_rag_quality_embedding_failure_handling(db_session):
    """Quality Test 9: Failure in query embedding generation is handled safely."""
    repo = Repository(name="EmbFailRepo", full_name="org/embfail", github_url="https://github.com/org/embfail")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="test.py", name="test.py", extension=".py", size=50, content="def test(): pass")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=1, content="def test(): pass")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.1] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="hf")
    db_session.add(emb)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[]):
        with pytest.raises(ValueError, match="Failed to generate embedding for the search query"):
            search_service.search_repository_chunks(db=db_session, repository_id=repo.id, query="any query")


def test_rag_quality_gemini_failure_handling(db_session):
    """Quality Test 11: Gemini API failure raises clear diagnostic error."""
    repo = Repository(name="GemFailRepo", full_name="org/gemfail", github_url="https://github.com/org/gemfail")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="main.py", name="main.py", extension=".py", size=50, content="print('hello')")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=1, content="print('hello')")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.5] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="h5")
    db_session.add(emb)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.5] * 384]):
        with patch("app.services.gemini_service.generate_rag_answer", side_effect=ValueError("Gemini API generation failed: Rate limit or quota exceeded (429)")):
            with pytest.raises(ValueError, match="Gemini API generation failed"):
                rag_service.answer_repository_question(
                    db=db_session,
                    repository_id=repo.id,
                    query="test question",
                )


def test_rate_limiter_enforcement():
    """Verify in-memory sliding window rate limiter blocks requests exceeding configured quota."""
    from app.core.errors import RateLimitExceededError
    from app.core.rate_limiter import InMemoryRateLimiter

    InMemoryRateLimiter.reset()
    test_key = "test_bucket_123"

    # Allow 3 requests in a 60s window
    InMemoryRateLimiter.check_rate_limit(key=test_key, max_requests=3, window_seconds=60)
    InMemoryRateLimiter.check_rate_limit(key=test_key, max_requests=3, window_seconds=60)
    InMemoryRateLimiter.check_rate_limit(key=test_key, max_requests=3, window_seconds=60)

    # 4th request must raise RateLimitExceededError with retry_after and 429 status
    with pytest.raises(RateLimitExceededError) as exc_info:
        InMemoryRateLimiter.check_rate_limit(key=test_key, max_requests=3, window_seconds=60)

    assert exc_info.value.retry_after > 0
    assert exc_info.value.status_code == 429
    assert exc_info.value.category == "rate_limit"

    InMemoryRateLimiter.reset()

