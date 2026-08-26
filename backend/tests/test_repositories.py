"""
Tests for the /api/repositories endpoints.

Each test uses the 'client' fixture from conftest.py, which:
  - Routes requests to our FastAPI app without a real server
  - Uses a database session that rolls back after each test
    so test data never persists between tests
"""

import pytest


# -------------------------------------------------------------------------
# POST /api/repositories — create
# -------------------------------------------------------------------------

def test_create_repository_returns_201(client):
    """Creating a valid repository should return 201 Created."""
    response = client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/testowner/testrepo"},
    )
    assert response.status_code == 201


def test_create_repository_response_shape(client):
    """The response should contain all expected fields."""
    response = client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/testowner/shape-check"},
    )
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "full_name" in data
    assert "github_url" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_repository_parses_name(client):
    """The service should extract name and full_name from the GitHub URL."""
    response = client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/alice/my-project"},
    )
    data = response.json()
    assert data["name"] == "my-project"
    assert data["full_name"] == "alice/my-project"


def test_create_repository_with_description(client):
    """Optional description should be saved and returned."""
    response = client.post(
        "/api/repositories",
        json={
            "github_url": "https://github.com/testowner/described-repo",
            "description": "A test repository",
        },
    )
    data = response.json()
    assert data["description"] == "A test repository"


def test_create_repository_invalid_url_returns_422(client):
    """A non-URL string should fail Pydantic validation with 422."""
    response = client.post(
        "/api/repositories",
        json={"github_url": "not-a-url"},
    )
    assert response.status_code == 422


def test_create_repository_missing_url_returns_422(client):
    """Missing github_url should return 422."""
    response = client.post("/api/repositories", json={})
    assert response.status_code == 422


def test_create_duplicate_repository_returns_400(client):
    """Submitting the same URL twice should return 400 with a clear message."""
    url = "https://github.com/testowner/duplicate-repo"
    client.post("/api/repositories", json={"github_url": url})
    response = client.post("/api/repositories", json={"github_url": url})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


# -------------------------------------------------------------------------
# GET /api/repositories — list
# -------------------------------------------------------------------------

def test_list_repositories_returns_200(client):
    """Listing repositories should return HTTP 200."""
    response = client.get("/api/repositories")
    assert response.status_code == 200


def test_list_repositories_returns_list(client):
    """The response body should be a JSON array."""
    response = client.get("/api/repositories")
    assert isinstance(response.json(), list)


def test_list_repositories_includes_created(client):
    """A repository created in this test should appear in the list."""
    client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/testowner/listed-repo"},
    )
    response = client.get("/api/repositories")
    urls = [r["github_url"] for r in response.json()]
    assert "https://github.com/testowner/listed-repo" in urls


# -------------------------------------------------------------------------
# GET /api/repositories/{id} — get by ID
# -------------------------------------------------------------------------

def test_get_repository_by_id_returns_200(client):
    """Fetching an existing repository by ID should return 200."""
    create_response = client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/testowner/fetch-by-id"},
    )
    repo_id = create_response.json()["id"]

    response = client.get(f"/api/repositories/{repo_id}")
    assert response.status_code == 200
    assert response.json()["id"] == repo_id


def test_get_nonexistent_repository_returns_404(client):
    """Fetching a UUID that doesn't exist should return 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/repositories/{fake_id}")
    assert response.status_code == 404


# -------------------------------------------------------------------------
# DELETE /api/repositories/{id}
# -------------------------------------------------------------------------

def test_delete_repository_returns_204(client):
    """Deleting an existing repository should return 204 No Content."""
    create_response = client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/testowner/to-delete"},
    )
    repo_id = create_response.json()["id"]

    response = client.delete(f"/api/repositories/{repo_id}")
    assert response.status_code == 204


def test_delete_repository_removes_it(client):
    """After deletion, the repository should no longer be retrievable."""
    create_response = client.post(
        "/api/repositories",
        json={"github_url": "https://github.com/testowner/really-deleted"},
    )
    repo_id = create_response.json()["id"]

    client.delete(f"/api/repositories/{repo_id}")
    get_response = client.get(f"/api/repositories/{repo_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_repository_returns_404(client):
    """Deleting a UUID that doesn't exist should return 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/api/repositories/{fake_id}")
    assert response.status_code == 404
