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
