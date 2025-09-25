"""
Test configuration and fixtures for the API tests.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client fixture"""
    return TestClient(app)


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "email": "testuser@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }


@pytest.fixture
def sample_login_data():
    """Sample login data for testing"""
    return {
        "email": "testuser@example.com",
        "password": "TestPassword123!"
    }


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure async test backend"""
    return "asyncio"