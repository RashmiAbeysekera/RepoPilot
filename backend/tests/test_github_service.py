"""
Tests for github_service (URL parsing and GitHub REST API integration).
"""

from unittest.mock import MagicMock, patch
import pytest
from app.services.github_service import (
    fetch_repository_contents,
    fetch_repository_metadata,
    parse_github_url,
)


def test_parse_github_url_valid():
    owner, repo = parse_github_url("https://github.com/facebook/react")
    assert owner == "facebook"
    assert repo == "react"


def test_parse_github_url_with_git_suffix():
    owner, repo = parse_github_url("https://github.com/facebook/react.git")
    assert owner == "facebook"
    assert repo == "react"


def test_parse_github_url_trailing_slash():
    owner, repo = parse_github_url("https://github.com/facebook/react/")
    assert owner == "facebook"
    assert repo == "react"


def test_parse_github_url_invalid_domain():
    with pytest.raises(ValueError, match="valid GitHub repository link"):
        parse_github_url("https://google.com/facebook/react")


def test_parse_github_url_invalid_plain_string():
    with pytest.raises(ValueError, match="valid GitHub repository link"):
        parse_github_url("hello")


def test_parse_github_url_incomplete_path():
    with pytest.raises(ValueError, match="both owner and repository name"):
        parse_github_url("https://github.com/onlyowner")



def test_fetch_repository_metadata_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "react",
        "full_name": "facebook/react",
        "html_url": "https://github.com/facebook/react",
        "description": "The library for web and native user interfaces.",
        "default_branch": "main",
    }

    with patch("httpx.Client.get", return_value=mock_response):
        metadata = fetch_repository_metadata("facebook", "react")
        assert metadata["name"] == "react"
        assert metadata["full_name"] == "facebook/react"
        assert metadata["default_branch"] == "main"


def test_fetch_repository_metadata_not_found():
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.Client.get", return_value=mock_response):
        with pytest.raises(ValueError, match="not found or is private"):
            fetch_repository_metadata("nonexistent", "fake-repo")


def test_fetch_repository_contents_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"name": "README.md", "path": "README.md", "type": "file"},
        {"name": "src", "path": "src", "type": "dir"},
    ]

    with patch("httpx.Client.get", return_value=mock_response):
        contents = fetch_repository_contents("facebook", "react")
        assert len(contents) == 2
        assert contents[0]["name"] == "README.md"
