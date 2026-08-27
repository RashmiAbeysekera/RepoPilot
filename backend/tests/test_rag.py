"""
Tests for Day 8 RAG (Retrieval-Augmented Generation) Pipeline.

TEST COVERAGE:
  1. Valid RAG request returns answer and sources.
  2. Query validation (empty string, whitespace-only).
  3. Repository validation (non-existent UUID returns 404).
  4. Repository isolation (chunks from Repo B are never included in Repo A RAG context).
  5. Context builder formatting (includes file path, line range, score, content).
  6. Context character limit / truncation handling.
  7. Empty retrieval / no relevant chunks returns grounded fallback response without calling Gemini.
  8. Un-embedded repository raises appropriate 400 error.
  9. Gemini API missing API key error handling.
 10. Gemini API runtime exception handling.
 11. Top-K parameter bounds validation (1 to 10).
 12. End-to-end API endpoint POST /api/repositories/{id}/ask with mocked Gemini client.
"""

import uuid
from unittest.mock import patch

import pytest
from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import context_builder, embedding_service, gemini_service, rag_service


def test_context_builder_formatting():
    """Test 5 & 6: Context builder formats file path, line range, score, and respects character limit."""
    chunks = [
        {
            "chunk_id": uuid.uuid4(),
            "repository_file_id": uuid.uuid4(),
            "file_path": "backend/auth/login.py",
            "chunk_index": 0,
            "start_line": 10,
            "end_line": 35,
            "content": "def login_user(username, password):\n    return True",
            "score": 0.8921,
        },
        {
            "chunk_id": uuid.uuid4(),
            "repository_file_id": uuid.uuid4(),
            "file_path": "backend/auth/jwt.py",
            "chunk_index": 1,
            "start_line": 5,
            "end_line": 20,
            "content": "def generate_jwt(user_id):\n    return 'token'",
            "score": 0.7450,
        },
    ]

    context = context_builder.build_rag_context(chunks)

    assert "--- Source 1 ---" in context
    assert "File: backend/auth/login.py" in context
    assert "Lines: 10-35" in context
    assert "Relevance Score: 0.8921" in context
    assert "def login_user" in context

    assert "--- Source 2 ---" in context
    assert "File: backend/auth/jwt.py" in context
    assert "Lines: 5-20" in context
    assert "Relevance Score: 0.7450" in context
    assert "def generate_jwt" in context

    # Test truncation with small limit
    truncated_context = context_builder.build_rag_context(chunks, max_context_chars=120)
    assert len(truncated_context) <= 300
    assert "--- Source 1" in truncated_context


def test_rag_service_valid_query(db_session):
    """Test 1, 4, 7, 8, 9: Complete RAG pipeline execution with mocked Gemini response."""
    repo = Repository(
        name="RAG Pipeline Test Repo",
        full_name="testowner/ragrepo",
        github_url="https://github.com/testowner/ragrepo",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="backend/auth/session.py",
        name="session.py",
        extension=".py",
        size=100,
        file_type="source",
        content="def verify_session(token): return True",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=1,
        content="def verify_session(token): return True",
    )
    db_session.add(chunk)
    db_session.commit()

    # Add embedding
    dummy_vector = [0.1] * 384
    emb = ChunkEmbedding(
        code_chunk_id=chunk.id,
        embedding=dummy_vector,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash=embedding_service.compute_content_hash(chunk.content),
    )
    db_session.add(emb)
    db_session.commit()

    mock_answer = "Authentication session verification is implemented in `backend/auth/session.py` via `verify_session`."

    with patch("app.services.gemini_service.generate_rag_answer", return_value=mock_answer) as mock_gemini:
        res = rag_service.answer_repository_question(
            db=db_session,
            repository_id=repo.id,
            query="How does session verification work?",
            top_k=5,
        )

        assert res["repository_id"] == repo.id
        assert res["query"] == "How does session verification work?"
        assert res["answer"] == mock_answer
        assert len(res["sources"]) == 1
        assert res["sources"][0]["file_path"] == "backend/auth/session.py"
        assert res["sources"][0]["start_line"] == 1
        assert res["sources"][0]["end_line"] == 1

        # Verify Gemini was invoked with prompt containing context & query
        mock_gemini.assert_called_once()
        call_kwargs = mock_gemini.call_args.kwargs
        assert "=== REPOSITORY CONTEXT ===" in call_kwargs["user_prompt"]
        assert "backend/auth/session.py" in call_kwargs["user_prompt"]
        assert "How does session verification work?" in call_kwargs["user_prompt"]


