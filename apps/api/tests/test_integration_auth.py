import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestAuthIntegrationFlows:
    """Test complete authentication flows"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_complete_user_registration_flow(self):
        """Test complete user registration and login flow"""
        # Step 1: Register new user
        user_data = {
            "email": "integration@example.com",
            "password": "IntegrationPass123!",
            "full_name": "Integration Test User"
        }

        register_response = self.client.post("/api/v1/auth/register", json=user_data)

        if register_response.status_code == 201:
            # Registration successful
            register_result = register_response.json()
            assert "user_id" in register_result
            assert register_result["message"] == "User registered successfully"

            # Step 2: Login with registered credentials
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }

            login_response = self.client.post("/api/v1/auth/login", json=login_data)
            assert login_response.status_code == 200

            login_result = login_response.json()
            assert "access_token" in login_result
            assert login_result["token_type"] == "bearer"
            assert "expires_in" in login_result

            # Step 3: Verify token is valid JWT format
            token = login_result["access_token"]
            assert len(token.split('.')) == 3  # JWT has 3 parts

        elif register_response.status_code == 409:
            # User already exists, try login
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }

            login_response = self.client.post("/api/v1/auth/login", json=login_data)
            # May succeed or fail depending on if password matches existing user
            assert login_response.status_code in [200, 401]

    def test_authentication_error_scenarios(self):
        """Test various authentication error scenarios"""
        # Scenario 1: Login with non-existent user
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "somepassword"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

        # Scenario 2: Register user with weak password
        weak_user = {
            "email": "weak@example.com",
            "password": "weak",
            "full_name": "Weak User"
        }
        response = self.client.post("/api/v1/auth/register", json=weak_user)
        assert response.status_code == 400

        # Scenario 3: Register user with invalid email
        invalid_email_user = {
            "email": "invalid-email",
            "password": "ValidPass123!",
            "full_name": "Invalid Email User"
        }
        response = self.client.post("/api/v1/auth/register", json=invalid_email_user)
        assert response.status_code == 422

    def test_logout_functionality(self):
        """Test logout endpoint"""
        response = self.client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

    def test_security_headers_in_auth_responses(self):
        """Test that auth responses include security headers"""
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "testpass"}
        )

        # Check security headers are present
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert "strict-transport-security" in response.headers

    def test_concurrent_registration_attempts(self):
        """Test handling of concurrent registration attempts"""
        import threading
        import time

        user_data = {
            "email": "concurrent@example.com",
            "password": "ConcurrentPass123!",
            "full_name": "Concurrent User"
        }

        results = []

        def register_user():
            try:
                response = self.client.post("/api/v1/auth/register", json=user_data)
                results.append(response.status_code)
            except Exception as e:
                results.append(500)

        # Start multiple threads trying to register same user
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=register_user)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have one success and others conflict/error
        success_count = sum(1 for status in results if status == 201)
        conflict_count = sum(1 for status in results if status == 409)

        # At most one should succeed, others should conflict
        assert success_count <= 1
        assert success_count + conflict_count == len(results)


class TestPerformanceUnderLoad:
    """Test authentication performance under load"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    @pytest.mark.asyncio
    async def test_auth_performance_multiple_users(self):
        """Test authentication performance with multiple different users"""
        import asyncio
        from httpx import AsyncClient

        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create multiple users
            users = [
                {
                    "email": f"perf{i}@example.com",
                    "password": f"PerfPass123!{i}",
                    "full_name": f"Perf User {i}"
                }
                for i in range(5)
            ]

            # Register users
            register_tasks = [
                client.post("/api/v1/auth/register", json=user)
                for user in users
            ]

            register_responses = await asyncio.gather(*register_tasks, return_exceptions=True)

            # Login with registered users
            login_tasks = [
                client.post("/api/v1/auth/login", json={
                    "email": user["email"],
                    "password": user["password"]
                })
                for user in users
            ]

            login_responses = await asyncio.gather(*login_tasks, return_exceptions=True)

            # At least some should succeed
            successful_logins = sum(
                1 for response in login_responses
                if hasattr(response, 'status_code') and response.status_code == 200
            )

            # Should have some successful authentications
            assert successful_logins > 0

    def test_rate_limit_performance_impact(self):
        """Test that rate limiting doesn't severely impact normal operation"""
        import time

        # Make several requests within rate limit
        start_time = time.time()

        responses = []
        for i in range(3):  # Well within rate limits
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": f"perf{i}@example.com", "password": "password"}
            )
            responses.append(response)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete reasonably quickly (under 5 seconds for 3 requests)
        assert duration < 5.0

        # All should be processed (not rate limited)
        for response in responses:
            assert response.status_code != 429


class TestSecurityCompliance:
    """Test security compliance requirements"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_https_security_headers(self):
        """Test HTTPS-related security headers"""
        response = self.client.get("/health")

        # HSTS header should be present
        hsts_header = response.headers.get("strict-transport-security")
        assert hsts_header is not None
        assert "max-age" in hsts_header
        assert "includeSubDomains" in hsts_header

    def test_content_security_policy(self):
        """Test Content Security Policy header"""
        response = self.client.get("/health")

        csp_header = response.headers.get("content-security-policy")
        assert csp_header is not None
        assert "default-src 'self'" in csp_header

    def test_clickjacking_protection(self):
        """Test clickjacking protection headers"""
        response = self.client.get("/health")

        # X-Frame-Options should deny framing
        assert response.headers.get("x-frame-options") == "DENY"

    def test_mime_type_sniffing_protection(self):
        """Test MIME type sniffing protection"""
        response = self.client.get("/health")

        # X-Content-Type-Options should prevent MIME sniffing
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_xss_protection_header(self):
        """Test XSS protection header"""
        response = self.client.get("/health")

        # X-XSS-Protection should be enabled
        xss_protection = response.headers.get("x-xss-protection")
        assert xss_protection == "1; mode=block"

    def test_referrer_policy(self):
        """Test referrer policy header"""
        response = self.client.get("/health")

        # Should have strict referrer policy
        referrer_policy = response.headers.get("referrer-policy")
        assert referrer_policy == "strict-origin-when-cross-origin"

    def test_no_sensitive_info_in_error_responses(self):
        """Test that error responses don't leak sensitive information"""
        # Test various error scenarios
        error_scenarios = [
            # Invalid JSON
            ("/api/v1/auth/login", "invalid json", "application/json"),
            # Missing fields
            ("/api/v1/auth/login", '{"email": "test@example.com"}', "application/json"),
        ]

        for endpoint, data, content_type in error_scenarios:
            response = self.client.post(
                endpoint,
                data=data,
                headers={"Content-Type": content_type}
            )

            response_text = response.text.lower()

            # Should not contain sensitive system information
            forbidden_terms = [
                "database",
                "sql",
                "redis",
                "internal server error",
                "traceback",
                "stack trace",
                "secret",
                "password",
                "token"
            ]

            for term in forbidden_terms:
                assert term not in response_text, f"Response contains sensitive term: {term}"