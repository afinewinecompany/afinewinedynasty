import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test basic health check endpoint."""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "A Fine Wine Dynasty API"
    assert data["version"] == "0.1.0"


def test_detailed_health_check(client: TestClient):
    """Test detailed health check endpoint."""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "A Fine Wine Dynasty API"
    assert data["version"] == "0.1.0"
    assert "uptime" in data
    assert "database" in data
    assert "redis" in data