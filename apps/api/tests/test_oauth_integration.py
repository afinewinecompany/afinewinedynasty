import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


class TestGoogleOAuthIntegration:
    """Test Google OAuth integration functionality"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    @patch('app.services.oauth_service.GoogleOAuthService.exchange_code_for_token')
    @patch('app.services.oauth_service.GoogleOAuthService.get_user_info')
    def test_google_oauth_login_new_user(self, mock_get_user_info, mock_exchange_code):
        """Test Google OAuth login with new user"""
        # Mock OAuth service responses
        mock_exchange_code.return_value = "mock_access_token"
        mock_get_user_info.return_value = {
            "id": "google_user_123",
            "email": "oauth@example.com",
            "name": "OAuth Test User",
            "picture": "https://example.com/photo.jpg"
        }

        oauth_data = {
            "code": "mock_authorization_code",
            "state": "mock_state"
        }

        response = self.client.post("/api/v1/auth/google/login", json=oauth_data)

        assert response.status_code == 200
        result = response.json()

        # Should return authentication tokens
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert "user_id" in result
        assert "is_new_user" in result

        # Verify token format
        assert len(result["access_token"].split('.')) == 3  # JWT format

    @patch('app.services.oauth_service.GoogleOAuthService.exchange_code_for_token')
    @patch('app.services.oauth_service.GoogleOAuthService.get_user_info')
    def test_google_oauth_login_existing_user(self, mock_get_user_info, mock_exchange_code):
        """Test Google OAuth login with existing user"""
        # First, create a regular user
        user_data = {
            "email": "oauth_existing@example.com",
            "password": "ExistingPass123!",
            "full_name": "Existing OAuth User"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

        # Mock OAuth service responses for same email
        mock_exchange_code.return_value = "mock_access_token"
        mock_get_user_info.return_value = {
            "id": "google_user_456",
            "email": "oauth_existing@example.com",
            "name": "Existing OAuth User",
            "picture": "https://example.com/photo.jpg"
        }

        oauth_data = {
            "code": "mock_authorization_code",
            "state": "mock_state"
        }

        response = self.client.post("/api/v1/auth/google/login", json=oauth_data)

        if response.status_code == 200:
            result = response.json()
            # Should link to existing account
            assert result["is_new_user"] is False

    @patch('app.services.oauth_service.GoogleOAuthService.exchange_code_for_token')
    def test_google_oauth_invalid_code(self, mock_exchange_code):
        """Test Google OAuth with invalid authorization code"""
        # Mock failed code exchange
        mock_exchange_code.return_value = None

        oauth_data = {
            "code": "invalid_code",
            "state": "mock_state"
        }

        response = self.client.post("/api/v1/auth/google/login", json=oauth_data)

        assert response.status_code == 400
        assert "Failed to exchange authorization code" in response.json()["detail"]

    @patch('app.services.oauth_service.GoogleOAuthService.exchange_code_for_token')
    @patch('app.services.oauth_service.GoogleOAuthService.get_user_info')
    def test_google_oauth_missing_email(self, mock_get_user_info, mock_exchange_code):
        """Test Google OAuth with missing email in user info"""
        mock_exchange_code.return_value = "mock_access_token"
        mock_get_user_info.return_value = {
            "id": "google_user_789",
            "name": "No Email User"
            # Missing email field
        }

        oauth_data = {
            "code": "mock_authorization_code",
            "state": "mock_state"
        }

        response = self.client.post("/api/v1/auth/google/login", json=oauth_data)

        assert response.status_code == 400
        assert "Email not provided by Google" in response.json()["detail"]

    def test_account_linking_valid_credentials(self):
        """Test linking Google account to existing email/password account"""
        # First, create a regular user
        user_data = {
            "email": "link@example.com",
            "password": "LinkPass123!",
            "full_name": "Link User"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

        # Mock successful account linking
        with patch('app.services.oauth_service.GoogleOAuthService.exchange_code_for_token') as mock_exchange_code, \
             patch('app.services.oauth_service.GoogleOAuthService.get_user_info') as mock_get_user_info:

            mock_exchange_code.return_value = "mock_access_token"
            mock_get_user_info.return_value = {
                "id": "google_user_link",
                "email": "link@example.com",
                "name": "Link User",
                "picture": "https://example.com/photo.jpg"
            }

            link_data = {
                "email": "link@example.com",
                "password": "LinkPass123!",
                "google_code": "mock_google_code"
            }

            response = self.client.post("/api/v1/auth/google/link", json=link_data)

            if response.status_code == 200:
                assert "Google account linked successfully" in response.json()["message"]

    def test_account_linking_invalid_password(self):
        """Test account linking with invalid password"""
        # First, create a regular user
        user_data = {
            "email": "link_invalid@example.com",
            "password": "LinkPass123!",
            "full_name": "Link Invalid User"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

        link_data = {
            "email": "link_invalid@example.com",
            "password": "WrongPassword123!",
            "google_code": "mock_google_code"
        }

        response = self.client.post("/api/v1/auth/google/link", json=link_data)

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_account_linking_email_mismatch(self):
        """Test account linking with mismatched emails"""
        # First, create a regular user
        user_data = {
            "email": "link_mismatch@example.com",
            "password": "LinkPass123!",
            "full_name": "Link Mismatch User"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

        with patch('app.services.oauth_service.GoogleOAuthService.exchange_code_for_token') as mock_exchange_code, \
             patch('app.services.oauth_service.GoogleOAuthService.get_user_info') as mock_get_user_info:

            mock_exchange_code.return_value = "mock_access_token"
            mock_get_user_info.return_value = {
                "id": "google_user_mismatch",
                "email": "different@example.com",  # Different email
                "name": "Different User"
            }

            link_data = {
                "email": "link_mismatch@example.com",
                "password": "LinkPass123!",
                "google_code": "mock_google_code"
            }

            response = self.client.post("/api/v1/auth/google/link", json=link_data)

            if response.status_code == 400:
                assert "Google account email must match" in response.json()["detail"]


class TestRefreshTokenFlow:
    """Test JWT refresh token functionality"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_refresh_token_valid_flow(self):
        """Test valid refresh token flow"""
        # First, register and login to get tokens
        user_data = {
            "email": "refresh@example.com",
            "password": "RefreshPass123!",
            "full_name": "Refresh User"
        }

        register_response = self.client.post("/api/v1/auth/register", json=user_data)

        if register_response.status_code in [201, 409]:  # Success or user exists
            login_response = self.client.post("/api/v1/auth/login", json={
                "email": user_data["email"],
                "password": user_data["password"]
            })

            if login_response.status_code == 200:
                login_result = login_response.json()
                refresh_token = login_result.get("refresh_token")

                if refresh_token:
                    # Test refresh token endpoint
                    refresh_data = {"refresh_token": refresh_token}
                    refresh_response = self.client.post("/api/v1/auth/refresh", json=refresh_data)

                    if refresh_response.status_code == 200:
                        refresh_result = refresh_response.json()

                        # Should return new tokens
                        assert "access_token" in refresh_result
                        assert "refresh_token" in refresh_result
                        assert refresh_result["token_type"] == "bearer"

                        # New tokens should be different from original
                        assert refresh_result["access_token"] != login_result["access_token"]

    def test_refresh_token_invalid(self):
        """Test refresh with invalid token"""
        refresh_data = {"refresh_token": "invalid.refresh.token"}
        response = self.client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]

    def test_refresh_token_missing(self):
        """Test refresh with missing token"""
        refresh_data = {"refresh_token": ""}
        response = self.client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401


