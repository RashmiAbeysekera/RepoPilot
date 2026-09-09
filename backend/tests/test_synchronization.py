import uuid
import hmac
import hashlib
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk
from app.models.chunk_embedding import ChunkEmbedding
from app.services import repository_ingestion_service, search_service, rag_service, embedding_service


# -------------------------------------------------------------------------
# Webhook and Sync Router tests
# -------------------------------------------------------------------------

def test_webhook_invalid_signature(client, db_session):
    """Test 8: Webhook returns 401 when signature validation fails."""
    # Configure webhook secret in config
    with patch("app.api.webhooks.get_github_webhook_secret", return_value="real_secret"):
        headers = {
            "x-github-event": "push",
            "x-hub-signature-256": "sha256=invalidsignaturehere",
        }
        res = client.post("/api/webhooks/github", json={"repository": {"full_name": "owner/repo"}}, headers=headers)
        assert res.status_code == 401
        assert "Signature validation failed" in res.json()["detail"]


def test_webhook_unsupported_event(client, db_session):
    """Test 9: Webhook skips processing for unsupported event types."""
    with patch("app.api.webhooks.get_github_webhook_secret", return_value=None):
        headers = {
            "x-github-event": "issues",
        }
        res = client.post("/api/webhooks/github", json={}, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "skipped"
        assert "Unsupported event" in res.json()["message"]



def test_webhook_unknown_repository(client, db_session):
    """Test 10: Webhook returns 404 for repositories not in database."""
    with patch("app.api.webhooks.get_github_webhook_secret", return_value=None):
        headers = {
            "x-github-event": "push",
        }
        res = client.post(
            "/api/webhooks/github",
            json={"repository": {"full_name": "nonexistent/repo"}, "ref": "refs/heads/main"},
            headers=headers
        )
        assert res.status_code == 404
        assert "not registered" in res.json()["detail"]


# -------------------------------------------------------------------------
# Incremental sync service tests
# -------------------------------------------------------------------------

def test_sync_success_workflow(db_session: Session):
    """Test 14, 1, 2, 3: Verify successful addition, modification, and deletion workflow."""
    # Seed repository
    repo = Repository(
        name="SyncRepo",
        full_name="owner/syncrepo",
        github_url="https://github.com/owner/syncrepo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    # Pre-populate repository with one file
    file_old = RepositoryFile(
        repository_id=repo.id,
        path="src/old.py",
        name="old.py",
        extension=".py",
        size=100,
        file_type="source",
        content="def old(): pass",
    )
    file_modified = RepositoryFile(
        repository_id=repo.id,
        path="src/modified.py",
        name="modified.py",
        extension=".py",
        size=100,
        file_type="source",
        content="def greet():\n    print('hello')\n",
    )
    db_session.add_all([file_old, file_modified])
    db_session.commit()

    # Mock github fetch content
    mock_file_contents = {
        "src/added.py": "def new_func():\n    return 42\n",
        "src/modified.py": "def greet():\n    print('hello world!')\n    return True\n",
    }

    def mock_fetch(owner, repo, path):
        return mock_file_contents.get(path)

    with patch("app.services.github_service.fetch_file_content", side_effect=mock_fetch):
        # Trigger incremental synchronization
        # Added: src/added.py
        # Modified: src/modified.py
        # Deleted: src/old.py
        result = repository_ingestion_service.sync_repository_changes(
            db=db_session,
            repository=repo,
            added_paths=["src/added.py"],
            modified_paths=["src/modified.py"],
            deleted_paths=["src/old.py"],
            commit_sha="commitsha123456",
        )

        assert result["sync_status"] == "synced"
        assert "src/added.py" in result["files_added"]
        assert "src/modified.py" in result["files_modified"]
        assert "src/old.py" in result["files_deleted"]

        # Assert database updates
        # 1. src/old.py should be deleted
        deleted_file = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id, RepositoryFile.path == "src/old.py").first()
        assert deleted_file is None

        # 2. src/modified.py should have new content
        mod_file = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id, RepositoryFile.path == "src/modified.py").first()
        assert mod_file is not None
        assert "hello world!" in mod_file.content

        # 3. src/added.py should exist in database
        add_file = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id, RepositoryFile.path == "src/added.py").first()
        assert add_file is not None
        assert "new_func" in add_file.content

        # Verify chunks and embeddings were generated
        chunks = db_session.query(CodeChunk).filter(CodeChunk.repository_file_id == add_file.id).all()
        assert len(chunks) == 1
        assert "new_func" in chunks[0].content

        emb = db_session.query(ChunkEmbedding).filter(ChunkEmbedding.code_chunk_id == chunks[0].id).first()
        assert emb is not None
        assert len(emb.embedding) == 384


