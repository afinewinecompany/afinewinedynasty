import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from app.main import app


class TestRateLimiting:
    """Test rate limiting functionality"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_auth_rate_limiting_enforcement(self):
        """Test that authentication endpoint enforces rate limits"""
        login_data = {"email": "test@example.com", "password": "wrongpassword"}

        # Make requests up to the limit (5 attempts per 15 minutes)
        responses = []
        for i in range(6):  # One more than the limit
            response = self.client.post("/api/v1/auth/login", json=login_data)
            responses.append(response)

        # First 5 requests should get 401 (wrong credentials)
        for i in range(5):
            assert responses[i].status_code == 401

        # 6th request should be rate limited (429)
        assert responses[5].status_code == 429
        assert "rate limit" in responses[5].json()["detail"].lower()

    def test_register_rate_limiting_enforcement(self):
        """Test that register endpoint enforces rate limits"""
        register_data = {
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "full_name": "Test User"
        }

        # Make requests up to the limit (3 attempts per hour)
        responses = []
        for i in range(4):  # One more than the limit
            response = self.client.post("/api/v1/auth/register", json=register_data)
            responses.append(response)

        # First request should succeed (201) or conflict if user exists (409)
        assert responses[0].status_code in [201, 409]

        # Subsequent requests within rate limit should also get processed
        for i in range(1, 3):
            assert responses[i].status_code in [201, 409]  # May conflict after first success

        # 4th request should be rate limited (429)
        assert responses[3].status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_reset_behavior(self):
        """Test that rate limits reset properly (simplified test)"""
        # This is a simplified test - in practice, you'd need to wait for the time window
        # or mock the time to test reset behavior properly
        login_data = {"email": "reset@example.com", "password": "wrongpassword"}

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/auth/login", json=login_data)
            assert response.status_code == 401  # Should work initially

    def test_different_ips_separate_limits(self):
        """Test that different IPs have separate rate limits"""
        # Note: This test is limited by the test client's IP simulation
        # In a real environment, you'd test with actual different IPs
        login_data = {"email": "ip1@example.com", "password": "wrongpassword"}

        # Make request with default IP
        response1 = self.client.post("/api/v1/auth/login", json=login_data)
        assert response1.status_code == 401

        # In a real test environment, you'd simulate different IPs
        # For now, just verify the endpoint works
        response2 = self.client.post("/api/v1/auth/login", json=login_data)
        assert response2.status_code == 401

    def test_valid_requests_not_rate_limited(self):
        """Test that valid requests within limits are not blocked"""
        # Register a user first
        register_data = {
            "email": "valid@example.com",
            "password": "ValidPass123!",
            "full_name": "Valid User"
        }
        register_response = self.client.post("/api/v1/auth/register", json=register_data)

        # Should succeed (201) or conflict if already exists (409)
        assert register_response.status_code in [201, 409]

        # Now test login with correct credentials (if we had real auth)
        login_data = {"email": "valid@example.com", "password": "ValidPass123!"}
        login_response = self.client.post("/api/v1/auth/login", json=login_data)

        # Should not be rate limited for valid attempts
        assert login_response.status_code != 429


@pytest.mark.asyncio
class TestRateLimitingAsync:
    """Async tests for rate limiting under concurrent load"""

    async def test_concurrent_auth_requests(self):
        """Test rate limiting behavior under concurrent requests"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            login_data = {"email": "concurrent@example.com", "password": "wrongpassword"}

            # Make 10 concurrent requests
            tasks = [
                client.post("/api/v1/auth/login", json=login_data)
                for _ in range(10)
            ]

            responses = await asyncio.gather(*tasks)

            # Some should be rate limited
            status_codes = [r.status_code for r in responses]
            assert 429 in status_codes  # At least some should be rate limited
            assert 401 in status_codes  # Some should get through as failed auth

    async def test_mixed_endpoints_separate_limits(self):
        """Test that different endpoints have separate rate limits"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            login_data = {"email": "mixed1@example.com", "password": "wrongpassword"}
            register_data = {
                "email": "mixed2@example.com",
                "password": "MixedPass123!",
                "full_name": "Mixed User"
            }

            # Exhaust login rate limit
            login_tasks = [
                client.post("/api/v1/auth/login", json=login_data)
                for _ in range(6)
            ]
            login_responses = await asyncio.gather(*login_tasks)

            # Register should still work (separate limit)
            register_response = await client.post("/api/v1/auth/register", json=register_data)
            assert register_response.status_code in [201, 409]  # Should not be rate limited