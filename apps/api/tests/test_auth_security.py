import pytest
import jwt
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import verify_token, create_access_token, is_password_complex


class TestAuthSecurity:
    """Test authentication security functionality"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_login_invalid_credentials_generic_error(self):
        """Test that login with invalid credentials returns generic error"""
        # Test with non-existent user
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_prevents_user_enumeration(self):
        """Test that login errors don't reveal if user exists"""
        # Register a user first
        register_data = {
            "email": "enumtest@example.com",
            "password": "ValidPass123!",
            "full_name": "Enum Test"
        }
        self.client.post("/api/v1/auth/register", json=register_data)

        # Test with existing user, wrong password
        response1 = self.client.post(
            "/api/v1/auth/login",
            json={"email": "enumtest@example.com", "password": "wrongpassword"}
        )

        # Test with non-existent user
        response2 = self.client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrongpassword"}
        )

        # Both should return the same generic error
        assert response1.status_code == response2.status_code == 401
        assert response1.json()["detail"] == response2.json()["detail"]

    def test_jwt_token_generation_and_validation(self):
        """Test JWT token creation and validation"""
        # Test token creation
        test_email = "jwt@example.com"
        token = create_access_token(subject=test_email)

        assert isinstance(token, str)
        assert len(token) > 0

        # Test token validation
        decoded_email = verify_token(token)
        assert decoded_email == test_email

    def test_jwt_token_expiration(self):
        """Test that JWT tokens have proper expiration"""
        token = create_access_token(subject="expire@example.com")

        # Decode token to check expiration
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload
        assert payload["exp"] > jwt.datetime.utcnow().timestamp()

    def test_invalid_jwt_token_rejected(self):
        """Test that invalid JWT tokens are rejected"""
        # Test with completely invalid token
        assert verify_token("invalid.token.here") is None

        # Test with tampered token
        valid_token = create_access_token(subject="valid@example.com")
        tampered_token = valid_token[:-10] + "tampered123"
        assert verify_token(tampered_token) is None

    def test_password_complexity_requirements(self):
        """Test password complexity validation"""
        # Valid password
        valid, message = is_password_complex("ValidPass123!")
        assert valid is True

        # Too short
        valid, message = is_password_complex("Short1!")
        assert valid is False
        assert "8 characters" in message

        # No uppercase
        valid, message = is_password_complex("lowercase123!")
        assert valid is False
        assert "uppercase" in message

        # No lowercase
        valid, message = is_password_complex("UPPERCASE123!")
        assert valid is False
        assert "lowercase" in message

        # No digits
        valid, message = is_password_complex("NoDigits!")
        assert valid is False
        assert "digit" in message

        # No special characters
        valid, message = is_password_complex("NoSpecial123")
        assert valid is False
        assert "special character" in message

    def test_register_password_complexity_enforced(self):
        """Test that registration enforces password complexity"""
        # Try to register with weak password
        weak_data = {
            "email": "weak@example.com",
            "password": "weak",
            "full_name": "Weak User"
        }

        response = self.client.post("/api/v1/auth/register", json=weak_data)
        assert response.status_code == 400

        # Register with strong password should work
        strong_data = {
            "email": "strong@example.com",
            "password": "StrongPass123!",
            "full_name": "Strong User"
        }

        response = self.client.post("/api/v1/auth/register", json=strong_data)
        assert response.status_code in [201, 409]  # Success or already exists

    def test_duplicate_user_registration_prevented(self):
        """Test that duplicate user registration is prevented"""
        user_data = {
            "email": "duplicate@example.com",
            "password": "ValidPass123!",
            "full_name": "Duplicate User"
        }

        # First registration should succeed
        response1 = self.client.post("/api/v1/auth/register", json=user_data)
        assert response1.status_code == 201

        # Second registration should fail
        response2 = self.client.post("/api/v1/auth/register", json=user_data)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    def test_password_hashing_security(self):
        """Test that passwords are properly hashed"""
        from app.core.security import get_password_hash, verify_password

        password = "TestPassword123!"
        hashed = get_password_hash(password)

        # Hash should be different from original
        assert hashed != password

        # Should be able to verify
        assert verify_password(password, hashed) is True

        # Wrong password should fail
        assert verify_password("WrongPassword123!", hashed) is False

    def test_session_management(self):
        """Test basic session/token management"""
        # Register and login user
        register_data = {
            "email": "session@example.com",
            "password": "SessionPass123!",
            "full_name": "Session User"
        }

        register_response = self.client.post("/api/v1/auth/register", json=register_data)
        if register_response.status_code == 201:
            # Login to get token
            login_response = self.client.post(
                "/api/v1/auth/login",
                json={"email": "session@example.com", "password": "SessionPass123!"}
            )

            assert login_response.status_code == 200
            token_data = login_response.json()
            assert "access_token" in token_data
            assert token_data["token_type"] == "bearer"
            assert "expires_in" in token_data

    def test_error_handling_no_information_disclosure(self):
        """Test that error handling doesn't disclose sensitive information"""
        # Test various error scenarios
        test_cases = [
            {"email": "invalid-email", "password": "pass"},  # Invalid email format
            {"email": "", "password": "pass"},  # Empty email
            {"email": "test@example.com", "password": ""},  # Empty password
        ]

        for case in test_cases:
            response = self.client.post("/api/v1/auth/login", json=case)
            # Should not reveal internal system details
            assert "database" not in response.json().get("detail", "").lower()
            assert "sql" not in response.json().get("detail", "").lower()
            assert "internal" not in response.json().get("detail", "").lower()


class TestAuthSecurityHeaders:
    """Test security headers and CORS configuration"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_security_headers_present(self):
        """Test that security headers are present in responses"""
        response = self.client.get("/health")

        # Check for security headers
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-xss-protection") == "1; mode=block"
        assert "strict-transport-security" in response.headers
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("content-security-policy") == "default-src 'self'"

    def test_cors_configuration(self):
        """Test CORS configuration security"""
        # Test preflight request
        response = self.client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        # Should have CORS headers but be restrictive
        cors_headers = response.headers
        if "access-control-allow-origin" in cors_headers:
            # Should not be wildcard in production
            assert cors_headers["access-control-allow-origin"] != "*"