def test_sync_unsupported_and_oversized_files(db_session: Session):
    """Test 4, 5: Verify unsupported extensions and oversized files are skipped during sync."""
    repo = Repository(
        name="FilterRepo",
        full_name="owner/filterrepo",
        github_url="https://github.com/owner/filterrepo",
    )
    db_session.add(repo)
    db_session.commit()

    # Added: image (unsupported), big_file (oversized)
    mock_file_contents = {
        "src/logo.png": "binary_content_mock",
        "src/large.py": "x" * 600000, # Max is 500_000
    }

    def mock_fetch(owner, repo, path):
        return mock_file_contents.get(path)

    with patch("app.services.github_service.fetch_file_content", side_effect=mock_fetch):
        result = repository_ingestion_service.sync_repository_changes(
            db=db_session,
            repository=repo,
            added_paths=["src/logo.png", "src/large.py"],
            modified_paths=[],
            deleted_paths=[],
        )

        assert "src/logo.png" in result["files_skipped"]
        assert "src/large.py" in result["files_skipped"]
        assert len(result["files_added"]) == 0


def test_repository_isolation(db_session: Session):
    """Test 6: Verify sync operations on Repo A do not affect Repo B files/chunks/embeddings."""
    repo_a = Repository(name="RepoA", full_name="owner/repo-a", github_url="https://github.com/owner/repo-a")
    repo_b = Repository(name="RepoB", full_name="owner/repo-b", github_url="https://github.com/owner/repo-b")
    db_session.add_all([repo_a, repo_b])
    db_session.commit()

    # Prepopulate Repo B
    file_b = RepositoryFile(
        repository_id=repo_b.id,
        path="src/shared.py",
        name="shared.py",
        extension=".py",
        size=100,
        content="def b_func(): pass",
    )
    db_session.add(file_b)
    db_session.commit()

    # Generate chunks for B
    chunk_b = CodeChunk(repository_file_id=file_b.id, chunk_index=0, start_line=1, end_line=1, content="def b_func(): pass")
    db_session.add(chunk_b)
    db_session.commit()

    # Sync Repo A stating "src/shared.py" is deleted. Repo B's file should remain intact.
    result = repository_ingestion_service.sync_repository_changes(
        db=db_session,
        repository=repo_a,
        added_paths=[],
        modified_paths=[],
        deleted_paths=["src/shared.py"], # Same name path
    )

    # Repo B's file and chunk should still exist
    stored_b = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo_b.id, RepositoryFile.path == "src/shared.py").first()
    assert stored_b is not None
    assert stored_b.id == file_b.id


def test_sync_idempotency_duplicate_webhook(db_session: Session):
    """Test 7, 16: Verify duplicate webhooks are safe and do not create duplicate chunks/embeddings."""
    repo = Repository(
        name="IdempotentRepo",
        full_name="owner/idemrepo",
        github_url="https://github.com/owner/idemrepo",
    )
    db_session.add(repo)
    db_session.commit()

    mock_file_contents = {
        "src/main.py": "def run():\n    print('running')\n",
    }

    with patch("app.services.github_service.fetch_file_content", return_value=mock_file_contents["src/main.py"]):
        # First sync
        repository_ingestion_service.sync_repository_changes(
            db=db_session,
            repository=repo,
            added_paths=["src/main.py"],
            modified_paths=[],
            deleted_paths=[],
        )

        # Count chunks in DB
        file_rec = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id, RepositoryFile.path == "src/main.py").first()
        chunk_count_1 = db_session.query(CodeChunk).filter(CodeChunk.repository_file_id == file_rec.id).count()
        assert chunk_count_1 == 1

        # Duplicate webhook (send same sync again)
        repository_ingestion_service.sync_repository_changes(
            db=db_session,
            repository=repo,
            added_paths=["src/main.py"],
            modified_paths=[],
            deleted_paths=[],
        )

        # Count chunks in DB again — should still be 1 (not duplicated)
        chunk_count_2 = db_session.query(CodeChunk).filter(CodeChunk.repository_file_id == file_rec.id).count()
        assert chunk_count_2 == 1


