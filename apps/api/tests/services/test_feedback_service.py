"""
Test suite for FeedbackService.

Tests feedback submission, retrieval, validation, and categorization
for different feedback types (bug, feature_request, general, nps).

@module test_feedback_service
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.feedback_service import FeedbackService
from app.db.models import Feedback


@pytest.fixture
def mock_db():
    """
    Create mock database session.

    @returns Mock AsyncSession for testing
    """
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_bug_feedback():
    """
    Create sample bug feedback for testing.

    @returns Feedback instance
    """
    return Feedback(
        id=1,
        user_id=100,
        type='bug',
        rating=None,
        message='Login page is not working',
        feature_request=None,
        submitted_at=datetime.utcnow()
    )


@pytest.fixture
def sample_feature_feedback():
    """
    Create sample feature request feedback for testing.

    @returns Feedback instance
    """
    return Feedback(
        id=2,
        user_id=100,
        type='feature_request',
        rating=None,
        message='Would love to see dark mode',
        feature_request='Dark mode toggle in settings',
        submitted_at=datetime.utcnow()
    )


@pytest.fixture
def sample_nps_feedback():
    """
    Create sample NPS feedback for testing.

    @returns Feedback instance
    """
    return Feedback(
        id=3,
        user_id=100,
        type='nps',
        rating=9,
        message='Great app, very useful!',
        feature_request=None,
        submitted_at=datetime.utcnow()
    )


@pytest.fixture
def feedback_service(mock_db):
    """
    Create FeedbackService instance with mocked dependencies.

    @param mock_db - Mock database session
    @returns FeedbackService instance
    """
    return FeedbackService(mock_db)


class TestSubmitFeedback:
    """Test suite for feedback submission."""

    @pytest.mark.asyncio
    async def test_submit_bug_feedback(
        self, feedback_service, mock_db
    ):
        """
        Test submitting bug feedback.

        Verifies that bug feedback is created with correct type and message.
        """
        # Mock feedback object that will be returned after refresh
        mock_feedback = Feedback(
            id=1,
            user_id=100,
            type='bug',
            rating=None,
            message='App crashes on startup',
            feature_request=None,
            submitted_at=datetime.utcnow()
        )

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 1))

        # Submit feedback
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='bug',
            message='App crashes on startup'
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'bug'
        assert result['message'] == 'App crashes on startup'
        assert result['rating'] is None
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_submit_feature_request_feedback(
        self, feedback_service, mock_db
    ):
        """
        Test submitting feature request feedback.

        Verifies that feature request is created with both message and feature_request.
        """
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 2))

        # Submit feedback
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='feature_request',
            message='Need better search',
            feature_request='Advanced search with filters'
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'feature_request'
        assert result['message'] == 'Need better search'
        assert result['feature_request'] == 'Advanced search with filters'
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_submit_general_feedback(
        self, feedback_service, mock_db
    ):
        """
        Test submitting general feedback.

        Verifies that general feedback is created correctly.
        """
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 3))

        # Submit feedback
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='general',
            message='Love the new UI design!'
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'general'
        assert result['message'] == 'Love the new UI design!'
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_submit_nps_feedback(
        self, feedback_service, mock_db
    ):
        """
        Test submitting NPS feedback.

        Verifies that NPS feedback is created with rating.
        """
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 4))

        # Submit feedback
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='nps',
            rating=9,
            message='Would definitely recommend!'
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'nps'
        assert result['rating'] == 9
        assert result['message'] == 'Would definitely recommend!'
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_submit_feedback_with_rating_only(
        self, feedback_service, mock_db
    ):
        """
        Test submitting feedback with rating but no message.

        Verifies that feedback can be created with only a rating.
        """
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 5))

        # Submit feedback
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='nps',
            rating=10
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'nps'
        assert result['rating'] == 10
        assert result['message'] is None
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_submit_feedback_database_error(
        self, feedback_service, mock_db
    ):
        """
        Test error handling during feedback submission.

        Verifies that database errors are handled and transaction rolled back.
        """
        # Mock database error
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        # Should raise exception
        with pytest.raises(Exception, match="Database error"):
            await feedback_service.submit_feedback(
                user_id=100,
                feedback_type='bug',
                message='Test message'
            )

        assert mock_db.rollback.called


class TestGetUserFeedback:
    """Test suite for feedback retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_feedback_with_results(
        self, feedback_service, mock_db, sample_bug_feedback, sample_nps_feedback
    ):
        """
        Test retrieving user feedback with results.

        Verifies that all feedback is returned in correct order.
        """
        # Mock database query
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            sample_nps_feedback,  # Most recent
            sample_bug_feedback
        ]

        mock_db.execute = AsyncMock(return_value=result)

        # Get feedback
        feedback_list = await feedback_service.get_user_feedback(user_id=100)

        # Assertions
        assert len(feedback_list) == 2
        assert feedback_list[0]['type'] == 'nps'
        assert feedback_list[0]['rating'] == 9
        assert feedback_list[1]['type'] == 'bug'
        assert feedback_list[1]['message'] == 'Login page is not working'

    @pytest.mark.asyncio
    async def test_get_user_feedback_empty_results(
        self, feedback_service, mock_db
    ):
        """
        Test retrieving feedback for user with no feedback.

        Verifies that empty list is returned.
        """
        # Mock database query with no results
        result = MagicMock()
        result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(return_value=result)

        # Get feedback
        feedback_list = await feedback_service.get_user_feedback(user_id=100)

        # Assertions
        assert len(feedback_list) == 0
        assert feedback_list == []

    @pytest.mark.asyncio
    async def test_get_user_feedback_error_handling(
        self, feedback_service, mock_db
    ):
        """
        Test error handling during feedback retrieval.

        Verifies that empty list is returned on error.
        """
        # Mock database error
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

        # Get feedback
        feedback_list = await feedback_service.get_user_feedback(user_id=100)

        # Should return empty list on error
        assert feedback_list == []


class TestFeedbackValidation:
    """Test suite for feedback validation."""

    @pytest.mark.asyncio
    async def test_submit_feedback_with_all_fields(
        self, feedback_service, mock_db
    ):
        """
        Test submitting feedback with all optional fields.

        Verifies that all fields are preserved correctly.
        """
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 6))

        # Submit feedback with all fields
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='feature_request',
            rating=8,
            message='Great app but needs improvements',
            feature_request='Add export functionality'
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'feature_request'
        assert result['rating'] == 8
        assert result['message'] == 'Great app but needs improvements'
        assert result['feature_request'] == 'Add export functionality'

    @pytest.mark.asyncio
    async def test_submit_feedback_minimal_fields(
        self, feedback_service, mock_db
    ):
        """
        Test submitting feedback with minimal required fields.

        Verifies that feedback can be created with just user_id and type.
        """
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, 'id', 7))

        # Submit feedback with minimal fields
        result = await feedback_service.submit_feedback(
            user_id=100,
            feedback_type='general'
        )

        # Assertions
        assert result['user_id'] == 100
        assert result['type'] == 'general'
        assert result['rating'] is None
        assert result['message'] is None
        assert result['feature_request'] is None
