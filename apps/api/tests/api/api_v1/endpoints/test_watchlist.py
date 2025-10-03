"""
Integration tests for watchlist API endpoints

Tests the complete request/response flow for all watchlist endpoints including
CRUD operations, authentication, validation, and error handling.

@module test_watchlist
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
def mock_watchlist_service():
    """
    Mock WatchlistService for testing endpoint logic

    @returns AsyncMock WatchlistService
    """
    return AsyncMock()


class TestWatchlistEndpoints:
    """Integration tests for /api/v1/watchlist endpoints"""

    def test_add_to_watchlist_success(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test POST / endpoint with successful watchlist addition

        Verifies that prospect can be added to watchlist
        """
        # Setup mock
        mock_watchlist_service.add_to_watchlist.return_value = {
            "id": 1,
            "user_id": 1,
            "prospect_id": 100,
            "notes": "Great prospect",
            "added_at": "2025-10-03T12:00:00",
            "notify_on_changes": True
        }

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.post(
                "/api/v1/watchlist/",
                json={
                    "prospect_id": 100,
                    "notes": "Great prospect",
                    "notify_on_changes": True
                }
            )

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["prospect_id"] == 100
            assert data["notes"] == "Great prospect"
            assert data["notify_on_changes"] is True

    def test_add_to_watchlist_already_exists(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test POST / endpoint when prospect already in watchlist

        Verifies that 400 is returned for duplicate entry
        """
        # Setup mock to raise ValueError
        mock_watchlist_service.add_to_watchlist.side_effect = ValueError("Prospect already in watchlist")

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.post(
                "/api/v1/watchlist/",
                json={"prospect_id": 100}
            )

            # Assert
            assert response.status_code == 400
            assert "already in watchlist" in response.json()["detail"].lower()

    def test_add_to_watchlist_prospect_not_found(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test POST / endpoint with non-existent prospect

        Verifies that 400 is returned when prospect doesn't exist
        """
        # Setup mock to raise ValueError
        mock_watchlist_service.add_to_watchlist.side_effect = ValueError("Prospect 999 not found")

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.post(
                "/api/v1/watchlist/",
                json={"prospect_id": 999}
            )

            # Assert
            assert response.status_code == 400
            assert "not found" in response.json()["detail"].lower()

    def test_add_to_watchlist_missing_prospect_id(self, client: TestClient, mock_auth_user):
        """
        Test POST / endpoint without prospect_id

        Verifies that 422 is returned for missing required field
        """
        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user):

            response = client.post(
                "/api/v1/watchlist/",
                json={"notes": "Test notes"}
            )

            # Assert
            assert response.status_code == 422  # Validation error

    def test_get_watchlist_success(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test GET / endpoint with successful watchlist retrieval

        Verifies that user can retrieve their watchlist
        """
        # Setup mock
        mock_watchlist_service.get_user_watchlist.return_value = [
            {
                "id": 1,
                "prospect_id": 100,
                "prospect_name": "John Doe",
                "prospect_position": "Forward",
                "prospect_organization": "Team A",
                "notes": "Great prospect",
                "added_at": "2025-10-03T12:00:00",
                "notify_on_changes": True
            },
            {
                "id": 2,
                "prospect_id": 101,
                "prospect_name": "Jane Smith",
                "prospect_position": "Defense",
                "prospect_organization": "Team B",
                "notes": None,
                "added_at": "2025-10-03T13:00:00",
                "notify_on_changes": False
            }
        ]

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.get("/api/v1/watchlist/")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["prospect_name"] == "John Doe"
            assert data[1]["prospect_name"] == "Jane Smith"

    def test_get_watchlist_empty(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test GET / endpoint with empty watchlist

        Verifies that empty array is returned when no entries
        """
        # Setup mock
        mock_watchlist_service.get_user_watchlist.return_value = []

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.get("/api/v1/watchlist/")

            # Assert
            assert response.status_code == 200
            assert response.json() == []

    def test_remove_from_watchlist_success(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test DELETE /{prospect_id} endpoint with successful removal

        Verifies that prospect can be removed from watchlist
        """
        # Setup mock
        mock_watchlist_service.remove_from_watchlist.return_value = {
            "message": "Prospect removed from watchlist"
        }

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.delete("/api/v1/watchlist/100")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Prospect removed from watchlist"

    def test_remove_from_watchlist_not_found(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test DELETE /{prospect_id} endpoint with non-existent entry

        Verifies that 404 is returned when entry doesn't exist
        """
        # Setup mock to raise ValueError
        mock_watchlist_service.remove_from_watchlist.side_effect = ValueError("Watchlist entry not found")

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.delete("/api/v1/watchlist/999")

            # Assert
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_update_watchlist_notes_success(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test PATCH /{prospect_id}/notes endpoint with successful update

        Verifies that notes can be updated
        """
        # Setup mock
        mock_watchlist_service.update_watchlist_notes.return_value = {
            "id": 1,
            "prospect_id": 100,
            "notes": "Updated notes",
            "updated": True
        }

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.patch(
                "/api/v1/watchlist/100/notes",
                json={"notes": "Updated notes"}
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["prospect_id"] == 100
            assert data["notes"] == "Updated notes"
            assert data["updated"] is True

    def test_update_watchlist_notes_not_found(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test PATCH /{prospect_id}/notes endpoint with non-existent entry

        Verifies that 404 is returned when entry doesn't exist
        """
        # Setup mock to raise ValueError
        mock_watchlist_service.update_watchlist_notes.side_effect = ValueError("Watchlist entry not found")

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.patch(
                "/api/v1/watchlist/999/notes",
                json={"notes": "Test notes"}
            )

            # Assert
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_toggle_notifications_enable(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test PATCH /{prospect_id}/notifications endpoint to enable notifications

        Verifies that notifications can be enabled
        """
        # Setup mock
        mock_watchlist_service.toggle_notifications.return_value = {
            "prospect_id": 100,
            "notify_on_changes": True
        }

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.patch(
                "/api/v1/watchlist/100/notifications",
                json={"enabled": True}
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["prospect_id"] == 100
            assert data["notify_on_changes"] is True

    def test_toggle_notifications_disable(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test PATCH /{prospect_id}/notifications endpoint to disable notifications

        Verifies that notifications can be disabled
        """
        # Setup mock
        mock_watchlist_service.toggle_notifications.return_value = {
            "prospect_id": 100,
            "notify_on_changes": False
        }

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.patch(
                "/api/v1/watchlist/100/notifications",
                json={"enabled": False}
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["notify_on_changes"] is False

    def test_toggle_notifications_not_found(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test PATCH /{prospect_id}/notifications endpoint with non-existent entry

        Verifies that 404 is returned when entry doesn't exist
        """
        # Setup mock to raise ValueError
        mock_watchlist_service.toggle_notifications.side_effect = ValueError("Watchlist entry not found")

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.patch(
                "/api/v1/watchlist/999/notifications",
                json={"enabled": True}
            )

            # Assert
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_watchlist_unauthorized_access(self, client: TestClient):
        """
        Test endpoints without authentication

        Verifies that 401/403 is returned when not authenticated
        """
        # Test without mocking authentication (should fail)
        endpoints = [
            ("/api/v1/watchlist/", "GET"),
            ("/api/v1/watchlist/", "POST", {"prospect_id": 100}),
            ("/api/v1/watchlist/100", "DELETE"),
            ("/api/v1/watchlist/100/notes", "PATCH", {"notes": "test"}),
            ("/api/v1/watchlist/100/notifications", "PATCH", {"enabled": True})
        ]

        for endpoint_data in endpoints:
            endpoint = endpoint_data[0]
            method = endpoint_data[1]
            payload = endpoint_data[2] if len(endpoint_data) > 2 else None

            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json=payload)
            elif method == "DELETE":
                response = client.delete(endpoint)
            elif method == "PATCH":
                response = client.patch(endpoint, json=payload)

            # Should fail authentication (401 or 403)
            assert response.status_code in [401, 403], f"{endpoint} should require authentication"

    def test_server_error_handling(self, client: TestClient, mock_auth_user, mock_watchlist_service):
        """
        Test 500 error handling for unexpected exceptions

        Verifies that server errors are handled gracefully
        """
        # Setup mock to raise unexpected exception
        mock_watchlist_service.add_to_watchlist.side_effect = Exception("Database connection failed")

        with patch("app.api.api_v1.endpoints.watchlist.get_current_user", return_value=mock_auth_user), \
             patch("app.api.api_v1.endpoints.watchlist.WatchlistService", return_value=mock_watchlist_service):

            response = client.post(
                "/api/v1/watchlist/",
                json={"prospect_id": 100}
            )

            # Assert
            assert response.status_code == 500
            assert "Failed to add to watchlist" in response.json()["detail"]