def test_github_api_failure_preserves_records(db_session: Session):
    """Test 11, 15: Verify GitHub API failure aborts sync and leaves existing DB data intact."""
    repo = Repository(
        name="FailureRepo",
        full_name="owner/failurerepo",
        github_url="https://github.com/owner/failurerepo",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    repo_id = repo.id

    # Prepopulate database
    file_rec = RepositoryFile(
        repository_id=repo_id,
        path="src/main.py",
        name="main.py",
        extension=".py",
        size=100,
        content="def main(): pass",
    )
    db_session.add(file_rec)
    db_session.commit()

    # Mock github fetch content to raise ValueError (simulating rate limit / API down)
    with patch("app.services.github_service.fetch_file_content", side_effect=ValueError("Rate limit exceeded")):
        with pytest.raises(ValueError):
            repository_ingestion_service.sync_repository_changes(
                db=db_session,
                repository=repo,
                added_paths=[],
                modified_paths=["src/main.py"], # Modified path fails retrieval
                deleted_paths=[],
            )

        # Assert repository status is set to failed on fresh record
        repo_fresh = db_session.query(Repository).filter(Repository.id == repo_id).first()
        assert repo_fresh.sync_status == "failed"
        assert "Rate limit exceeded" in repo_fresh.sync_error

        # Verify old database record is preserved (not deleted)
        stored_file = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo_id, RepositoryFile.path == "src/main.py").first()
        assert stored_file is not None
        assert stored_file.content == "def main(): pass"  # Kept intact!




# -------------------------------------------------------------------------
# Semantic Search & RAG consistency tests
# -------------------------------------------------------------------------

def test_semantic_search_and_rag_consistency_after_sync(db_session: Session):
    """Test 17, 18, 19: Verify updated content is retrieved by search & RAG, and deleted is not."""
    repo = Repository(
        name="SearchRagRepo",
        full_name="owner/searchragrepo",
        github_url="https://github.com/owner/searchragrepo",
    )
    db_session.add(repo)
    db_session.commit()

    # Prepopulate repository with file to delete and file to modify
    file_delete = RepositoryFile(
        repository_id=repo.id,
        path="src/delete.py",
        name="delete.py",
        extension=".py",
        size=100,
        content="def handle_secrets():\n    return 'secretkey'\n",
    )
    file_modify = RepositoryFile(
        repository_id=repo.id,
        path="src/auth.py",
        name="auth.py",
        extension=".py",
        size=100,
        content="def login():\n    return 'old login'\n",
    )
    db_session.add_all([file_delete, file_modify])
    db_session.commit()

    # Chunk and embed prepopulated files
    chunk_del = CodeChunk(repository_file_id=file_delete.id, chunk_index=0, start_line=1, end_line=2, content=file_delete.content)
    chunk_mod = CodeChunk(repository_file_id=file_modify.id, chunk_index=0, start_line=1, end_line=2, content=file_modify.content)
    db_session.add_all([chunk_del, chunk_mod])
    db_session.commit()

    embedding_service.generate_embeddings_for_repository(db_session, repo.id)

    # Initial search returns deleted file contents
    init_res = search_service.search_repository_chunks(db_session, repo.id, "secrets", top_k=2)
    assert any(item["file_path"] == "src/delete.py" for item in init_res["results"])

    # Now execute sync:
    # 1. Delete delete.py
    # 2. Modify auth.py to have "new authentication workflow"
    mock_file_contents = {
        "src/auth.py": "def login():\n    return 'new authentication workflow'\n",
    }
    with patch("app.services.github_service.fetch_file_content", side_effect=lambda owner, repo, path: mock_file_contents.get(path)):
        repository_ingestion_service.sync_repository_changes(
            db=db_session,
            repository=repo,
            added_paths=[],
            modified_paths=["src/auth.py"],
            deleted_paths=["src/delete.py"],
        )

    # Verify search after sync:
    # - "secrets" search should return NOTHING since file was deleted
    search_del = search_service.search_repository_chunks(db_session, repo.id, "secrets", top_k=5)
    assert not any(item["file_path"] == "src/delete.py" for item in search_del["results"])

    # - "authentication workflow" search should retrieve the new content of auth.py
    search_mod = search_service.search_repository_chunks(db_session, repo.id, "authentication workflow", top_k=5)
    assert len(search_mod["results"]) > 0
    assert search_mod["results"][0]["file_path"] == "src/auth.py"
    assert "new authentication workflow" in search_mod["results"][0]["content"]

    # Verify RAG gets the new content
    with patch("app.services.gemini_service.generate_rag_answer", return_value="Using new authentication workflow") as mock_gemini:
        rag_res = rag_service.answer_repository_question(db_session, repo.id, "How do we login?")
        assert rag_res["answer"] == "Using new authentication workflow"
        
        # Verify context sent to Gemini contains the updated chunk content
        user_prompt = mock_gemini.call_args[1]["user_prompt"]
        assert "new authentication workflow" in user_prompt
        assert "old login" not in user_prompt
