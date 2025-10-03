"""
Integration tests for onboarding API endpoints

Tests the complete request/response flow for all onboarding endpoints including
authentication, validation, and error handling.

@module test_onboarding
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


@pytest.fixture
def mock_auth_user():
    """
    Mock authenticated user for dependency injection

    @returns Mock user object with id
    """
    class MockUser:
        id = 1
        email = "test@example.com"

    return MockUser()


@pytest.fixture
def mock_onboarding_service():
    """
    Mock OnboardingService for testing endpoint logic

    @returns AsyncMock OnboardingService
    """
    return AsyncMock()


class TestOnboardingEndpoints:
    """Integration tests for /api/v1/onboarding endpoints"""

    def test_start_onboarding_success(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /start endpoint with successful onboarding start

        Verifies that authenticated user can start onboarding
        """
        # Setup mock
        mock_onboarding_service.start_onboarding.return_value = {
            "user_id": 1,
            "current_step": 0,
            "current_step_name": "welcome",
            "total_steps": 6,
            "is_completed": False,
            "progress_percentage": 0.0,
            "started_at": "2025-10-03T12:00:00",
            "completed_at": None
        }

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/start")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 1
            assert data["current_step"] == 0
            assert data["current_step_name"] == "welcome"
            assert data["total_steps"] == 6
            assert data["is_completed"] is False
            assert data["progress_percentage"] == 0.0

    def test_start_onboarding_user_not_found(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /start endpoint with non-existent user

        Verifies that 404 is returned when user not found
        """
        # Setup mock to raise ValueError
        mock_onboarding_service.start_onboarding.side_effect = ValueError("User with id 999 not found")

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/start")

            # Assert
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_onboarding_status_success(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test GET /status endpoint with successful status retrieval

        Verifies that authenticated user can retrieve onboarding status
        """
        # Setup mock
        mock_onboarding_service.get_onboarding_status.return_value = {
            "user_id": 1,
            "current_step": 2,
            "current_step_name": "feature_tour_profiles",
            "total_steps": 6,
            "is_completed": False,
            "progress_percentage": 33.33,
            "started_at": "2025-10-03T12:00:00",
            "completed_at": None
        }

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.get("/api/v1/onboarding/status")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == 1
            assert data["current_step"] == 2
            assert data["current_step_name"] == "feature_tour_profiles"
            assert data["is_completed"] is False

    def test_progress_onboarding_success(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /progress endpoint with valid step progression

        Verifies that user can progress to valid step
        """
        # Setup mock
        mock_onboarding_service.progress_step.return_value = {
            "user_id": 1,
            "current_step": 3,
            "current_step_name": "feature_tour_comparisons",
            "total_steps": 6,
            "is_completed": False,
            "progress_percentage": 50.0,
            "started_at": "2025-10-03T12:00:00",
            "completed_at": None
        }

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post(
                "/api/v1/onboarding/progress",
                json={"step": 3}
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["current_step"] == 3
            assert data["progress_percentage"] == 50.0

    def test_progress_onboarding_invalid_step(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /progress endpoint with invalid step number

        Verifies that 400 is returned for out-of-range step
        """
        # Setup mock to raise ValueError
        mock_onboarding_service.progress_step.side_effect = ValueError("Invalid step 10")

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post(
                "/api/v1/onboarding/progress",
                json={"step": 10}
            )

            # Assert
            assert response.status_code == 400
            assert "Invalid step" in response.json()["detail"]

    def test_progress_onboarding_missing_step(self, client: TestClient, mock_auth_user):
        """
        Test POST /progress endpoint without step parameter

        Verifies that 422 is returned for missing required field
        """
        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user):

            response = client.post(
                "/api/v1/onboarding/progress",
                json={}
            )

            # Assert
            assert response.status_code == 422  # Validation error

    def test_complete_onboarding_success(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /complete endpoint with successful completion

        Verifies that user can complete onboarding
        """
        # Setup mock
        mock_onboarding_service.complete_onboarding.return_value = {
            "user_id": 1,
            "is_completed": True,
            "completed_at": "2025-10-03T13:00:00",
            "message": "Onboarding completed successfully"
        }

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/complete")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["is_completed"] is True
            assert data["message"] == "Onboarding completed successfully"
            assert "completed_at" in data

    def test_skip_onboarding_success(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /skip endpoint with successful skip

        Verifies that user can skip onboarding
        """
        # Setup mock
        mock_onboarding_service.skip_onboarding.return_value = {
            "user_id": 1,
            "is_completed": True,
            "completed_at": "2025-10-03T13:00:00",
            "message": "Onboarding skipped successfully"
        }

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/skip")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["is_completed"] is True
            assert "completed_at" in data

    def test_reset_onboarding_success(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /reset endpoint with successful reset

        Verifies that user can reset onboarding progress
        """
        # Setup mock
        mock_onboarding_service.reset_onboarding.return_value = {
            "user_id": 1,
            "current_step": 0,
            "is_completed": False,
            "message": "Onboarding reset successfully"
        }

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/reset")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["is_completed"] is False
            assert data["current_step"] == 0
            assert data["message"] == "Onboarding reset successfully"

    def test_reset_onboarding_user_not_found(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test POST /reset endpoint with non-existent user

        Verifies that 404 is returned when user not found
        """
        # Setup mock to raise ValueError
        mock_onboarding_service.reset_onboarding.side_effect = ValueError("User with id 999 not found")

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/reset")

            # Assert
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_onboarding_unauthorized_access(self, client: TestClient):
        """
        Test endpoints without authentication

        Verifies that 401/403 is returned when not authenticated
        """
        # Test without mocking authentication (should fail)
        endpoints = [
            ("/api/v1/onboarding/start", "POST"),
            ("/api/v1/onboarding/status", "GET"),
            ("/api/v1/onboarding/complete", "POST"),
            ("/api/v1/onboarding/skip", "POST"),
            ("/api/v1/onboarding/reset", "POST")
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)

            # Should fail authentication (401 or 403)
            assert response.status_code in [401, 403], f"{endpoint} should require authentication"

    def test_server_error_handling(self, client: TestClient, mock_auth_user, mock_onboarding_service):
        """
        Test 500 error handling for unexpected exceptions

        Verifies that server errors are handled gracefully
        """
        # Setup mock to raise unexpected exception
        mock_onboarding_service.start_onboarding.side_effect = Exception("Database connection failed")

        with patch("app.api.api_v1.endpoints.onboarding.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.onboarding.OnboardingService", return_value=mock_onboarding_service):

            response = client.post("/api/v1/onboarding/start")

            # Assert
            assert response.status_code == 500
            assert "Failed to start onboarding" in response.json()["detail"]
