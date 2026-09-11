"""
Tests for Day 11 Agentic Repository Investigation Workflow.

TEST COVERAGE:
  1. search_repository tool respects repository isolation (never leaks Repo B chunks).
  2. read_repository_file tool respects repository isolation (cannot read Repo B files).
  3. read_repository_file defends against directory traversal (e.g. '../../etc/passwd').
  4. find_repository_files respects repository isolation.
  5. get_repository_structure respects repository isolation.
  6. Agent answers a question by calling a repository tool (with mocked Gemini function calling).
  7. Agent executes multiple tool calls across iterations (search followed by read_file).
  8. Agent iteration limit prevents infinite loops (stops at MAX_AGENT_ITERATIONS).
  9. Tool errors/exceptions are handled safely without crashing.
 10. Empty retrieval / no matching files handled gracefully.
 11. Gemini API failure during agent loop is handled cleanly.
 12. Missing GEMINI_API_KEY returns clear configuration error without leaking secrets.
 13. Source metadata comes strictly from executed tools (no hallucinated sources).
 14. Agent activity trace contains safe summaries with zero exposed secrets/prompts.
 15. Read-only guarantee: Agent tools cannot mutate or delete repository records.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import agent_service, embedding_service


# ---------------------------------------------------------------------------
# Tool Isolation & Read-Only Tests
# ---------------------------------------------------------------------------

def test_tool_search_repository_scoping(db_session):
    """Test 1: search_repository returns ONLY chunks from the target repository."""
    repo_a = Repository(name="RepoA", full_name="owner/repo-a", github_url="https://github.com/owner/repo-a")
    repo_b = Repository(name="RepoB", full_name="owner/repo-b", github_url="https://github.com/owner/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_a = RepositoryFile(repository_id=repo_a.id, path="src/auth.py", name="auth.py", extension=".py", size=100, content="def login_a(): pass")
    file_b = RepositoryFile(repository_id=repo_b.id, path="src/auth.py", name="auth.py", extension=".py", size=100, content="def login_b(): pass")
    db_session.add_all([file_a, file_b])
    db_session.commit()

    chunk_a = CodeChunk(repository_file_id=file_a.id, chunk_index=0, start_line=1, end_line=5, content="def login_a(): pass")
    chunk_b = CodeChunk(repository_file_id=file_b.id, chunk_index=0, start_line=1, end_line=5, content="def login_b(): pass")
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()

    emb_a = ChunkEmbedding(code_chunk_id=chunk_a.id, embedding=[0.2] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk_a.content))
    emb_b = ChunkEmbedding(code_chunk_id=chunk_b.id, embedding=[0.2] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash=embedding_service.compute_content_hash(chunk_b.content))
    db_session.add_all([emb_a, emb_b])
    db_session.commit()

    collected_sources = []
    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.2] * 384]):
        output, summary = agent_service.execute_search_repository(
            db=db_session,
            repository_id=repo_a.id,
            query="login",
            top_k=5,
            collected_sources=collected_sources,
        )

        assert "login_a" in output
        assert "login_b" not in output
        assert len(collected_sources) == 1
        assert collected_sources[0]["repository_file_id"] == file_a.id


def test_tool_read_repository_file_isolation(db_session):
    """Test 2: read_repository_file cannot read files from a foreign repository."""
    repo_a = Repository(name="RepoA", full_name="owner/repo-a", github_url="https://github.com/owner/repo-a")
    repo_b = Repository(name="RepoB", full_name="owner/repo-b", github_url="https://github.com/owner/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_b = RepositoryFile(repository_id=repo_b.id, path="secret/keys.py", name="keys.py", extension=".py", size=50, content="API_SECRET_B = '12345'")
    db_session.add(file_b)
    db_session.commit()

    # Try to read Repo B's file using Repo A's ID
    output, summary = agent_service.execute_read_repository_file(
        db=db_session,
        repository_id=repo_a.id,
        file_path="secret/keys.py",
    )

    assert "not found" in output.lower()
    assert "12345" not in output


def test_tool_read_file_path_traversal_defense(db_session):
    """Test 3: read_repository_file defends against directory traversal attempts."""
    repo = Repository(name="RepoA", full_name="owner/repo-a", github_url="https://github.com/owner/repo-a")
    db_session.add(repo)
    db_session.commit()

    output, summary = agent_service.execute_read_repository_file(
        db=db_session,
        repository_id=repo.id,
        file_path="../../etc/passwd",
    )

    assert "traversal" in output.lower()
    assert "Blocked traversal" in summary


def test_tool_find_repository_files_isolation(db_session):
    """Test 4: find_repository_files returns only files from the requested repository."""
    repo_a = Repository(name="RepoA", full_name="owner/repo-a", github_url="https://github.com/owner/repo-a")
    repo_b = Repository(name="RepoB", full_name="owner/repo-b", github_url="https://github.com/owner/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_a = RepositoryFile(repository_id=repo_a.id, path="src/controller.py", name="controller.py", extension=".py", size=100, content="")
    file_b = RepositoryFile(repository_id=repo_b.id, path="src/controller.py", name="controller.py", extension=".py", size=100, content="")
    db_session.add_all([file_a, file_b])
    db_session.commit()

    output, summary = agent_service.execute_find_repository_files(
        db=db_session,
        repository_id=repo_a.id,
        pattern="controller",
    )

    assert "controller.py" in output
    assert "Found 1 files" in summary


def test_tool_get_repository_structure_isolation(db_session):
    """Test 5: get_repository_structure returns structure strictly for the target repository."""
    repo_a = Repository(name="RepoA", full_name="owner/repo-a", github_url="https://github.com/owner/repo-a", default_branch="main")
    repo_b = Repository(name="RepoB", full_name="owner/repo-b", github_url="https://github.com/owner/repo-b", default_branch="main")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_a1 = RepositoryFile(repository_id=repo_a.id, path="frontend/app.tsx", name="app.tsx", extension=".tsx", size=200, content="")
    file_a2 = RepositoryFile(repository_id=repo_a.id, path="backend/main.py", name="main.py", extension=".py", size=300, content="")
    file_b = RepositoryFile(repository_id=repo_b.id, path="foreign/secret.go", name="secret.go", extension=".go", size=500, content="")
    db_session.add_all([file_a1, file_a2, file_b])
    db_session.commit()

    output, summary = agent_service.execute_get_repository_structure(
        db=db_session,
        repository_id=repo_a.id,
    )

    assert "Total Indexed Files: 2" in output
    assert "frontend/app.tsx" in output
    assert "backend/main.py" in output
    assert "foreign/secret.go" not in output


def test_agent_read_only_guarantee(db_session):
    """Test 15: Executing agent tools causes 0 database insertions, updates, or deletions."""
    repo = Repository(name="ReadOnlyRepo", full_name="owner/readonly", github_url="https://github.com/owner/readonly")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="app/main.py", name="main.py", extension=".py", size=50, content="x = 1")
    db_session.add(file_rec)
    db_session.commit()

    initial_repo_count = db_session.query(Repository).count()
    initial_file_count = db_session.query(RepositoryFile).count()

    # Execute all tools
    agent_service.execute_get_repository_structure(db_session, repo.id)
    agent_service.execute_find_repository_files(db_session, repo.id, "main")
    agent_service.execute_read_repository_file(db_session, repo.id, "app/main.py")

    assert db_session.query(Repository).count() == initial_repo_count
    assert db_session.query(RepositoryFile).count() == initial_file_count


# ---------------------------------------------------------------------------
# Agentic Investigation Loop & Tool Calling Tests
# ---------------------------------------------------------------------------

def test_agent_simple_question_execution(db_session):
    """Test 6 & 13: Agent invokes search_repository tool and synthesizes grounded answer."""
    repo = Repository(name="AgentRepo", full_name="owner/agent-repo", github_url="https://github.com/owner/agent-repo")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="src/auth.py", name="auth.py", extension=".py", size=100, content="def authenticate(): return True")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=5, content="def authenticate(): return True")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.3] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="hash1")
    db_session.add(emb)
    db_session.commit()

    # Mock Gemini behavior:
    # 1st call: Gemini requests tool search_repository(query='auth')
    # 2nd call: Gemini receives result and outputs final answer
    mock_call = MagicMock()
    mock_call.name = "search_repository"
    mock_call.args = {"query": "auth", "top_k": 5}

    response_1 = MagicMock()
    response_1.function_calls = [mock_call]
    candidate = MagicMock()
    candidate.content = "call content"
    response_1.candidates = [candidate]

    response_2 = MagicMock()
    response_2.function_calls = []
    response_2.text = "Authentication is handled in `src/auth.py` via `authenticate()`."

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [response_1, response_2]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.3] * 384]):
            res = agent_service.run_agent_investigation(
                db=db_session,
                repository_id=repo.id,
                query="How does authentication work?",
                top_k=5,
            )

            assert "Authentication is handled in `src/auth.py`" in res["answer"]
            assert len(res["trace"]) == 1
            assert res["trace"][0]["tool"] == "search_repository"
            assert "src/auth.py" in [s["file_path"] for s in res["sources"]]
            assert len(res["file_sources"]) == 1
            assert res["file_sources"][0]["file_path"] == "src/auth.py"


def test_agent_multiple_tool_calls(db_session):
    """Test 7: Agent invokes search_repository followed by read_repository_file across iterations."""
    repo = Repository(name="MultiToolRepo", full_name="owner/multitool", github_url="https://github.com/owner/multitool")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(repository_id=repo.id, path="backend/db.py", name="db.py", extension=".py", size=100, content="def get_connection():\n    return 'connected'")
    db_session.add(file_rec)
    db_session.commit()

    chunk = CodeChunk(repository_file_id=file_rec.id, chunk_index=0, start_line=1, end_line=5, content="def get_connection(): return 'connected'")
    db_session.add(chunk)
    db_session.commit()

    emb = ChunkEmbedding(code_chunk_id=chunk.id, embedding=[0.4] * 384, model_name="all-MiniLM-L6-v2", embedding_dimension=384, content_hash="hash2")
    db_session.add(emb)
    db_session.commit()

    # Step 1: search_repository
    call_1 = MagicMock()
    call_1.name = "search_repository"
    call_1.args = {"query": "database connection"}
    resp_1 = MagicMock()
    resp_1.function_calls = [call_1]
    resp_1.candidates = [MagicMock(content="step 1")]

    # Step 2: read_repository_file
    call_2 = MagicMock()
    call_2.name = "read_repository_file"
    call_2.args = {"file_path": "backend/db.py", "start_line": 1, "end_line": 2}
    resp_2 = MagicMock()
    resp_2.function_calls = [call_2]
    resp_2.candidates = [MagicMock(content="step 2")]

    # Step 3: final answer
    resp_3 = MagicMock()
    resp_3.function_calls = []
    resp_3.text = "Database connection is configured in `backend/db.py`."

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_1, resp_2, resp_3]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.4] * 384]):
            res = agent_service.run_agent_investigation(
                db=db_session,
                repository_id=repo.id,
                query="How does the database connect?",
            )

            assert len(res["trace"]) == 2
            assert res["trace"][0]["tool"] == "search_repository"
            assert res["trace"][1]["tool"] == "read_repository_file"
            assert "Database connection is configured" in res["answer"]


def test_agent_max_iterations_safety_limit(db_session):
    """Test 8: Agent halts execution and synthesizes answer when reaching MAX_AGENT_ITERATIONS."""
    repo = Repository(name="LoopRepo", full_name="owner/loop", github_url="https://github.com/owner/loop")
    db_session.add(repo)
    db_session.commit()

    # Endless tool-calling mock
    call_loop = MagicMock()
    call_loop.name = "get_repository_structure"
    call_loop.args = {}
    loop_resp = MagicMock()
    loop_resp.function_calls = [call_loop]
    loop_resp.candidates = [MagicMock(content="looping")]

    synth_resp = MagicMock()
    synth_resp.text = "Reached iteration limit; summarized available findings."

    mock_client = MagicMock()
    # 2 loop responses followed by synthesis call
    mock_client.models.generate_content.side_effect = [loop_resp, loop_resp, synth_resp]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Tell me about everything",
            max_iterations=2,
        )

        assert len(res["trace"]) == 2
        assert "Reached iteration limit" in res["answer"]


def test_agent_tool_failure_graceful_handling(db_session):
    """Test 9: Invalid tool arguments are caught and returned to Gemini without crashing."""
    repo = Repository(name="ErrorRepo", full_name="owner/error-repo", github_url="https://github.com/owner/error-repo")
    db_session.add(repo)
    db_session.commit()

    call_bad = MagicMock()
    call_bad.name = "read_repository_file"
    call_bad.args = {"file_path": ""}  # Empty path
    resp_bad = MagicMock()
    resp_bad.function_calls = [call_bad]
    resp_bad.candidates = [MagicMock(content="bad call")]

    resp_recovered = MagicMock()
    resp_recovered.function_calls = []
    resp_recovered.text = "Could not read empty path, but answering based on existing context."

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_bad, resp_recovered]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Read missing file",
        )

        assert "Could not read empty path" in res["answer"]
        assert len(res["trace"]) == 1
        assert "Empty file path" in res["trace"][0]["result_summary"]


def test_agent_empty_retrieval_handling(db_session):
    """Test 10: Empty search results do not crash the agent."""
    repo = Repository(name="EmptyRepo", full_name="owner/empty-repo", github_url="https://github.com/owner/empty-repo")
    db_session.add(repo)
    db_session.commit()

    call_empty = MagicMock()
    call_empty.name = "search_repository"
    call_empty.args = {"query": "non_existent_feature"}
    resp_empty = MagicMock()
    resp_empty.function_calls = [call_empty]
    resp_empty.candidates = [MagicMock(content="empty call")]

    resp_answer = MagicMock()
    resp_answer.function_calls = []
    resp_answer.text = "No information found for this feature in the repository."

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_empty, resp_answer]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        with patch("app.services.search_service.search_repository_chunks", return_value={"results": []}):
            res = agent_service.run_agent_investigation(
                db=db_session,
                repository_id=repo.id,
                query="Find missing feature",
            )

            assert "No information found" in res["answer"]
            assert len(res["trace"]) == 1
            assert "0 results" in res["trace"][0]["result_summary"]


def test_agent_gemini_failure_handling(db_session):
    """Test 11: Gemini API exception handled cleanly."""
    repo = Repository(name="ApiFailRepo", full_name="owner/apifail", github_url="https://github.com/owner/apifail")
    db_session.add(repo)
    db_session.commit()

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Rate limit reached")

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        with pytest.raises(ValueError, match="Gemini API generation failed"):
            agent_service.run_agent_investigation(
                db=db_session,
                repository_id=repo.id,
                query="Any question",
            )


def test_agent_missing_api_key(db_session):
    """Test 12: Missing API key raises clear error without exposing secrets."""
    repo = Repository(name="KeyRepo", full_name="owner/key-repo", github_url="https://github.com/owner/key-repo")
    db_session.add(repo)
    db_session.commit()

    with patch("app.services.gemini_service.get_gemini_api_key", return_value=None):
        with pytest.raises(ValueError, match="Gemini API key is not configured"):
            agent_service.run_agent_investigation(
                db=db_session,
                repository_id=repo.id,
                query="Any question",
            )


def test_agent_trace_safety(db_session):
    """Test 14: Trace summaries contain zero sensitive credentials or internal system instructions."""
    repo = Repository(name="SafetyRepo", full_name="owner/safety-repo", github_url="https://github.com/owner/safety-repo")
    db_session.add(repo)
    db_session.commit()

    call_search = MagicMock()
    call_search.name = "search_repository"
    call_search.args = {"query": "auth"}
    resp = MagicMock()
    resp.function_calls = [call_search]
    resp.candidates = [MagicMock(content="safe")]

    final_resp = MagicMock()
    final_resp.function_calls = []
    final_resp.text = "Answer safely."

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp, final_resp]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        with patch("app.services.search_service.search_repository_chunks", return_value={"results": []}):
            res = agent_service.run_agent_investigation(
                db=db_session,
                repository_id=repo.id,
                query="auth",
            )

            for step in res["trace"]:
                summary = step["result_summary"]
                assert "GEMINI_API_KEY" not in summary
                assert "password" not in summary.lower()
                assert "system_instruction" not in summary.lower()