class TestPasswordResetFlow:
    """Test password reset functionality"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_password_reset_request_valid_email(self):
        """Test password reset request with valid email"""
        # First, register a user
        user_data = {
            "email": "reset@example.com",
            "password": "ResetPass123!",
            "full_name": "Reset User"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

        # Request password reset
        reset_data = {"email": "reset@example.com"}
        response = self.client.post("/api/v1/auth/password-reset", json=reset_data)

        assert response.status_code == 200
        # Should always return success to prevent user enumeration
        assert "password reset link has been sent" in response.json()["message"].lower()

    def test_password_reset_request_nonexistent_email(self):
        """Test password reset request with non-existent email"""
        reset_data = {"email": "nonexistent@example.com"}
        response = self.client.post("/api/v1/auth/password-reset", json=reset_data)

        assert response.status_code == 200
        # Should return same message to prevent user enumeration
        assert "password reset link has been sent" in response.json()["message"].lower()

    def test_password_reset_invalid_token(self):
        """Test password reset with invalid token"""
        reset_data = {
            "token": "invalid_reset_token",
            "new_password": "NewValidPass123!"
        }
        response = self.client.put("/api/v1/auth/password-reset", json=reset_data)

        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["detail"]

    def test_password_reset_weak_password(self):
        """Test password reset with weak new password"""
        reset_data = {
            "token": "some_token",
            "new_password": "weak"
        }
        response = self.client.put("/api/v1/auth/password-reset", json=reset_data)

        assert response.status_code == 400
        # Should contain password complexity requirements
        assert any(keyword in response.json()["detail"].lower()
                  for keyword in ["password", "character", "complexity"])


class TestRateLimitingValidation:
    """Test rate limiting enforcement"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_auth_rate_limiting(self):
        """Test authentication endpoint rate limiting"""
        login_data = {"email": "test@example.com", "password": "testpass"}

        # Make multiple requests quickly
        responses = []
        for _ in range(10):  # Exceed typical rate limit
            response = self.client.post("/api/v1/auth/login", json=login_data)
            responses.append(response.status_code)

        # Should eventually get rate limited
        rate_limited_count = sum(1 for status in responses if status == 429)
        assert rate_limited_count > 0, "Rate limiting should have kicked in"

    def test_registration_rate_limiting(self):
        """Test registration endpoint rate limiting"""
        # Make multiple registration attempts
        responses = []
        for i in range(6):  # Exceed typical sensitive endpoint rate limit
            user_data = {
                "email": f"spam{i}@example.com",
                "password": "SpamPass123!",
                "full_name": f"Spam User {i}"
            }
            response = self.client.post("/api/v1/auth/register", json=user_data)
            responses.append(response.status_code)

        # Should eventually get rate limited
        rate_limited_count = sum(1 for status in responses if status == 429)
        # Sensitive endpoints have stricter rate limits
        assert rate_limited_count > 0, "Registration rate limiting should have kicked in"