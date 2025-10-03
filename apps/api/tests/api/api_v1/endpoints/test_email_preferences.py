"""
Integration tests for email preferences API endpoints.

Tests GET/PUT email preferences, unsubscribe, and preview functionality.

@module test_email_preferences
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.main import app


@pytest.fixture
def client():
    """
    Create test client for API requests.

    @returns FastAPI TestClient instance
    """
    return TestClient(app)


@pytest.fixture
def mock_auth_user():
    """
    Mock authenticated user for testing.

    @returns Mock User object
    """
    from app.models.user import User

    return User(
        id=1,
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        subscription_tier="free",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


class TestGetEmailPreferences:
    """Test suite for GET /users/email-preferences endpoint."""

    def test_get_email_preferences_success(self, client, mock_auth_user):
        """
        Test successful retrieval of email preferences.

        Verifies that authenticated user can retrieve their email settings.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
                # Mock database query
                mock_session = AsyncMock()
                mock_result = MagicMock()

                from app.models.engagement import EmailPreferences
                test_prefs = EmailPreferences(
                    id=1,
                    user_id=1,
                    digest_enabled=True,
                    frequency="weekly",
                    preferences={},
                    last_sent=None,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                mock_result.scalar_one_or_none.return_value = test_prefs
                mock_session.execute.return_value = mock_result
                mock_db.return_value.__aenter__.return_value = mock_session

                response = client.get("/api/v1/users/email-preferences")

                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["digest_enabled"] is True
                assert data["frequency"] == "weekly"

    def test_get_email_preferences_unauthorized(self, client):
        """
        Test email preferences retrieval without authentication.

        Verifies that 401 is returned for unauthenticated requests.
        """
        response = client.get("/api/v1/users/email-preferences")

        # Should return 401 Unauthorized
        assert response.status_code == 401


class TestUpdateEmailPreferences:
    """Test suite for PUT /users/email-preferences endpoint."""

    def test_update_digest_enabled(self, client, mock_auth_user):
        """
        Test updating digest enabled status.

        Verifies that user can disable email digests.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
                mock_session = AsyncMock()
                mock_result = MagicMock()

                from app.models.engagement import EmailPreferences
                updated_prefs = EmailPreferences(
                    id=1,
                    user_id=1,
                    digest_enabled=False,
                    frequency="weekly",
                    preferences={},
                    last_sent=None,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                mock_result.scalar_one_or_none.return_value = updated_prefs
                mock_session.execute.return_value = mock_result
                mock_session.commit = AsyncMock()
                mock_db.return_value.__aenter__.return_value = mock_session

                response = client.put(
                    "/api/v1/users/email-preferences",
                    json={"digest_enabled": False}
                )

                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["digest_enabled"] is False

    def test_update_frequency(self, client, mock_auth_user):
        """
        Test updating digest frequency.

        Verifies that user can change from weekly to daily digests.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
                mock_session = AsyncMock()
                mock_result = MagicMock()

                from app.models.engagement import EmailPreferences
                updated_prefs = EmailPreferences(
                    id=1,
                    user_id=1,
                    digest_enabled=True,
                    frequency="daily",
                    preferences={},
                    last_sent=None,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                mock_result.scalar_one_or_none.return_value = updated_prefs
                mock_session.execute.return_value = mock_result
                mock_session.commit = AsyncMock()
                mock_db.return_value.__aenter__.return_value = mock_session

                response = client.put(
                    "/api/v1/users/email-preferences",
                    json={"frequency": "daily"}
                )

                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["frequency"] == "daily"

    def test_update_invalid_frequency(self, client, mock_auth_user):
        """
        Test updating with invalid frequency value.

        Verifies that 400 error is returned for invalid frequency.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db'):
                response = client.put(
                    "/api/v1/users/email-preferences",
                    json={"frequency": "hourly"}  # Invalid
                )

                # Should return 400 Bad Request
                assert response.status_code == 400
                assert "Invalid frequency" in response.json()["detail"]

    def test_update_no_values(self, client, mock_auth_user):
        """
        Test update with no values provided.

        Verifies that 400 error is returned when update is empty.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db'):
                response = client.put(
                    "/api/v1/users/email-preferences",
                    json={}
                )

                # Should return 400 Bad Request
                assert response.status_code == 400
                assert "No update values" in response.json()["detail"]


class TestUnsubscribe:
    """Test suite for POST /users/unsubscribe endpoint."""

    def test_unsubscribe_valid_token(self, client):
        """
        Test unsubscribe with valid token.

        Verifies that user is unsubscribed successfully with valid JWT.
        """
        with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
            mock_session = AsyncMock()

            # Mock EmailDigestService
            with patch('app.api.api_v1.endpoints.email_preferences.EmailDigestService') as mock_service:
                mock_instance = MagicMock()
                mock_instance.verify_unsubscribe_token.return_value = 123
                mock_instance.unsubscribe_user.return_value = True
                mock_service.return_value = mock_instance

                mock_db.return_value.__aenter__.return_value = mock_session

                response = client.post(
                    "/api/v1/users/unsubscribe",
                    json={"token": "valid.jwt.token"}
                )

                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "unsubscribed" in data["message"].lower()

    def test_unsubscribe_invalid_token(self, client):
        """
        Test unsubscribe with invalid token.

        Verifies that 400 error is returned for invalid tokens.
        """
        with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
            mock_session = AsyncMock()

            with patch('app.api.api_v1.endpoints.email_preferences.EmailDigestService') as mock_service:
                mock_instance = MagicMock()
                mock_instance.verify_unsubscribe_token.return_value = None  # Invalid
                mock_service.return_value = mock_instance

                mock_db.return_value.__aenter__.return_value = mock_session

                response = client.post(
                    "/api/v1/users/unsubscribe",
                    json={"token": "invalid.token"}
                )

                # Should return 400 Bad Request
                assert response.status_code == 400
                assert "Invalid or expired" in response.json()["detail"]


class TestPreviewDigest:
    """Test suite for GET /users/preview-digest endpoint."""

    def test_preview_digest_success(self, client, mock_auth_user):
        """
        Test successful digest preview generation.

        Verifies that authenticated user can preview their digest content.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
                mock_session = AsyncMock()

                with patch('app.api.api_v1.endpoints.email_preferences.EmailDigestService') as mock_service:
                    mock_instance = MagicMock()
                    mock_instance.generate_digest_content.return_value = {
                        "user_name": "Test User",
                        "user_email": "test@example.com",
                        "watchlist_updates": [],
                        "top_movers": [],
                        "recommendations": [],
                        "achievement_progress": {},
                        "generated_at": datetime.utcnow()
                    }
                    mock_service.return_value = mock_instance

                    mock_db.return_value.__aenter__.return_value = mock_session

                    response = client.get("/api/v1/users/preview-digest")

                    # Assertions
                    assert response.status_code == 200
                    data = response.json()
                    assert "content" in data
                    assert data["content"]["user_name"] == "Test User"

    def test_preview_digest_disabled(self, client, mock_auth_user):
        """
        Test preview when digests are disabled.

        Verifies that appropriate message is returned when digests disabled.
        """
        with patch('app.core.auth.get_current_user', return_value=mock_auth_user):
            with patch('app.api.api_v1.endpoints.email_preferences.get_db') as mock_db:
                mock_session = AsyncMock()

                with patch('app.api.api_v1.endpoints.email_preferences.EmailDigestService') as mock_service:
                    mock_instance = MagicMock()
                    mock_instance.generate_digest_content.return_value = None  # Disabled
                    mock_service.return_value = mock_instance

                    mock_db.return_value.__aenter__.return_value = mock_session

                    response = client.get("/api/v1/users/preview-digest")

                    # Assertions
                    assert response.status_code == 200
                    data = response.json()
                    assert data["content"] is None
                    assert "disabled" in data["message"].lower()

    def test_preview_digest_unauthorized(self, client):
        """
        Test preview digest without authentication.

        Verifies that 401 is returned for unauthenticated requests.
        """
        response = client.get("/api/v1/users/preview-digest")

        # Should return 401 Unauthorized
        assert response.status_code == 401
