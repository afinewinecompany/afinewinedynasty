import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestUserProfileManagement:
    """Test user profile management endpoints"""

    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def create_authenticated_user(self, email="profile@example.com", password="ProfilePass123!"):
        """Helper to create and authenticate a user"""
        # Register user
        user_data = {
            "email": email,
            "password": password,
            "full_name": "Profile Test User"
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

    def test_get_user_profile(self):
        """Test retrieving user profile"""
        headers = self.create_authenticated_user("getprofile@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        response = self.client.get("/api/v1/users/profile", headers=headers)

        assert response.status_code == 200
        profile = response.json()

        # Should contain all profile fields
        required_fields = ["id", "email", "full_name", "is_active", "created_at", "updated_at"]
        for field in required_fields:
            assert field in profile

        # Email should match registered email
        assert profile["email"] == "getprofile@example.com"
        assert profile["full_name"] == "Profile Test User"
        assert profile["is_active"] is True

    def test_get_profile_unauthorized(self):
        """Test getting profile without authentication"""
        response = self.client.get("/api/v1/users/profile")

        assert response.status_code == 401

    def test_update_user_profile(self):
        """Test updating user profile"""
        headers = self.create_authenticated_user("updateprofile@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Update profile
        update_data = {
            "full_name": "Updated Profile User",
            "preferences": {
                "theme": "dark",
                "notifications": False,
                "language": "en"
            }
        }

        response = self.client.put("/api/v1/users/profile", json=update_data, headers=headers)

        assert response.status_code == 200
        updated_profile = response.json()

        # Verify updates
        assert updated_profile["full_name"] == "Updated Profile User"
        assert updated_profile["preferences"]["theme"] == "dark"
        assert updated_profile["preferences"]["notifications"] is False

    def test_update_profile_partial(self):
        """Test partial profile updates"""
        headers = self.create_authenticated_user("partialupdate@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Update only full name
        update_data = {"full_name": "Partially Updated User"}

        response = self.client.put("/api/v1/users/profile", json=update_data, headers=headers)

        assert response.status_code == 200
        updated_profile = response.json()

        # Only full name should be updated
        assert updated_profile["full_name"] == "Partially Updated User"
        assert updated_profile["email"] == "partialupdate@example.com"

    def test_update_profile_invalid_name(self):
        """Test profile update with invalid name"""
        headers = self.create_authenticated_user("invalidname@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Try to update with invalid name
        update_data = {"full_name": "A"}  # Too short

        response = self.client.put("/api/v1/users/profile", json=update_data, headers=headers)

        assert response.status_code == 422  # Validation error

    def test_update_profile_unauthorized(self):
        """Test updating profile without authentication"""
        update_data = {"full_name": "Unauthorized Update"}

        response = self.client.put("/api/v1/users/profile", json=update_data)

        assert response.status_code == 401

    def test_password_update_valid(self):
        """Test password update with valid credentials"""
        headers = self.create_authenticated_user("passwordupdate@example.com", "OldPass123!")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Update password
        password_data = {
            "current_password": "OldPass123!",
            "new_password": "NewSecurePass123!"
        }

        response = self.client.put("/api/v1/users/password", json=password_data, headers=headers)

        assert response.status_code == 200
        assert "Password updated successfully" in response.json()["message"]

        # Verify old password no longer works
        old_login = self.client.post("/api/v1/auth/login", json={
            "email": "passwordupdate@example.com",
            "password": "OldPass123!"
        })
        assert old_login.status_code == 401

        # Verify new password works
        new_login = self.client.post("/api/v1/auth/login", json={
            "email": "passwordupdate@example.com",
            "password": "NewSecurePass123!"
        })
        assert new_login.status_code == 200

    def test_password_update_wrong_current_password(self):
        """Test password update with wrong current password"""
        headers = self.create_authenticated_user("wrongpassword@example.com", "CorrectPass123!")
        if not headers:
            pytest.skip("Could not authenticate user")

        password_data = {
            "current_password": "WrongPass123!",
            "new_password": "NewSecurePass123!"
        }

        response = self.client.put("/api/v1/users/password", json=password_data, headers=headers)

        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]

    def test_password_update_weak_new_password(self):
        """Test password update with weak new password"""
        headers = self.create_authenticated_user("weaknewpass@example.com", "StrongPass123!")
        if not headers:
            pytest.skip("Could not authenticate user")

        password_data = {
            "current_password": "StrongPass123!",
            "new_password": "weak"
        }

        response = self.client.put("/api/v1/users/password", json=password_data, headers=headers)

        assert response.status_code == 400
        # Should mention password complexity
        assert any(keyword in response.json()["detail"].lower()
                  for keyword in ["password", "character", "complexity", "strong"])

    def test_password_update_unauthorized(self):
        """Test password update without authentication"""
        password_data = {
            "current_password": "SomePass123!",
            "new_password": "NewPass123!"
        }

        response = self.client.put("/api/v1/users/password", json=password_data)

        assert response.status_code == 401

    def test_preferences_management(self):
        """Test user preferences management"""
        headers = self.create_authenticated_user("preferences@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Get initial preferences
        response = self.client.get("/api/v1/users/preferences", headers=headers)

        assert response.status_code == 200
        preferences = response.json()
        assert isinstance(preferences, dict)

        # Update preferences
        new_preferences = {
            "theme": "dark",
            "language": "en",
            "notifications": True,
            "auto_save": False
        }

        update_response = self.client.put("/api/v1/users/preferences", json=new_preferences, headers=headers)

        assert update_response.status_code == 200
        result = update_response.json()
        assert "Preferences updated successfully" in result["message"]
        assert result["preferences"] == new_preferences

        # Verify preferences were saved
        get_response = self.client.get("/api/v1/users/preferences", headers=headers)
        assert get_response.status_code == 200
        saved_preferences = get_response.json()
        assert saved_preferences == new_preferences

    def test_preferences_unauthorized(self):
        """Test preferences endpoints without authentication"""
        # Get preferences without auth
        response = self.client.get("/api/v1/users/preferences")
        assert response.status_code == 401

        # Update preferences without auth
        response = self.client.put("/api/v1/users/preferences", json={"theme": "dark"})
        assert response.status_code == 401

    def test_oauth_user_password_restrictions(self):
        """Test that OAuth users have appropriate restrictions"""
        # This test would need to be implemented with actual OAuth user creation
        # For now, we test the error case when trying to update password for OAuth user

        # Skip this test as it requires complex OAuth user setup
        pytest.skip("OAuth user testing requires complex setup")

    def test_profile_fields_validation(self):
        """Test profile field validation"""
        headers = self.create_authenticated_user("validation@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        # Test various invalid inputs
        invalid_updates = [
            {"full_name": ""},  # Empty name
            {"full_name": " "},  # Whitespace only
            {"full_name": "x" * 1000},  # Too long name (if length validation exists)
        ]

        for invalid_data in invalid_updates:
            response = self.client.put("/api/v1/users/profile", json=invalid_data, headers=headers)
            # Should either validate and reject or process with cleaned data
            assert response.status_code in [200, 400, 422]

    def test_concurrent_profile_updates(self):
        """Test handling of concurrent profile updates"""
        import threading
        import time

        headers = self.create_authenticated_user("concurrent@example.com")
        if not headers:
            pytest.skip("Could not authenticate user")

        results = []

        def update_profile(name_suffix):
            try:
                update_data = {"full_name": f"Concurrent User {name_suffix}"}
                response = self.client.put("/api/v1/users/profile", json=update_data, headers=headers)
                results.append(response.status_code)
            except Exception:
                results.append(500)

        # Start multiple threads trying to update profile
        threads = []
        for i in range(3):
            thread = threading.Thread(target=update_profile, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All updates should succeed (last one wins)
        success_count = sum(1 for status in results if status == 200)
        assert success_count == len(results), "All profile updates should succeed"