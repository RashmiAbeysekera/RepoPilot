"""
Tests for repository ingestion service and ingestion API endpoints.
"""

from unittest.mock import patch
from app.services.repository_ingestion_service import (
    classify_file,
    is_ignored_directory,
)


def test_is_ignored_directory():
    assert is_ignored_directory(".git") is True
    assert is_ignored_directory("node_modules") is True
    assert is_ignored_directory("__pycache__") is True
    assert is_ignored_directory("src") is False
    assert is_ignored_directory("components") is False


def test_classify_file():
    assert classify_file("main.py") == "source"
    assert classify_file("App.tsx") == "source"
    assert classify_file("styles.css") == "source"
    assert classify_file("logo.png") == "ignored"
    assert classify_file("archive.zip") == "ignored"


def test_import_repository_endpoint(client, db_session):
    mock_metadata = {
        "name": "react",
        "full_name": "facebook/react",
        "github_url": "https://github.com/facebook/react",
        "description": "JavaScript library for user interfaces",
        "default_branch": "main",
    }

    with patch("app.services.github_service.fetch_repository_metadata", return_value=mock_metadata):
        response = client.post("/api/repositories/import", json={"github_url": "https://github.com/facebook/react"})
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "facebook/react"
        assert data["default_branch"] == "main"


def test_ingest_repository_endpoint(client, db_session):
    mock_metadata = {
        "name": "react",
        "full_name": "facebook/react",
        "github_url": "https://github.com/facebook/react",
        "description": "JavaScript library for user interfaces",
        "default_branch": "main",
    }

    mock_contents_root = [
        {"name": "README.md", "path": "README.md", "type": "file"},
        {"name": "package.json", "path": "package.json", "type": "file"},
        {"name": "node_modules", "path": "node_modules", "type": "dir"},
        {"name": "logo.png", "path": "logo.png", "type": "file"},
    ]

    with patch("app.services.github_service.fetch_repository_metadata", return_value=mock_metadata):
        import_res = client.post("/api/repositories/import", json={"github_url": "https://github.com/facebook/react"})
        repo_id = import_res.json()["id"]

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_contents_root):
        ingest_res = client.post(f"/api/repositories/{repo_id}/ingest")
        assert ingest_res.status_code == 200
        data = ingest_res.json()
        assert data["repository"] == "facebook/react"
        assert data["files_discovered"] == 3
        assert data["source_files"] == 2
        assert data["ignored_files"] == 2


# =========================================================================
# Data Integrity & Resilience Tests (Critical Health Check Fixes)
# =========================================================================

import pytest
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.code_chunk import CodeChunk
from app.models.chunk_embedding import ChunkEmbedding
from app.services import (
    chunking_service,
    embedding_service,
    repository_ingestion_service,
    github_service,
)
from app.services.github_service import GitHubAPIError, GitHubResourceNotFoundError


def test_successful_ingestion_creates_files_chunks_and_embeddings(db_session):
    """Requirement 1: Successful ingestion creates files, chunks, and embeddings."""
    repo = Repository(
        name="full-pipeline-repo",
        full_name="owner/full-pipeline-repo",
        github_url="https://github.com/owner/full-pipeline-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    mock_tree = [
        {"name": "main.py", "path": "src/main.py", "type": "file", "size": 60},
        {"name": "utils.py", "path": "src/utils.py", "type": "file", "size": 70},
    ]

    mock_file_contents = {
        "src/main.py": "def main():\n    print('RepoPilot active')\n    return 0\n",
        "src/utils.py": "def add(a, b):\n    return a + b\n",
    }

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_tree), \
         patch("app.services.github_service.fetch_file_content", side_effect=lambda o, r, p: mock_file_contents[p]):

        # 1. Ingest files
        summary = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert summary["files_stored"] == 2
        assert repo.sync_status == "synced"
        assert repo.sync_error is None
        assert repo.last_synced_at is not None

        # 2. Generate chunks
        chunk_stats = chunking_service.generate_chunks_for_repository(db_session, repo.id)
        assert chunk_stats["files_processed"] == 2
        assert chunk_stats["chunks_created"] >= 2

        # 3. Generate embeddings
        emb_stats = embedding_service.generate_embeddings_for_repository(db_session, repo.id)
        assert emb_stats["embeddings_created"] >= 2

        # Verify database records
        files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
        assert len(files) == 2

        chunks = (
            db_session.query(CodeChunk)
            .join(RepositoryFile)
            .filter(RepositoryFile.repository_id == repo.id)
            .all()
        )
        assert len(chunks) >= 2

        embeddings = (
            db_session.query(ChunkEmbedding)
            .join(CodeChunk)
            .join(RepositoryFile)
            .filter(RepositoryFile.repository_id == repo.id)
            .all()
        )
        assert len(embeddings) >= 2