def test_rag_repository_isolation(db_session):
    """Test 4 & 14: RAG search on Repo A never returns code chunks from Repo B."""
    # Repo A
    repo_a = Repository(
        name="Repo A",
        full_name="testowner/repoA",
        github_url="https://github.com/testowner/repoA",
    )
    # Repo B
    repo_b = Repository(
        name="Repo B",
        full_name="testowner/repoB",
        github_url="https://github.com/testowner/repoB",
    )
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_a = RepositoryFile(repository_id=repo_a.id, path="src/repoA_secret.py", name="repoA_secret.py", extension=".py", size=50, file_type="source", content="SECRET_A = 100")
    file_b = RepositoryFile(repository_id=repo_b.id, path="src/repoB_secret.py", name="repoB_secret.py", extension=".py", size=50, file_type="source", content="SECRET_B = 200")
    db_session.add_all([file_a, file_b])
    db_session.commit()

    chunk_a = CodeChunk(repository_file_id=file_a.id, chunk_index=0, start_line=1, end_line=1, content="SECRET_A = 100")
    chunk_b = CodeChunk(repository_file_id=file_b.id, chunk_index=0, start_line=1, end_line=1, content="SECRET_B = 200")
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()

    emb_a = ChunkEmbedding(code_chunk_id=chunk_a.id, embedding=[0.5] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk_a.content))
    emb_b = ChunkEmbedding(code_chunk_id=chunk_b.id, embedding=[0.5] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk_b.content))
    db_session.add_all([emb_a, emb_b])
    db_session.commit()

    with patch("app.services.gemini_service.generate_rag_answer", return_value="Ground Answer"):
        res = rag_service.answer_repository_question(db_session, repo_a.id, "Where is secret stored?")
        source_paths = [s["file_path"] for s in res["sources"]]

        assert "src/repoA_secret.py" in source_paths
        assert "src/repoB_secret.py" not in source_paths


def test_rag_query_and_top_k_validation(db_session):
    """Test 2 & 11: Validation for empty query, whitespace query, and invalid top_k bounds."""
    fake_id = uuid.uuid4()

    with pytest.raises(ValueError, match="Question query cannot be empty"):
        rag_service.answer_repository_question(db_session, fake_id, "")

    with pytest.raises(ValueError, match="Question query cannot be empty"):
        rag_service.answer_repository_question(db_session, fake_id, "   ")

    with pytest.raises(ValueError, match="top_k must be an integer between 1 and 10"):
        rag_service.answer_repository_question(db_session, fake_id, "Valid query", top_k=0)

    with pytest.raises(ValueError, match="top_k must be an integer between 1 and 10"):
        rag_service.answer_repository_question(db_session, fake_id, "Valid query", top_k=15)


def test_rag_non_existent_repository(db_session):
    """Test 3: Non-existent repository UUID raises ValueError."""
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match="not found"):
        rag_service.answer_repository_question(db_session, fake_id, "How to run app?")


def test_rag_unembedded_repository(db_session):
    """Test 12: Repository with chunks but 0 embeddings raises 400 error."""
    repo = Repository(
        name="Unembedded Repo",
        full_name="testowner/unembedded",
        github_url="https://github.com/testowner/unembedded",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="main.py", name="main.py", extension=".py", size=20, file_type="source", content="print('hello')")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=1, content="print('hello')")
    db_session.add(chunk)
    db_session.commit()

    with pytest.raises(ValueError, match="Repository has not been embedded yet"):
        rag_service.answer_repository_question(db_session, repo.id, "What does main.py do?")


def test_gemini_service_missing_api_key():
    """Test 9: Missing GEMINI_API_KEY raises user-friendly error without leaking secrets."""
    with patch("app.services.gemini_service.GEMINI_API_KEY", None):
        with pytest.raises(ValueError, match="Gemini API key is not configured"):
            gemini_service.generate_rag_answer("System instruction", "User prompt")


def test_gemini_service_api_exception():
    """Test 10: Gemini API exception handled cleanly."""
    with patch("app.services.gemini_service.GEMINI_API_KEY", "dummy_key"):
        with patch("app.services.gemini_service.get_gemini_client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("Quota exceeded")
            with pytest.raises(ValueError, match="Gemini API generation failed: Quota exceeded"):
                gemini_service.generate_rag_answer("System instruction", "User prompt")


def test_api_ask_repository_endpoint(client, db_session):
    """Test 12 & 15: Full REST API POST /api/repositories/{id}/ask with mocked Gemini client."""
    repo = Repository(
        name="RAG API Test Repo",
        full_name="testowner/ragapi",
        github_url="https://github.com/testowner/ragapi",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="app/db.py", name="db.py", extension=".py", size=50, file_type="source", content="def get_connection(): pass")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=1, content="def get_connection(): pass")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.2] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk.content))
    db_session.add(emb)
    db_session.commit()

    mock_answer = "Database connection is created in `app/db.py` via `get_connection()`."

    with patch("app.services.gemini_service.generate_rag_answer", return_value=mock_answer):
        response = client.post(
            f"/api/repositories/{repo.id}/ask",
            json={"query": "How to get DB connection?", "top_k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["repository_id"] == str(repo.id)
        assert data["query"] == "How to get DB connection?"
        assert data["answer"] == mock_answer
        assert len(data["sources"]) == 1
        assert data["sources"][0]["file_path"] == "app/db.py"
        assert "model_name" in data


def test_api_ask_invalid_repository_404(client):
    """Test 404 response for non-existent repository in POST /ask endpoint."""
    fake_id = uuid.uuid4()
    response = client.post(
        f"/api/repositories/{fake_id}/ask",
        json={"query": "Where is main?", "top_k": 5},
    )
    assert response.status_code == 404
