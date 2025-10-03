"""
Test suite for EmailDigestService.

Tests email digest generation, content personalization, sending, scheduling,
and unsubscribe functionality.

@module test_email_digest_service
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.services.email_digest_service import EmailDigestService
from app.models.user import User
from app.models.engagement import EmailPreferences


@pytest.fixture
def mock_db():
    """
    Create mock database session.

    @returns Mock AsyncSession for testing
    """
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_user():
    """
    Create sample user for testing.

    @returns User instance
    """
    return User(
        id=1,
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        subscription_tier="free",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_email_preferences():
    """
    Create sample email preferences for testing.

    @returns EmailPreferences instance
    """
    return EmailPreferences(
        id=1,
        user_id=1,
        digest_enabled=True,
        frequency="weekly",
        preferences={},
        last_sent=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def email_digest_service(mock_db):
    """
    Create EmailDigestService instance with mocked dependencies.

    @param mock_db - Mock database session
    @returns EmailDigestService instance
    """
    service = EmailDigestService(mock_db)
    service.resend_api_key = None  # Disable Resend for tests
    return service


class TestEmailDigestContentGeneration:
    """Test suite for digest content generation."""

    @pytest.mark.asyncio
    async def test_generate_digest_content_success(
        self, email_digest_service, mock_db, sample_user, sample_email_preferences
    ):
        """
        Test successful digest content generation.

        Verifies that digest content is generated correctly with all sections
        when user exists and has digests enabled.
        """
        # Mock database queries
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        prefs_result = MagicMock()
        prefs_result.scalar_one_or_none.return_value = sample_email_preferences

        mock_db.execute.side_effect = [user_result, prefs_result]

        # Generate content
        content = await email_digest_service.generate_digest_content(user_id=1)

        # Assertions
        assert content is not None
        assert content["user_name"] == "Test User"
        assert content["user_email"] == "test@example.com"
        assert "watchlist_updates" in content
        assert "top_movers" in content
        assert "recommendations" in content
        assert "achievement_progress" in content
        assert "generated_at" in content

    @pytest.mark.asyncio
    async def test_generate_digest_content_user_not_found(
        self, email_digest_service, mock_db
    ):
        """
        Test digest generation when user not found.

        Verifies that ValueError is raised when user ID is invalid.
        """
        # Mock user not found
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = None

        mock_db.execute.return_value = user_result

        # Should raise ValueError
        with pytest.raises(ValueError, match="User .* not found"):
            await email_digest_service.generate_digest_content(user_id=999)

    @pytest.mark.asyncio
    async def test_generate_digest_content_digests_disabled(
        self, email_digest_service, mock_db, sample_user
    ):
        """
        Test digest generation when user has digests disabled.

        Verifies that None is returned when digest_enabled is False.
        """
        # Mock database queries
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = sample_user

        disabled_prefs = EmailPreferences(
            id=1,
            user_id=1,
            digest_enabled=False,
            frequency="weekly",
            preferences={},
            last_sent=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        prefs_result = MagicMock()
        prefs_result.scalar_one_or_none.return_value = disabled_prefs

        mock_db.execute.side_effect = [user_result, prefs_result]

        # Generate content
        content = await email_digest_service.generate_digest_content(user_id=1)

        # Should return None for disabled digests
        assert content is None


class TestEmailSending:
    """Test suite for email sending operations."""

    @pytest.mark.asyncio
    async def test_send_digest_success(
        self, email_digest_service, mock_db, sample_user, sample_email_preferences
    ):
        """
        Test successful digest email sending.

        Verifies that digest is sent and last_sent timestamp is updated.
        """
        # Mock content generation
        test_content = {
            "user_name": "Test User",
            "user_email": "test@example.com",
            "watchlist_updates": [],
            "top_movers": [],
            "recommendations": [],
            "achievement_progress": {},
            "generated_at": datetime.utcnow()
        }

        # Mock database updates
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        # Send digest
        success = await email_digest_service.send_digest(
            user_id=1, content=test_content
        )

        # Assertions
        assert success is True
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_send_digest_without_content(
        self, email_digest_service, mock_db
    ):
        """
        Test digest sending without provided content.

        Verifies that service generates content if not provided.
        """
        # Mock content generation to return None (digests disabled)
        with patch.object(
            email_digest_service,
            'generate_digest_content',
            return_value=None
        ):
            success = await email_digest_service.send_digest(user_id=1)

            # Should return False if no content
            assert success is False

    @pytest.mark.asyncio
    async def test_update_last_sent_timestamp(
        self, email_digest_service, mock_db
    ):
        """
        Test that last_sent timestamp is updated after sending.

        Verifies that the database update occurs with correct timestamp.
        """
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        await email_digest_service._update_last_sent(user_id=1)

        # Verify update was called
        assert mock_db.execute.called
        assert mock_db.commit.called


class TestDigestScheduling:
    """Test suite for digest scheduling operations."""

    @pytest.mark.asyncio
    async def test_get_users_for_weekly_digest(
        self, email_digest_service, mock_db
    ):
        """
        Test retrieving users eligible for weekly digest.

        Verifies that correct users are returned based on frequency and last_sent.
        """
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,), (2,), (3,)]

        mock_db.execute = AsyncMock(return_value=mock_result)

        user_ids = await email_digest_service.get_users_for_digest(frequency="weekly")

        # Assertions
        assert len(user_ids) == 3
        assert user_ids == [1, 2, 3]
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_get_users_for_daily_digest(
        self, email_digest_service, mock_db
    ):
        """
        Test retrieving users eligible for daily digest.

        Verifies that daily frequency filter works correctly.
        """
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(5,)]

        mock_db.execute = AsyncMock(return_value=mock_result)

        user_ids = await email_digest_service.get_users_for_digest(frequency="daily")

        # Assertions
        assert len(user_ids) == 1
        assert user_ids == [5]

    @pytest.mark.asyncio
    async def test_get_users_invalid_frequency(
        self, email_digest_service, mock_db
    ):
        """
        Test error handling for invalid frequency.

        Verifies that ValueError is raised for invalid frequency values.
        """
        with pytest.raises(ValueError, match="Invalid frequency"):
            await email_digest_service.get_users_for_digest(frequency="invalid")


class TestUnsubscribeFunctionality:
    """Test suite for unsubscribe operations."""

    def test_generate_unsubscribe_token(self, email_digest_service):
        """
        Test unsubscribe token generation.

        Verifies that a valid JWT token is created with correct payload.
        """
        user_id = 123
        token = email_digest_service.generate_unsubscribe_token(user_id)

        # Token should be non-empty string
        assert token
        assert isinstance(token, str)

        # Decode and verify payload
        from app.core.config import settings
        secret_key = getattr(settings, 'SECRET_KEY', 'dev-secret-key')
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])

        assert payload["user_id"] == user_id
        assert payload["action"] == "unsubscribe"
        assert "exp" in payload

    def test_verify_unsubscribe_token_valid(self, email_digest_service):
        """
        Test verification of valid unsubscribe token.

        Verifies that user ID is correctly extracted from valid token.
        """
        user_id = 456
        token = email_digest_service.generate_unsubscribe_token(user_id)

        # Verify token
        verified_user_id = email_digest_service.verify_unsubscribe_token(token)

        assert verified_user_id == user_id

    def test_verify_unsubscribe_token_invalid(self, email_digest_service):
        """
        Test verification of invalid token.

        Verifies that None is returned for malformed tokens.
        """
        invalid_token = "invalid.token.string"

        verified_user_id = email_digest_service.verify_unsubscribe_token(invalid_token)

        assert verified_user_id is None

    def test_verify_unsubscribe_token_wrong_action(self, email_digest_service):
        """
        Test verification of token with wrong action.

        Verifies that None is returned if action is not 'unsubscribe'.
        """
        from app.core.config import settings
        secret_key = getattr(settings, 'SECRET_KEY', 'dev-secret-key')

        # Create token with wrong action
        payload = {
            "user_id": 789,
            "action": "verify_email",
            "exp": datetime.utcnow() + timedelta(days=1)
        }
        wrong_token = jwt.encode(payload, secret_key, algorithm="HS256")

        verified_user_id = email_digest_service.verify_unsubscribe_token(wrong_token)

        assert verified_user_id is None

    @pytest.mark.asyncio
    async def test_unsubscribe_user_success(
        self, email_digest_service, mock_db
    ):
        """
        Test successful user unsubscribe.

        Verifies that digest_enabled is set to False and changes are committed.
        """
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        success = await email_digest_service.unsubscribe_user(user_id=1)

        # Assertions
        assert success is True
        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_unsubscribe_user_database_error(
        self, email_digest_service, mock_db
    ):
        """
        Test unsubscribe with database error.

        Verifies that False is returned and transaction is rolled back on error.
        """
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        success = await email_digest_service.unsubscribe_user(user_id=1)

        # Assertions
        assert success is False
        assert mock_db.rollback.called


class TestTemplateRendering:
    """Test suite for email template rendering."""

    @pytest.mark.asyncio
    async def test_render_digest_template(self, email_digest_service):
        """
        Test HTML email template rendering.

        Verifies that template is rendered with correct content placeholders.
        """
        content = {
            "user_name": "John Doe",
            "user_email": "john@example.com",
            "watchlist_updates": [],
            "top_movers": [],
            "recommendations": [],
            "achievement_progress": {},
            "generated_at": datetime.utcnow()
        }

        html = await email_digest_service._render_digest_template(content)

        # Assertions
        assert html
        assert "John Doe" in html
        assert "DOCTYPE html" in html
        assert "unsubscribe" in html.lower()