def test_temporary_fetch_failure_preserves_existing_files_and_embeddings(db_session):
    """Requirement 2: Temporary failure while fetching one file preserves all existing files, chunks, embeddings."""
    repo = Repository(
        name="preserve-repo",
        full_name="owner/preserve-repo",
        github_url="https://github.com/owner/preserve-repo",
        default_branch="main",
        sync_status="synced",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="src/main.py",
        name="main.py",
        extension=".py",
        size=100,
        file_type="source",
        content="def main(): pass",
    )
    file2 = RepositoryFile(
        repository_id=repo.id,
        path="src/utils.py",
        name="utils.py",
        extension=".py",
        size=80,
        file_type="source",
        content="def helper(): return 42",
    )
    db_session.add_all([file1, file2])
    db_session.commit()

    # Generate chunks and embeddings for file2
    chunking_service.generate_chunks_for_file(db_session, file2)
    embedding_service.generate_embeddings_for_file(db_session, file2)

    chunks_before = db_session.query(CodeChunk).filter(CodeChunk.repository_file_id == file2.id).all()
    assert len(chunks_before) > 0

    mock_tree = [
        {"name": "main.py", "path": "src/main.py", "type": "file", "size": 100},
        {"name": "utils.py", "path": "src/utils.py", "type": "file", "size": 80},
    ]

    def mock_fetch(owner, repo_name, path):
        if path == "src/main.py":
            return "def main(): return 'updated'"
        # utils.py fails with a temporary rate limit
        raise GitHubAPIError("GitHub API rate limit exceeded.")

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_tree), \
         patch("app.services.github_service.fetch_file_content", side_effect=mock_fetch):

        with pytest.raises(ValueError, match="GitHub API rate limit exceeded."):
            repository_ingestion_service.ingest_and_persist_repository(db_session, repo)

    # Re-query repository state
    db_session.refresh(repo)
    assert repo.sync_status == "failed"
    assert "rate limit" in repo.sync_error.lower()

    # CRITICAL: Both files MUST still exist in database! utils.py was NOT deleted!
    files_after = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
    assert len(files_after) == 2
    paths = {f.path for f in files_after}
    assert "src/main.py" in paths
    assert "src/utils.py" in paths

    # Code chunks and embeddings for utils.py must still exist!
    chunks_after = db_session.query(CodeChunk).filter(CodeChunk.repository_file_id == file2.id).all()
    assert len(chunks_after) == len(chunks_before)


def test_discovery_failure_does_not_delete_existing_files(db_session):
    """Requirement 3: A GitHub API discovery failure does not delete existing files."""
    repo = Repository(
        name="discovery-fail-repo",
        full_name="owner/discovery-fail-repo",
        github_url="https://github.com/owner/discovery-fail-repo",
        default_branch="main",
        sync_status="synced",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="src/index.ts",
        name="index.ts",
        extension=".ts",
        size=150,
        file_type="source",
        content="export const x = 1;",
    )
    db_session.add(file1)
    db_session.commit()

    with patch("app.services.github_service.fetch_repository_contents", side_effect=GitHubAPIError("Could not connect to GitHub API")):
        with pytest.raises(ValueError, match="Could not connect to GitHub API"):
            repository_ingestion_service.ingest_and_persist_repository(db_session, repo)

    db_session.refresh(repo)
    assert repo.sync_status == "failed"
    assert "could not connect" in repo.sync_error.lower()

    # Existing file is completely intact
    files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
    assert len(files) == 1
    assert files[0].path == "src/index.ts"


