"""
Tests for RepositoryFile model, database relationships, constraints,
ingestion persistence, idempotency, and API endpoints.
"""

from unittest.mock import patch
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services import repository_ingestion_service, repository_service


def test_repository_file_model_creation(db_session):
    repo = Repository(
        name="test-repo",
        full_name="owner/test-repo",
        github_url="https://github.com/owner/test-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    repo_file = RepositoryFile(
        repository_id=repo.id,
        path="src/main.py",
        name="main.py",
        extension=".py",
        size=250,
        file_type="source",
        content="print('Hello World')",
    )
    db_session.add(repo_file)
    db_session.commit()
    db_session.refresh(repo_file)

    assert repo_file.id is not None
    assert repo_file.repository_id == repo.id
    assert repo_file.path == "src/main.py"
    assert repo_file.content == "print('Hello World')"


def test_repository_file_relationship_and_cascade_delete(db_session):
    repo = Repository(
        name="cascade-repo",
        full_name="owner/cascade-repo",
        github_url="https://github.com/owner/cascade-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="README.md",
        name="README.md",
        extension=".md",
        size=100,
        file_type="documentation",
    )
    file2 = RepositoryFile(
        repository_id=repo.id,
        path="app.py",
        name="app.py",
        extension=".py",
        size=200,
        file_type="source",
    )
    db_session.add_all([file1, file2])
    db_session.commit()

    # Relationship verification
    assert len(repo.files) == 2

    # Cascade delete on repository removal
    db_session.delete(repo)
    db_session.commit()

    orphaned_files = db_session.query(RepositoryFile).filter(
        RepositoryFile.repository_id == repo.id
    ).all()
    assert len(orphaned_files) == 0


def test_duplicate_repository_id_and_path_prevented(db_session):
    repo = Repository(
        name="unique-repo",
        full_name="owner/unique-repo",
        github_url="https://github.com/owner/unique-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="src/App.jsx",
        name="App.jsx",
        extension=".jsx",
        size=150,
        file_type="source",
    )
    db_session.add(file1)
    db_session.commit()

    file2 = RepositoryFile(
        repository_id=repo.id,
        path="src/App.jsx",
        name="App.jsx",
        extension=".jsx",
        size=150,
        file_type="source",
    )
    db_session.add(file2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_file_ingestion_stores_and_idempotency(db_session):
    repo = Repository(
        name="ingest-repo",
        full_name="owner/ingest-repo",
        github_url="https://github.com/owner/ingest-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    mock_contents = [
        {"name": "README.md", "path": "README.md", "type": "file", "size": 100},
        {"name": "main.py", "path": "main.py", "type": "file", "size": 200},
        {"name": "logo.png", "path": "logo.png", "type": "file", "size": 500},  # ignored
        {"name": "node_modules", "path": "node_modules", "type": "dir"},      # ignored
    ]

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_contents), \
         patch("app.services.github_service.fetch_file_content", return_value="dummy content"):
        
        # First Ingestion
        res1 = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert res1["files_stored"] == 2
        assert res1["files_updated"] == 0

        stored_files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
        assert len(stored_files) == 2

        # Second Ingestion (Idempotency)
        res2 = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert res2["files_stored"] == 0
        assert res2["files_updated"] == 2

        stored_files_after = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
        assert len(stored_files_after) == 2  # No duplicate rows created!


def test_oversized_and_ignored_files_skipped(db_session):
    repo = Repository(
        name="limits-repo",
        full_name="owner/limits-repo",
        github_url="https://github.com/owner/limits-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    mock_contents = [
        {"name": "huge.py", "path": "huge.py", "type": "file", "size": 1_000_000},  # Oversized (> 500 KB)
        {"name": "binary.exe", "path": "binary.exe", "type": "file", "size": 100},   # Unsupported extension
        {"name": "valid.py", "path": "valid.py", "type": "file", "size": 50},
    ]

    with patch("app.services.github_service.fetch_repository_contents", return_value=mock_contents), \
         patch("app.services.github_service.fetch_file_content", return_value="print('valid')"):

        res = repository_ingestion_service.ingest_and_persist_repository(db_session, repo)
        assert res["files_stored"] == 1
        assert res["files_skipped"] == 2
        assert res["skip_reasons"]["oversized"] == 1
        assert res["skip_reasons"]["unsupported_extension"] == 1


def test_list_and_single_file_api_endpoints(client, db_session):
    repo1 = Repository(
        name="api-repo-1",
        full_name="owner/api-repo-1",
        github_url="https://github.com/owner/api-repo-1",
        default_branch="main",
    )
    repo2 = Repository(
        name="api-repo-2",
        full_name="owner/api-repo-2",
        github_url="https://github.com/owner/api-repo-2",
        default_branch="main",
    )
    db_session.add_all([repo1, repo2])
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo1.id,
        path="src/index.js",
        name="index.js",
        extension=".js",
        size=300,
        file_type="source",
        content="console.log('Repo 1')",
    )
    file2 = RepositoryFile(
        repository_id=repo2.id,
        path="src/other.js",
        name="other.js",
        extension=".js",
        size=400,
        file_type="source",
        content="console.log('Repo 2')",
    )
    db_session.add_all([file1, file2])
    db_session.commit()

    # 1. GET /api/repositories/{repo1.id}/files
    list_res = client.get(f"/api/repositories/{repo1.id}/files")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total_files"] == 1
    assert list_data["files"][0]["path"] == "src/index.js"

    # 2. GET /api/repositories/{repo1.id}/files/{file1.id}
    detail_res = client.get(f"/api/repositories/{repo1.id}/files/{file1.id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["content"] == "console.log('Repo 1')"

    # 3. Cross-repository security check: GET /api/repositories/{repo1.id}/files/{file2.id}
    # file2 belongs to repo2, not repo1 -> Should return 404
    cross_res = client.get(f"/api/repositories/{repo1.id}/files/{file2.id}")
    assert cross_res.status_code == 404


def test_github_failure_preserves_existing_db_records(db_session):
    repo = Repository(
        name="fail-repo",
        full_name="owner/fail-repo",
        github_url="https://github.com/owner/fail-repo",
        default_branch="main",
    )
    db_session.add(repo)
    db_session.commit()

    file1 = RepositoryFile(
        repository_id=repo.id,
        path="src/index.ts",
        name="index.ts",
        extension=".ts",
        size=120,
        file_type="source",
        content="console.log('safe')",
    )
    db_session.add(file1)
    db_session.commit()

    # Simulate GitHub API Rate Limit failure during traversal
    with patch("app.services.github_service.fetch_repository_contents", side_effect=ValueError("GitHub API rate limit exceeded.")):
        with pytest.raises(ValueError, match="GitHub API rate limit exceeded."):
            repository_ingestion_service.ingest_and_persist_repository(db_session, repo)

    # Verify existing DB record remains intact and was NOT deleted
    files = db_session.query(RepositoryFile).filter(RepositoryFile.repository_id == repo.id).all()
    assert len(files) == 1
    assert files[0].path == "src/index.ts"
