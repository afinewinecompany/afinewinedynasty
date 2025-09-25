import pytest
from fastapi.testclient import TestClient


def test_get_prospects(client: TestClient):
    """Test getting list of prospects."""
    response = client.get("/api/v1/prospects/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:  # If there's data returned
        prospect = data[0]
        assert "id" in prospect
        assert "name" in prospect
        assert "position" in prospect
        assert "organization" in prospect


def test_get_single_prospect(client: TestClient):
    """Test getting a single prospect by ID."""
    prospect_id = 1
    response = client.get(f"/api/v1/prospects/{prospect_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == prospect_id
    assert "name" in data
    assert "position" in data
    assert "organization" in data
    assert "age" in data