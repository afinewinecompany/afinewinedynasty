import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestInputValidation:
    """Test input validation and sanitization"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_email_format_validation(self):
        """Test email format validation"""
        # Valid email
        valid_data = {
            "email": "valid@example.com",
            "password": "ValidPass123!",
            "full_name": "Valid User"
        }
        response = self.client.post("/api/v1/auth/register", json=valid_data)
        assert response.status_code in [201, 409]  # Success or already exists

        # Invalid email formats
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user@@example.com",
            "user@example",
            "",
            " ",
            "user with spaces@example.com"
        ]

        for invalid_email in invalid_emails:
            invalid_data = {
                "email": invalid_email,
                "password": "ValidPass123!",
                "full_name": "Test User"
            }
            response = self.client.post("/api/v1/auth/register", json=invalid_data)
            assert response.status_code == 422  # Validation error

    def test_password_length_validation(self):
        """Test password length validation"""
        # Too short password
        short_data = {
            "email": "short@example.com",
            "password": "1234567",  # 7 chars, too short
            "full_name": "Short User"
        }
        response = self.client.post("/api/v1/auth/register", json=short_data)
        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]

        # Too long password (129 chars)
        long_password = "a" * 129
        long_data = {
            "email": "long@example.com",
            "password": long_password,
            "full_name": "Long User"
        }
        response = self.client.post("/api/v1/auth/register", json=long_data)
        assert response.status_code == 400
        assert "128 characters" in response.json()["detail"]

    def test_name_validation_and_sanitization(self):
        """Test name input validation and sanitization"""
        # Valid names
        valid_names = [
            "John Doe",
            "Mary-Jane Watson",
            "Patrick O'Connor",
            "Jean-Claude Van Damme"
        ]

        for valid_name in valid_names:
            valid_data = {
                "email": f"user{hash(valid_name)}@example.com",
                "password": "ValidPass123!",
                "full_name": valid_name
            }
            response = self.client.post("/api/v1/auth/register", json=valid_data)
            assert response.status_code in [201, 409]

        # Invalid names with special characters
        invalid_names = [
            "John<script>alert('xss')</script>",
            "User@#$%",
            "123456",
            "",
            " ",
            "User\x00Name",  # Null byte
            "A" * 101  # Too long (over 100 chars)
        ]

        for invalid_name in invalid_names:
            invalid_data = {
                "email": f"invalid{hash(invalid_name)}@example.com",
                "password": "ValidPass123!",
                "full_name": invalid_name
            }
            response = self.client.post("/api/v1/auth/register", json=invalid_data)
            assert response.status_code == 400

    def test_injection_attack_prevention(self):
        """Test prevention of injection attacks"""
        # SQL injection attempts
        injection_attempts = [
            "'; DROP TABLE users; --",
            "admin'/*",
            "' OR '1'='1",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ]

        for injection in injection_attempts:
            # Test in email field
            response = self.client.post(
                "/api/v1/auth/login",
                json={"email": injection, "password": "password123"}
            )
            # Should get validation error, not 500 (indicating injection prevented)
            assert response.status_code in [400, 401, 422]

    def test_xss_prevention(self):
        """Test prevention of XSS attacks"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src='x' onerror='alert(\"xss\")'>",
            "<iframe src='javascript:alert(\"xss\")'></iframe>",
            "vbscript:msgbox('xss')"
        ]

        for payload in xss_payloads:
            # Test XSS in email field
            xss_data = {
                "email": f"{payload}@example.com",
                "password": "ValidPass123!",
                "full_name": "XSS Test"
            }
            response = self.client.post("/api/v1/auth/register", json=xss_data)
            assert response.status_code == 400  # Should be rejected

    def test_request_size_limits(self):
        """Test request size limitation"""
        # Create a large payload (over 2MB)
        large_name = "A" * (3 * 1024 * 1024)  # 3MB name
        large_data = {
            "email": "large@example.com",
            "password": "ValidPass123!",
            "full_name": large_name
        }

        response = self.client.post("/api/v1/auth/register", json=large_data)
        assert response.status_code == 413  # Request too large

    def test_null_byte_rejection(self):
        """Test rejection of null bytes in input"""
        # Test null bytes in different fields
        null_tests = [
            {"field": "email", "value": "test\x00@example.com"},
            {"field": "password", "value": "password\x00123"},
            {"field": "full_name", "value": "Test\x00User"}
        ]

        for test in null_tests:
            data = {
                "email": "nulltest@example.com",
                "password": "ValidPass123!",
                "full_name": "Null Test"
            }
            data[test["field"]] = test["value"]

            response = self.client.post("/api/v1/auth/register", json=data)
            assert response.status_code == 400

    def test_unicode_handling(self):
        """Test proper Unicode handling"""
        # Valid Unicode characters should be accepted
        unicode_data = {
            "email": "unicode@example.com",
            "password": "ValidPass123!",
            "full_name": "José María Azñar"  # Spanish characters
        }

        response = self.client.post("/api/v1/auth/register", json=unicode_data)
        assert response.status_code in [201, 409]

        # Test with other valid Unicode names
        unicode_names = [
            "François Müller",  # French/German
            "田中太郎",  # Japanese
            "김철수",  # Korean
            "Владимир Путин"  # Russian (Cyrillic)
        ]

        # Note: Some of these might fail based on name validation rules
        # This test checks that Unicode is handled gracefully
        for name in unicode_names:
            data = {
                "email": f"unicode{hash(name)}@example.com",
                "password": "ValidPass123!",
                "full_name": name
            }
            response = self.client.post("/api/v1/auth/register", json=data)
            # Should either succeed or fail gracefully (not 500 error)
            assert response.status_code != 500

    def test_whitespace_handling(self):
        """Test proper whitespace handling"""
        # Leading/trailing whitespace should be trimmed
        whitespace_data = {
            "email": "  whitespace@example.com  ",
            "password": "ValidPass123!",
            "full_name": "  Whitespace User  "
        }

        # The email validation should handle this
        response = self.client.post("/api/v1/auth/register", json=whitespace_data)
        # Should succeed or fail gracefully
        assert response.status_code in [201, 400, 409, 422]


class TestAPIValidation:
    """Test API-level validation"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        # Missing email
        response = self.client.post(
            "/api/v1/auth/register",
            json={"password": "ValidPass123!", "full_name": "Test User"}
        )
        assert response.status_code == 422

        # Missing password
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "full_name": "Test User"}
        )
        assert response.status_code == 422

        # Missing full_name
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPass123!"}
        )
        assert response.status_code == 422

    def test_invalid_json_format(self):
        """Test handling of invalid JSON"""
        # Invalid JSON should be rejected
        response = self.client.post(
            "/api/v1/auth/register",
            data="invalid json content",  # Not JSON
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_wrong_content_type(self):
        """Test handling of wrong content types"""
        # Try to send form data to JSON endpoint
        response = self.client.post(
            "/api/v1/auth/register",
            data={"email": "test@example.com", "password": "ValidPass123!", "full_name": "Test User"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # Should require JSON content type
        assert response.status_code == 422

    def test_extra_fields_handling(self):
        """Test handling of extra unexpected fields"""
        # Extra fields should be ignored or cause validation error
        data_with_extra = {
            "email": "extra@example.com",
            "password": "ValidPass123!",
            "full_name": "Extra User",
            "unexpected_field": "should_be_ignored",
            "admin": True  # Potentially dangerous extra field
        }

        response = self.client.post("/api/v1/auth/register", json=data_with_extra)
        # Should either ignore extra fields or reject the request
        assert response.status_code in [201, 400, 409, 422]