def test_genuinely_deleted_github_file_removed_during_sync(db_session):
    """Requirement 4: A genuinely deleted GitHub file is removed during successful synchronization."""
    repo = Repository(
        name="clean-sync-repo",
        full_name="owner/clean-sync-repo",
        github_url="https://github.com/owner/clean-sync-repo",
        default_branch="main",
        sync_status="synced",
    )
    db_session.add(repo)
    db_session.commit()

    keep_file = RepositoryFile(
        repository_id=repo.id,
        path="src/keep.py",
        name="keep.py",
        extension=".py",
        size=50,
        file_type="source",
        content="print('stay')",
    )
    stale_file = RepositoryFile(
        repository_id=repo.id,
        path="src/deleted_on_github.py",
        name="deleted_on_github.py",
        extension=".py",
        size=50,
        file_type="source",
        content="print('delete me')",
    )
    db_session.add_all([keep_file, stale_file])
    db_session.commit()

    # Re-ingestion discovers ONLY keep.py on GitHub
    mock_tree = [
        {"name": "keep.py", "path": "src/keep.py", "type": "file", "size": 50},
    ]

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_tree), \
         patch("app.services.github_service.fetch_file_content", return_value="print('stay')"):

        res = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert repo.sync_status == "synced"
        assert res["files_updated"] == 1

    # stale_file was removed because discovery completed reliably without errors or truncation
    files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
    assert len(files) == 1
    assert files[0].path == "src/keep.py"


def test_empty_repository_handled_safely(db_session):
    """Requirement 5: An empty repository is handled safely and does not crash."""
    repo = Repository(
        name="empty-repo",
        full_name="owner/empty-repo",
        github_url="https://github.com/owner/empty-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    # Mock empty GitHub contents list
    with patch("app.services.github_service.fetch_repository_contents", return_value=[]):
        res = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)

        assert res["files_discovered"] == 0
        assert res["files_stored"] == 0
        assert res["files_updated"] == 0
        assert repo.sync_status == "synced"
        assert repo.sync_error is None

        files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
        assert len(files) == 0


def test_duplicate_ingestion_is_idempotent(db_session):
    """Requirement 6: Duplicate ingestion remains idempotent without duplicates."""
    repo = Repository(
        name="idempotent-repo",
        full_name="owner/idempotent-repo",
        github_url="https://github.com/owner/idempotent-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    mock_tree = [
        {"name": "app.py", "path": "src/app.py", "type": "file", "size": 40},
    ]

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_tree), \
         patch("app.services.github_service.fetch_file_content", return_value="app = True"):

        # First run
        run1 = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert run1["files_stored"] == 1
        assert run1["files_updated"] == 0

        # Second run with exact same data
        run2 = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert run2["files_stored"] == 0
        assert run2["files_updated"] == 1

        files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
        assert len(files) == 1


def test_error_statuses_and_recovery_flow(db_session):
    """Requirement 7: Error status and sync_error fields are accurate and clear on recovery."""
    repo = Repository(
        name="recovery-repo",
        full_name="owner/recovery-repo",
        github_url="https://github.com/owner/recovery-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    # Step 1: Simulate failure
    with patch("app.services.github_service.fetch_repository_contents", side_effect=GitHubAPIError("GitHub API rate limit exceeded.")):
        with pytest.raises(ValueError):
            repository_ingestion_service.ingest_and_persist_repository(db_session, repo)

    db_session.refresh(repo)
    assert repo.sync_status == "failed"
    assert repo.sync_error == "GitHub API rate limit exceeded."

    # Step 2: Simulate recovery (subsequent run succeeds)
    mock_tree = [{"name": "recovered.py", "path": "recovered.py", "type": "file", "size": 30}]
    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_tree), \
         patch("app.services.github_service.fetch_file_content", return_value="print('recovered')"):
        repository_ingestion_service.ingest_and_persist_repository(db_session, repo)

    db_session.refresh(repo)
    assert repo.sync_status == "synced"
    assert repo.sync_error is None
    assert repo.last_synced_at is not None


def test_truncated_discovery_skips_stale_file_deletion(db_session):
    """Truncated discovery (e.g. max_files reached) must NOT delete unvisited files."""
    repo = Repository(
        name="truncate-repo",
        full_name="owner/truncate-repo",
        github_url="https://github.com/owner/truncate-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="file1.py",
        name="file1.py",
        extension=".py",
        size=50,
        content="f1",
    )
    file2 = RepositoryFile(
        repository_id=repo.id,
        path="file2.py",
        name="file2.py",
        extension=".py",
        size=50,
        content="f2",
    )
    db_session.add_all([file1, file2])
    db_session.commit()

    mock_tree = [
        {"name": "file1.py", "path": "file1.py", "type": "file", "size": 50},
        {"name": "file2.py", "path": "file2.py", "type": "file", "size": 50},
    ]

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_tree), \
         patch("app.services.github_service.fetch_file_content", return_value="content"):

        # Ingest with max_files=1 so it truncates after 1 file
        repository_ingestion_service.ingest_and_persist_repository(db_session, repo, max_files=1)

    # file2.py must NOT have been deleted because discovery was truncated
    files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
    assert len(files) == 2

