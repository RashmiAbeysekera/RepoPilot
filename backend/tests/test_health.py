"""
Tests for GET /api/health.
"""


def test_health_returns_200(client_no_db):
    """The health endpoint should always return HTTP 200."""
    response = client_no_db.get("/api/health")
    assert response.status_code == 200


def test_health_response_shape(client_no_db):
    """The response must contain 'status', 'backend', and 'database' keys."""
    response = client_no_db.get("/api/health")
    data = response.json()
    assert "status" in data
    assert "backend" in data
    assert "database" in data


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
