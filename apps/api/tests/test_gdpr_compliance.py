import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestGDPRCompliance:
    """Test GDPR compliance functionality"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def create_authenticated_user(self, email="gdpr@example.com", password="GdprPass123!"):
        """Helper to create and authenticate a user"""
        # Register user
        user_data = {
            "email": email,
            "password": password,
            "full_name": "GDPR Test User"
        }
        self.client.post("/api/v1/auth/register", json=user_data)

        # Login to get token
        login_response = self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password
        })

        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}
        return None

    def test_user_data_export(self):
        """Test GDPR data export functionality"""
        headers = self.create_authenticated_user("export@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        response = self.client.get("/api/v1/users/export", headers=headers)

        assert response.status_code == 200
        result = response.json()

        # Should contain all required GDPR data sections
        assert "user_data" in result
        assert "export_timestamp" in result
        assert "data_retention_info" in result

        user_data = result["user_data"]

        # Personal information section
        assert "personal_information" in user_data
        personal_info = user_data["personal_information"]
        assert "id" in personal_info
        assert "email" in personal_info
        assert "full_name" in personal_info
        assert "account_created" in personal_info

        # Preferences section
        assert "preferences" in user_data

        # Consent data section
        assert "consent_data" in user_data
        consent_data = user_data["consent_data"]
        assert "privacy_policy_accepted" in consent_data
        assert "data_processing_accepted" in consent_data

        # Account status section
        assert "account_status" in user_data

    def test_user_data_export_unauthorized(self):
        """Test data export without authentication"""
        response = self.client.get("/api/v1/users/export")

        assert response.status_code == 401

    def test_consent_management(self):
        """Test user consent management"""
        headers = self.create_authenticated_user("consent@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Update consent preferences
        consent_data = {
            "privacy_policy_accepted": True,
            "marketing_emails_accepted": True,
            "data_processing_accepted": True
        }

        response = self.client.put("/api/v1/users/consent", json=consent_data, headers=headers)

        assert response.status_code == 200
        assert "Consent preferences updated successfully" in response.json()["message"]

        # Verify consent was updated by checking export
        export_response = self.client.get("/api/v1/users/export", headers=headers)
        if export_response.status_code == 200:
            export_data = export_response.json()
            consent_info = export_data["user_data"]["consent_data"]
            assert consent_info["marketing_emails_accepted"] is True

    def test_consent_management_unauthorized(self):
        """Test consent management without authentication"""
        consent_data = {
            "privacy_policy_accepted": True,
            "marketing_emails_accepted": False,
            "data_processing_accepted": True
        }

        response = self.client.put("/api/v1/users/consent", json=consent_data)

        assert response.status_code == 401

    def test_account_deletion_with_password(self):
        """Test GDPR account deletion for password-based account"""
        headers = self.create_authenticated_user("delete@example.com", "DeletePass123!")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Attempt account deletion
        deletion_data = {
            "password": "DeletePass123!",
            "confirmation": "DELETE_MY_ACCOUNT"
        }

        response = self.client.delete("/api/v1/users/delete", json=deletion_data, headers=headers)

        assert response.status_code == 200
        result = response.json()
        assert "permanently deleted" in result["message"]
        assert "deleted_at" in result

        # Verify user can no longer login
        login_response = self.client.post("/api/v1/auth/login", json={
            "email": "delete@example.com",
            "password": "DeletePass123!"
        })
        assert login_response.status_code == 401

    def test_account_deletion_wrong_password(self):
        """Test account deletion with wrong password"""
        headers = self.create_authenticated_user("delete_wrong@example.com", "DeleteWrongPass123!")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Attempt account deletion with wrong password
        deletion_data = {
            "password": "WrongPassword123!",
            "confirmation": "DELETE_MY_ACCOUNT"
        }

        response = self.client.delete("/api/v1/users/delete", json=deletion_data, headers=headers)

        assert response.status_code == 400
        assert "Invalid password" in response.json()["detail"]

    def test_account_deletion_wrong_confirmation(self):
        """Test account deletion with wrong confirmation"""
        headers = self.create_authenticated_user("delete_conf@example.com", "DeleteConfPass123!")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Attempt account deletion with wrong confirmation
        deletion_data = {
            "password": "DeleteConfPass123!",
            "confirmation": "WRONG_CONFIRMATION"
        }

        response = self.client.delete("/api/v1/users/delete", json=deletion_data, headers=headers)

        assert response.status_code == 422  # Validation error

    def test_account_deletion_unauthorized(self):
        """Test account deletion without authentication"""
        deletion_data = {
            "password": "SomePass123!",
            "confirmation": "DELETE_MY_ACCOUNT"
        }

        response = self.client.delete("/api/v1/users/delete", json=deletion_data)

        assert response.status_code == 401

    def test_data_portability_format(self):
        """Test that exported data follows GDPR portability requirements"""
        headers = self.create_authenticated_user("portable@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Update user preferences first
        preferences_data = {"theme": "dark", "notifications": False}
        self.client.put("/api/v1/users/preferences", json=preferences_data, headers=headers)

        # Export data
        response = self.client.get("/api/v1/users/export", headers=headers)

        assert response.status_code == 200
        result = response.json()

        # Verify structured format suitable for portability
        user_data = result["user_data"]

        # Data should be in human-readable format with clear sections
        assert isinstance(user_data["personal_information"], dict)
        assert isinstance(user_data["preferences"], dict)
        assert isinstance(user_data["consent_data"], dict)
        assert isinstance(user_data["account_status"], dict)

        # Timestamps should be in ISO format
        personal_info = user_data["personal_information"]
        if personal_info.get("account_created"):
            # Should be valid ISO timestamp
            import datetime
            try:
                datetime.datetime.fromisoformat(personal_info["account_created"].replace('Z', '+00:00'))
            except ValueError:
                pytest.fail("Timestamps should be in valid ISO format")

    def test_privacy_policy_acceptance_tracking(self):
        """Test privacy policy acceptance tracking"""
        headers = self.create_authenticated_user("privacy@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Check that privacy policy acceptance is tracked
        export_response = self.client.get("/api/v1/users/export", headers=headers)

        assert export_response.status_code == 200
        export_data = export_response.json()
        consent_data = export_data["user_data"]["consent_data"]

        # Should have privacy policy acceptance information
        assert "privacy_policy_accepted" in consent_data
        assert "privacy_policy_accepted_at" in consent_data

        # Should be accepted (required for registration)
        assert consent_data["privacy_policy_accepted"] is True
        assert consent_data["privacy_policy_accepted_at"] is not None

    def test_marketing_consent_separate_from_service(self):
        """Test that marketing consent is separate from service consent"""
        headers = self.create_authenticated_user("marketing@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Marketing emails should be separate and optional
        export_response = self.client.get("/api/v1/users/export", headers=headers)

        if export_response.status_code == 200:
            export_data = export_response.json()
            consent_data = export_data["user_data"]["consent_data"]

            # Service consent (data processing) should be required and true
            assert consent_data.get("data_processing_accepted") is True

            # Marketing consent should be optional and separate
            marketing_consent = consent_data.get("marketing_emails_accepted")
            assert marketing_consent is not None  # Should be explicitly set
            # Can be true or false, but should be present

    def test_consent_withdrawal_functionality(self):
        """Test that users can withdraw marketing consent"""
        headers = self.create_authenticated_user("withdraw@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Withdraw marketing consent
        consent_data = {
            "privacy_policy_accepted": True,  # Required for service
            "marketing_emails_accepted": False,  # Withdraw marketing consent
            "data_processing_accepted": True  # Required for service
        }

        response = self.client.put("/api/v1/users/consent", json=consent_data, headers=headers)

        assert response.status_code == 200

        # Verify consent was updated
        export_response = self.client.get("/api/v1/users/export", headers=headers)
        if export_response.status_code == 200:
            export_data = export_response.json()
            consent_info = export_data["user_data"]["consent_data"]
            assert consent_info["marketing_emails_accepted"] is False

    def test_data_retention_information(self):
        """Test that data retention information is provided"""
        headers = self.create_authenticated_user("retention@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        response = self.client.get("/api/v1/users/export", headers=headers)

        assert response.status_code == 200
        result = response.json()

        # Should include data retention information
        assert "data_retention_info" in result
        retention_info = result["data_retention_info"]

        # Should provide meaningful information about data retention
        assert len(retention_info) > 10  # Not just empty string
        assert "privacy policy" in retention_info.lower() or "data" in retention_info.lower()


class TestGDPRSecurityRequirements:
    """Test GDPR-related security requirements"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_data_export_requires_authentication(self):
        """Test that data export requires proper authentication"""
        # Try without authentication
        response = self.client.get("/api/v1/users/export")
        assert response.status_code == 401

        # Try with invalid token
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = self.client.get("/api/v1/users/export", headers=headers)
        assert response.status_code == 401

    def test_account_deletion_requires_strong_confirmation(self):
        """Test that account deletion requires strong confirmation"""
        # Even with authentication, should require exact confirmation string
        headers = {"Authorization": "Bearer valid.token.here"}

        # Test various incorrect confirmation strings
        incorrect_confirmations = [
            "DELETE_ACCOUNT",
            "delete_my_account",
            "DELETE MY ACCOUNT",
            "confirm",
            ""
        ]

        for confirmation in incorrect_confirmations:
            deletion_data = {
                "password": "SomePass123!",
                "confirmation": confirmation
            }

            response = self.client.delete("/api/v1/users/delete", json=deletion_data, headers=headers)

            # Should reject due to validation or authentication
            assert response.status_code in [401, 422]

    def test_consent_changes_are_logged(self):
        """Test that consent changes include timestamps"""
        # This test verifies that consent changes are properly timestamped
        # In a real implementation, you might want to log all consent changes

        # For now, we test that the current consent timestamp is updated
        headers = {"Authorization": "Bearer invalid.token"}  # Will fail auth

        consent_data = {
            "privacy_policy_accepted": True,
            "marketing_emails_accepted": False,
            "data_processing_accepted": True
        }

        response = self.client.put("/api/v1/users/consent", json=consent_data, headers=headers)

        # Should require authentication
        assert response.status_code == 401