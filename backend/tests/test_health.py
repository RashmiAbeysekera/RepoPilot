"""
Tests for GET /api/health.
"""


def test_health_returns_200(client_no_db):
    """The health endpoint should always return HTTP 200."""
    response = client_no_db.get("/api/health")
    assert response.status_code == 200


def test_health_response_shape(client_no_db):
    """The response must contain 'status', 'backend', 'database', 'ai', and 'github' keys."""
    response = client_no_db.get("/api/health")
    data = response.json()
    assert "status" in data
    assert "backend" in data
    assert "database" in data
    assert "ai" in data
    assert "github" in data


def test_health_backend_is_healthy(client_no_db):
    """If the server is running, backend should always be 'healthy'."""
    response = client_no_db.get("/api/health")
    data = response.json()
    assert data["backend"] == "healthy"


def test_health_database_is_healthy(client_no_db):
    """Database should be reachable if DATABASE_URL is configured correctly."""
    response = client_no_db.get("/api/health")
    data = response.json()
    assert data["database"] == "healthy", (
        f"Database reported unhealthy — check DATABASE_URL. Got: {data}"
    )


def test_health_overall_status_when_db_healthy(client_no_db):
    """Overall status should be 'healthy' when both backend and database are up."""
    response = client_no_db.get("/api/health")
    data = response.json()
    if data["database"] == "healthy":
        assert data["status"] == "healthy"
    else:
        assert data["status"] == "degraded"


def test_health_ai_configured_and_unconfigured(client_no_db):
    """Test AI status reporting when GEMINI_API_KEY is configured vs unconfigured."""
    from unittest.mock import patch

    with patch("app.main.check_gemini_health", return_value="healthy"):
        resp = client_no_db.get("/api/health")
        assert resp.json()["ai"] == "healthy"

    with patch("app.main.check_gemini_health", return_value="not-configured"):
        resp = client_no_db.get("/api/health")
        assert resp.json()["ai"] == "not-configured"


def test_health_github_reachable_and_unreachable(client_no_db):
    """Test GitHub status reporting when reachable vs network failure."""
    from unittest.mock import patch

    with patch("app.main.check_github_health", return_value="healthy"):
        resp = client_no_db.get("/api/health")
        assert resp.json()["github"] == "healthy"

    with patch("app.main.check_github_health", return_value="unavailable"):
        resp = client_no_db.get("/api/health")
        assert resp.json()["github"] == "unavailable"
