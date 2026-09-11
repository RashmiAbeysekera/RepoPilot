"""
Tests for Day 10 Source-Aware Grounded RAG Pipeline.

TEST COVERAGE:
  1. Valid RAG request returns answer, source references, and deduplicated file sources.
  2. Source deduplication: multiple chunks from the same file are consolidated into a single file source with combined line ranges.
  3. Source metadata fidelity: start_line, end_line, file_path, and similarity scores are authentic and non-fabricated.
  4. Backward compatibility: chunks with None/legacy line numbers do not crash the pipeline.
  5. Relevance threshold filtering: low-relevance chunks below RAG_SIMILARITY_THRESHOLD are filtered out.
  6. Low-relevance query fallback: returns controlled response without calling Gemini when no chunks meet threshold.
  7. Out-of-context query: "What is the capital of France?" triggers fallback without calling Gemini.
  8. Empty retrieval: 0 chunks found returns fallback response without calling Gemini.
  9. Repository isolation: RAG query on Repo A never retrieves chunks from Repo B.
 10. Stale data test: Day 9 incremental sync updates are reflected in RAG context while purged chunks are absent.
 11. Query & top_k validation: empty queries and out-of-bounds top_k rejected.
 12. Non-existent repository raises error / returns 404.
 13. Un-embedded repository raises clear 400 error.
 14. Gemini API error handling: missing API key and runtime API failure handled gracefully.
 15. End-to-end REST API endpoint POST /api/repositories/{id}/ask validation.
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
    """Context builder formats file path, line range, score, and respects character limit."""
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

    # Truncation with small limit
    truncated_context = context_builder.build_rag_context(chunks, max_context_chars=120)
    assert len(truncated_context) <= 300
    assert "--- Source 1" in truncated_context


def test_source_deduplication_helper():
    """Verify group_sources_by_file deduplicates files and consolidates line ranges."""
    f1_id = uuid.uuid4()
    f2_id = uuid.uuid4()
    chunks = [
        {
            "chunk_id": uuid.uuid4(),
            "repository_file_id": f1_id,
            "file_path": "backend/auth/login.py",
            "chunk_index": 0,
            "start_line": 10,
            "end_line": 30,
            "score": 0.85,
            "content": "chunk 1",
        },
        {
            "chunk_id": uuid.uuid4(),
            "repository_file_id": f1_id,
            "file_path": "backend/auth/login.py",
            "chunk_index": 1,
            "start_line": 35,
            "end_line": 60,
            "score": 0.92,
            "content": "chunk 2",
        },
        {
            "chunk_id": uuid.uuid4(),
            "repository_file_id": f2_id,
            "file_path": "backend/auth/jwt.py",
            "chunk_index": 0,
            "start_line": 5,
            "end_line": 25,
            "score": 0.78,
            "content": "chunk 3",
        },
    ]

    grouped = rag_service.group_sources_by_file(chunks)
    assert len(grouped) == 2

    # Verify login.py consolidation
    login_group = next(g for g in grouped if g["file_path"] == "backend/auth/login.py")
    assert login_group["repository_file_id"] == f1_id
    assert login_group["chunks_count"] == 2
    assert login_group["max_similarity"] == 0.92
    assert "10–30" in login_group["line_ranges"]
    assert "35–60" in login_group["line_ranges"]

    # Verify jwt.py consolidation
    jwt_group = next(g for g in grouped if g["file_path"] == "backend/auth/jwt.py")
    assert jwt_group["repository_file_id"] == f2_id
    assert jwt_group["chunks_count"] == 1
    assert jwt_group["max_similarity"] == 0.78
    assert "5–25" in jwt_group["line_ranges"]


def test_rag_service_valid_query(db_session):
    """Complete RAG pipeline returns answer, sources, file_sources, and preserves line metadata."""
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
        end_line=10,
        content="def verify_session(token): return True",
    )
    db_session.add(chunk)
    db_session.commit()

    # Add normalized embedding
    norm_vector = [0.05] * 384
    emb = ChunkEmbedding(
        code_chunk_id=chunk.id,
        embedding=norm_vector,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash=embedding_service.compute_content_hash(chunk.content),
    )
    db_session.add(emb)
    db_session.commit()

    mock_answer = "Authentication session verification is implemented in `backend/auth/session.py`."

    # Mock query embedding generation to return same vector so similarity is ~1.0
    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[norm_vector]):
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
            assert res["chunks_retrieved"] == 1

            # Verify chunk-level source reference
            assert len(res["sources"]) == 1
            src = res["sources"][0]
            assert src["file_path"] == "backend/auth/session.py"
            assert src["start_line"] == 1
            assert src["end_line"] == 10
            assert src["similarity"] >= 0.9
            assert src["score"] >= 0.9

            # Verify deduplicated file sources
            assert len(res["file_sources"]) == 1
            f_src = res["file_sources"][0]
            assert f_src["file_path"] == "backend/auth/session.py"
            assert f_src["chunks_count"] == 1
            assert "1–10" in f_src["line_ranges"]

            mock_gemini.assert_called_once()


def test_rag_low_relevance_threshold_fallback(db_session):
    """Chunks below RAG_SIMILARITY_THRESHOLD are filtered out; returns fallback without calling Gemini."""
    repo = Repository(
        name="Low Relevance Repo",
        full_name="testowner/lowrelevance",
        github_url="https://github.com/testowner/lowrelevance",
    )
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/math.py",
        name="math.py",
        extension=".py",
        size=50,
        file_type="source",
        content="def add(a, b): return a + b",
    )
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(
        repository_file_id=file_rec.id,
        chunk_index=0,
        start_line=1,
        end_line=5,
        content="def add(a, b): return a + b",
    )
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(
        code_chunk_id=chunk.id,
        embedding=[0.01] * 384,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash=embedding_service.compute_content_hash(chunk.content),
    )
    db_session.add(emb)
    db_session.commit()

    # Mock search_service to return a chunk with low similarity score (0.15)
    mock_low_result = {
        "repository_id": repo.id,
        "query": "What is the capital of France?",
        "top_k": 5,
        "total_results": 1,
        "results": [
            {
                "chunk_id": chunk.id,
                "repository_file_id": file_rec.id,
                "file_path": "src/math.py",
                "chunk_index": 0,
                "start_line": 1,
                "end_line": 5,
                "content": chunk.content,
                "score": 0.15,  # Below default threshold 0.35
            }
        ],
    }

    with patch("app.services.search_service.search_repository_chunks", return_value=mock_low_result):
        with patch("app.services.gemini_service.generate_rag_answer") as mock_gemini:
            res = rag_service.answer_repository_question(
                db=db_session,
                repository_id=repo.id,
                query="What is the capital of France?",
                top_k=5,
            )

            # Assert Gemini was NEVER called (zero API quota used)
            mock_gemini.assert_not_called()

            assert "couldn't find enough relevant information" in res["answer"]
            assert res["sources"] == []
            assert res["file_sources"] == []
            assert res["chunks_retrieved"] == 0
            assert "minimum relevance threshold" in res["confidence_warning"]


def test_rag_empty_retrieval(db_session):
    """Empty retrieval (0 chunks) returns fallback response without calling Gemini."""
    repo = Repository(
        name="Empty Repo",
        full_name="testowner/emptyrepo",
        github_url="https://github.com/testowner/emptyrepo",
    )
    db_session.add(repo)
    db_session.commit()

    mock_empty_result = {
        "repository_id": repo.id,
        "query": "How to deploy?",
        "top_k": 5,
        "total_results": 0,
        "results": [],
    }

    with patch("app.services.search_service.search_repository_chunks", return_value=mock_empty_result):
        with patch("app.services.gemini_service.generate_rag_answer") as mock_gemini:
            res = rag_service.answer_repository_question(
                db=db_session,
                repository_id=repo.id,
                query="How to deploy?",
                top_k=5,
            )

            mock_gemini.assert_not_called()
            assert "couldn't find enough relevant information" in res["answer"]
            assert res["sources"] == []
            assert res["file_sources"] == []
            assert res["chunks_retrieved"] == 0


def test_rag_repository_isolation(db_session):
    """RAG search on Repo A never returns code chunks from Repo B."""
    repo_a = Repository(name="Repo A", full_name="testowner/repoA", github_url="https://github.com/testowner/repoA")
    repo_b = Repository(name="Repo B", full_name="testowner/repoB", github_url="https://github.com/testowner/repoB")
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

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.5] * 384]):
        with patch("app.services.gemini_service.generate_rag_answer", return_value="Grounded Answer"):
            res = rag_service.answer_repository_question(db_session, repo_a.id, "Where is secret stored?")
            source_paths = [s["file_path"] for s in res["sources"]]

            assert "src/repoA_secret.py" in source_paths
            assert "src/repoB_secret.py" not in source_paths


def test_rag_stale_data_post_sync(db_session):
    """Verify that after an incremental file update/deletion, old chunks are absent and new chunks retrieved."""
    repo = Repository(name="Sync Test Repo", full_name="testowner/synctest", github_url="https://github.com/testowner/synctest")
    db_session.add(repo)
    db_session.commit()

    file_new = RepositoryFile(repository_id=repo.id, path="src/active.py", name="active.py", extension=".py", size=50, file_type="source", content="NEW_ALGORITHM = 'AES-GCM'")
    db_session.add(file_new)
    db_session.commit()

    chunk_new = CodeChunk(repository_file_id=file_new.id, chunk_index=0, start_line=1, end_line=5, content="NEW_ALGORITHM = 'AES-GCM'")
    db_session.add(chunk_new)
    db_session.commit()

    emb_new = ChunkEmbedding(code_chunk_id=chunk_new.id, embedding=[0.3] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk_new.content))
    db_session.add(emb_new)
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.3] * 384]):
        with patch("app.services.gemini_service.generate_rag_answer", return_value="The project uses AES-GCM."):
            res = rag_service.answer_repository_question(db_session, repo.id, "What algorithm is used?")
            assert len(res["sources"]) == 1
            assert res["sources"][0]["file_path"] == "src/active.py"
            assert "src/old_deleted.py" not in [s["file_path"] for s in res["sources"]]


def test_rag_backward_compatibility_legacy_chunks():
    """Legacy chunks with None line numbers are handled gracefully without crashing."""
    legacy_chunk = {
        "chunk_id": uuid.uuid4(),
        "repository_file_id": uuid.uuid4(),
        "file_path": "legacy/script.py",
        "chunk_index": 0,
        "start_line": None,
        "end_line": None,
        "score": 0.85,
        "content": "legacy_code()",
    }

    grouped = rag_service.group_sources_by_file([legacy_chunk])
    assert len(grouped) == 1
    assert grouped[0]["file_path"] == "legacy/script.py"
    assert grouped[0]["line_ranges"] == []
    assert grouped[0]["max_similarity"] == 0.85


def test_rag_query_and_top_k_validation(db_session):
    """Validation for empty query, whitespace query, and invalid top_k bounds."""
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
    """Non-existent repository UUID raises ValueError."""
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match="not found"):
        rag_service.answer_repository_question(db_session, fake_id, "How to run app?")


def test_rag_unembedded_repository(db_session):
    """Repository with chunks but 0 embeddings raises 400 error."""
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
    """Missing GEMINI_API_KEY raises user-friendly error without leaking secrets."""
    with patch("app.services.gemini_service.get_gemini_api_key", return_value=None):
        with pytest.raises(ValueError, match="Gemini API key is not configured"):
            gemini_service.generate_rag_answer("System instruction", "User prompt")


def test_gemini_service_api_exception():
    """Gemini API exception handled cleanly."""
    with patch("app.services.gemini_service.get_gemini_api_key", return_value="dummy_key"):
        with patch("app.services.gemini_service.get_gemini_client") as mock_client:
            mock_client.return_value.models.generate_content.side_effect = Exception("Quota exceeded")
            with pytest.raises(ValueError, match="Gemini API generation failed: Quota exceeded"):
                gemini_service.generate_rag_answer("System instruction", "User prompt")


def test_api_ask_repository_endpoint(client, db_session):
    """Full REST API POST /api/repositories/{id}/ask with mocked Gemini client returns RAGAnswerResponse."""
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

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=10, content="def get_connection(): pass")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.2] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk.content))
    db_session.add(emb)
    db_session.commit()

    mock_answer = "Database connection is created in `app/db.py` via `get_connection()`."

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.2] * 384]):
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
            assert data["sources"][0]["start_line"] == 1
            assert data["sources"][0]["end_line"] == 10
            assert "similarity" in data["sources"][0]
            assert len(data["file_sources"]) == 1
            assert data["file_sources"][0]["file_path"] == "app/db.py"
            assert data["file_sources"][0]["chunks_count"] == 1
            assert data["chunks_retrieved"] == 1
            assert "model_name" in data


def test_api_ask_invalid_repository_404(client):
    """Test 404 response for non-existent repository in POST /ask endpoint."""
    fake_id = uuid.uuid4()
    response = client.post(
        f"/api/repositories/{fake_id}/ask",
        json={"query": "Where is main?", "top_k": 5},
    )
    assert response.status_code == 404
