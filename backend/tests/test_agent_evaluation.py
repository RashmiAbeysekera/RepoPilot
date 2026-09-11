"""
Day 12 Production Engineering: Agent Evaluation Tests.

TEST CASES:
  A. Simple lookup ("Where is authentication implemented?")
  B. Multi-step investigation ("Explain the login flow from frontend to backend.")
  C. Architecture investigation ("How does repository structure work?")
  D. Negative question ("Where is the payment gateway implemented?" when absent)
  E. Tool selection & multi-turn execution
  F. Insufficient evidence handling & refusal
  G. Strictly bounded iterations (enforcing MAX_AGENT_ITERATIONS)
"""

from unittest.mock import MagicMock, patch
import pytest

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk
from app.models.chunk_embedding import ChunkEmbedding
from app.services import agent_service


def test_agent_eval_scenario_a_simple_lookup(db_session):
    """Scenario A: Simple lookup selects search or read_file and provides grounded answer."""
    repo = Repository(name="EvalRepoA", full_name="org/eval-a", github_url="https://github.com/org/eval-a")
    db_session.add(repo)
    db_session.commit()

    file_rec = RepositoryFile(
        repository_id=repo.id,
        path="src/auth.py",
        name="auth.py",
        extension=".py",
        size=100,
        content="def login(): pass\ndef verify_token(): pass",
    )
    db_session.add(file_rec)
    db_session.commit()

    # Model calls search_repository, then provides answer
    call_search = MagicMock(name="search_call")
    call_search.name = "find_repository_files"
    call_search.args = {"pattern": "auth"}
    resp_search = MagicMock()
    resp_search.function_calls = [call_search]
    resp_search.candidates = [MagicMock(content="search candidates")]

    resp_answer = MagicMock()
    resp_answer.function_calls = []
    resp_answer.text = "Authentication is implemented in `src/auth.py`."

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_search, resp_answer]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Where is authentication implemented?",
            max_iterations=3,
        )

        assert len(res["trace"]) == 1
        assert res["trace"][0]["tool"] == "find_repository_files"
        assert res["trace"][0]["status"] == "success"
        assert "src/auth.py" in res["answer"]


def test_agent_eval_scenario_b_multistep_investigation(db_session):
    """Scenario B: Multi-step investigation executes multiple tools sequentially."""
    repo = Repository(name="EvalRepoB", full_name="org/eval-b", github_url="https://github.com/org/eval-b")
    db_session.add(repo)
    db_session.commit()

    file_fe = RepositoryFile(repository_id=repo.id, path="frontend/Login.jsx", name="Login.jsx", extension=".jsx", size=100, content="fetch('/api/login')")
    file_be = RepositoryFile(repository_id=repo.id, path="backend/auth.py", name="auth.py", extension=".py", size=100, content="def api_login(): pass")
    db_session.add_all([file_fe, file_be])
    db_session.commit()

    # Call 1: find frontend files
    call_1 = MagicMock()
    call_1.name = "find_repository_files"
    call_1.args = {"pattern": "Login"}
    resp_1 = MagicMock(function_calls=[call_1], candidates=[MagicMock(content="c1")])

    # Call 2: read backend file
    call_2 = MagicMock()
    call_2.name = "read_repository_file"
    call_2.args = {"file_path": "backend/auth.py"}
    resp_2 = MagicMock(function_calls=[call_2], candidates=[MagicMock(content="c2")])

    # Call 3: finalize synthesis
    resp_3 = MagicMock(function_calls=[], text="The login flow starts in `frontend/Login.jsx` and calls `backend/auth.py`.")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_1, resp_2, resp_3]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Explain the login flow from frontend to backend.",
            max_iterations=4,
        )

        assert len(res["trace"]) == 2
        assert res["trace"][0]["tool"] == "find_repository_files"
        assert res["trace"][1]["tool"] == "read_repository_file"
        assert "Login.jsx" in res["answer"]
        assert "auth.py" in res["answer"]


def test_agent_eval_scenario_c_architecture_overview(db_session):
    """Scenario C: Architecture inquiry invokes get_repository_structure."""
    repo = Repository(name="EvalRepoC", full_name="org/eval-c", github_url="https://github.com/org/eval-c")
    db_session.add(repo)
    db_session.commit()

    db_session.add(RepositoryFile(repository_id=repo.id, path="server.js", name="server.js", extension=".js", size=100, content=""))
    db_session.commit()

    call_struct = MagicMock()
    call_struct.name = "get_repository_structure"
    call_struct.args = {}
    resp_struct = MagicMock(function_calls=[call_struct], candidates=[MagicMock(content="c")])
    resp_answer = MagicMock(function_calls=[], text="The repository contains a Node.js server.js architecture.")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_struct, resp_answer]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Explain the overall repository architecture.",
            max_iterations=2,
        )

        assert len(res["trace"]) == 1
        assert res["trace"][0]["tool"] == "get_repository_structure"
        assert "architecture" in res["answer"].lower()


def test_agent_eval_scenario_d_negative_question_refusal(db_session):
    """Scenario D: When asked about nonexistent feature, agent searches and acknowledges absence."""
    repo = Repository(name="EvalRepoD", full_name="org/eval-d", github_url="https://github.com/org/eval-d")
    db_session.add(repo)
    db_session.commit()

    # Search for payment
    call_search = MagicMock()
    call_search.name = "find_repository_files"
    call_search.args = {"pattern": "payment"}
    resp_search = MagicMock(function_calls=[call_search], candidates=[MagicMock(content="c")])

    resp_refusal = MagicMock(
        function_calls=[],
        text="I searched the repository for payment files, but no payment gateway is implemented in this codebase.",
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_search, resp_refusal]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Where is the payment gateway implemented?",
            max_iterations=3,
        )

        assert len(res["trace"]) == 1
        assert "no payment gateway" in res["answer"].lower()


def test_agent_eval_blocked_unauthorized_tool(db_session):
    """Ensure agent cannot call unauthorized tools outside the security whitelist."""
    repo = Repository(name="EvalRepoE", full_name="org/eval-e", github_url="https://github.com/org/eval-e")
    db_session.add(repo)
    db_session.commit()

    call_bad = MagicMock()
    call_bad.name = "execute_shell_command"
    call_bad.args = {"command": "rm -rf /"}
    resp_bad = MagicMock(function_calls=[call_bad], candidates=[MagicMock(content="bad")])

    resp_recovered = MagicMock(function_calls=[], text="I cannot execute shell commands.")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [resp_bad, resp_recovered]

    with patch("app.services.gemini_service.get_gemini_client", return_value=mock_client):
        res = agent_service.run_agent_investigation(
            db=db_session,
            repository_id=repo.id,
            query="Delete the database",
            max_iterations=2,
        )

        assert len(res["trace"]) == 1
        assert res["trace"][0]["status"] == "blocked"
        assert "Blocked unauthorized tool" in res["trace"][0]["result_summary"]
