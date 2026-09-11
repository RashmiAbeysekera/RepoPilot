"""
Comprehensive tests for strict cross-repository data isolation.

SECURITY REQUIREMENTS:
  - Repository A must NEVER leak files, chunks, embeddings, or metadata to Repository B.
  - Semantic search scoped to Repo A returns 0 results from Repo B.
  - Agent tools (search, read, find, structure) strictly scope all queries by repository_id.
  - Synchronization and file operations in Repo A never modify or delete Repo B data.
"""

import uuid
from unittest.mock import patch
import pytest

from app.models.chunk_embedding import ChunkEmbedding
from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import agent_service, embedding_service, search_service


def test_cross_repository_search_isolation(db_session):
    """Ensure vector search on Repo A never returns code chunks belonging to Repo B."""
    repo_a = Repository(name="RepoAlpha", full_name="org/repo-alpha", github_url="https://github.com/org/repo-alpha")
    repo_b = Repository(name="RepoBeta", full_name="org/repo-beta", github_url="https://github.com/org/repo-beta")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_a = RepositoryFile(
        repository_id=repo_a.id,
        path="src/payments.py",
        name="payments.py",
        extension=".py",
        size=120,
        content="def charge_card(amount): return 'Alpha-Payment-OK'",
    )
    file_b = RepositoryFile(
        repository_id=repo_b.id,
        path="src/payments.py",
        name="payments.py",
        extension=".py",
        size=120,
        content="def charge_card(amount): return 'Beta-Payment-SECRET-KEY'",
    )
    db_session.add_all([file_a, file_b])
    db_session.commit()

    chunk_a = CodeChunk(repository_file_id=file_a.id, chunk_index=0, start_line=1, end_line=5, content=file_a.content)
    chunk_b = CodeChunk(repository_file_id=file_b.id, chunk_index=0, start_line=1, end_line=5, content=file_b.content)
    db_session.add_all([chunk_a, chunk_b])
    db_session.commit()

    emb_a = ChunkEmbedding(
        code_chunk_id=chunk_a.id,
        embedding=[0.3] * 384,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash="hash_a",
    )
    emb_b = ChunkEmbedding(
        code_chunk_id=chunk_b.id,
        embedding=[0.3] * 384,
        model_name="all-MiniLM-L6-v2",
        embedding_dimension=384,
        content_hash="hash_b",
    )
    db_session.add_all([emb_a, emb_b])
    db_session.commit()

    with patch("app.services.embedding_service.generate_embeddings_batch", return_value=[[0.3] * 384]):
        res_a = search_service.search_repository_chunks(db=db_session, repository_id=repo_a.id, query="charge_card", top_k=5)
        res_b = search_service.search_repository_chunks(db=db_session, repository_id=repo_b.id, query="charge_card", top_k=5)

    # Repo A results must only contain file_a
    assert len(res_a["results"]) == 1
    assert res_a["results"][0]["repository_file_id"] == file_a.id
    assert "Alpha-Payment" in res_a["results"][0]["content"]
    assert "Beta-Payment" not in res_a["results"][0]["content"]

    # Repo B results must only contain file_b
    assert len(res_b["results"]) == 1
    assert res_b["results"][0]["repository_file_id"] == file_b.id
    assert "Beta-Payment" in res_b["results"][0]["content"]
    assert "Alpha-Payment" not in res_b["results"][0]["content"]


def test_agent_tools_cross_repository_read_isolation(db_session):
    """Ensure agent tool read_repository_file cannot access files in foreign repositories."""
    repo_a = Repository(name="RepoA", full_name="org/repo-a", github_url="https://github.com/org/repo-a")
    repo_b = Repository(name="RepoB", full_name="org/repo-b", github_url="https://github.com/org/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_b = RepositoryFile(
        repository_id=repo_b.id,
        path="config/secret.env",
        name="secret.env",
        extension=".env",
        size=45,
        content="SUPER_SECRET_TOKEN_XYZ_123",
    )
    db_session.add(file_b)
    db_session.commit()

    # Attempt to read Repo B's file while scoped to Repo A
    output, summary = agent_service.execute_read_repository_file(
        db=db_session,
        repository_id=repo_a.id,
        file_path="config/secret.env",
    )

    assert "not found" in output.lower()
    assert "SUPER_SECRET_TOKEN" not in output


def test_agent_tools_cross_repository_find_files_isolation(db_session):
    """Ensure agent tool find_repository_files only discovers files in target repository."""
    repo_a = Repository(name="RepoA", full_name="org/repo-a", github_url="https://github.com/org/repo-a")
    repo_b = Repository(name="RepoB", full_name="org/repo-b", github_url="https://github.com/org/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    file_a = RepositoryFile(repository_id=repo_a.id, path="src/user.js", name="user.js", extension=".js", size=50, content="")
    file_b = RepositoryFile(repository_id=repo_b.id, path="src/user.js", name="user.js", extension=".js", size=50, content="")
    file_b_admin = RepositoryFile(repository_id=repo_b.id, path="src/admin_user.js", name="admin_user.js", extension=".js", size=50, content="")
    db_session.add_all([file_a, file_b, file_b_admin])
    db_session.commit()

    output_a, summary_a = agent_service.execute_find_repository_files(
        db=db_session,
        repository_id=repo_a.id,
        pattern="user",
    )

    # Should only find 1 file for Repo A, not Repo B's admin_user
    assert "admin_user.js" not in output_a
    assert "1 files" in summary_a


def test_agent_tools_cross_repository_structure_isolation(db_session):
    """Ensure get_repository_structure accurately counts only the requested repository's files."""
    repo_a = Repository(name="RepoA", full_name="org/repo-a", github_url="https://github.com/org/repo-a")
    repo_b = Repository(name="RepoB", full_name="org/repo-b", github_url="https://github.com/org/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    for i in range(3):
        db_session.add(RepositoryFile(repository_id=repo_a.id, path=f"file_a_{i}.py", name=f"file_{i}.py", extension=".py", size=10, content=""))
    for i in range(7):
        db_session.add(RepositoryFile(repository_id=repo_b.id, path=f"file_b_{i}.py", name=f"file_{i}.py", extension=".py", size=10, content=""))
    db_session.commit()

    output_a, summary_a = agent_service.execute_get_repository_structure(db=db_session, repository_id=repo_a.id)
    output_b, summary_b = agent_service.execute_get_repository_structure(db=db_session, repository_id=repo_b.id)

    assert "Total Indexed Files: 3" in output_a
    assert "Total Indexed Files: 7" in output_b
    assert "3 files" in summary_a
    assert "7 files" in summary_b
