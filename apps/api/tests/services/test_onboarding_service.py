"""
Test suite for OnboardingService

Tests onboarding flow operations including initialization, step progression,
completion, skip, and reset functionality.

@module test_onboarding_service
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.onboarding_service import OnboardingService
from app.db.models import User


@pytest.fixture
def mock_db():
    """
    Create mock database session

    @returns Mock AsyncSession for testing
    """
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_user():
    """
    Create sample user for testing with default onboarding state

    @returns User instance with onboarding fields initialized
    """
    user = User(
        id=1,
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashed_password",
        is_active=True,
        onboarding_completed=False,
        onboarding_step=0,
        onboarding_started_at=None,
        onboarding_completed_at=None,
        subscription_tier="free",
        privacy_policy_accepted=True,
        data_processing_accepted=True,
        marketing_emails_accepted=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return user


@pytest.fixture
def user_mid_onboarding():
    """
    Create user who is mid-way through onboarding

    @returns User instance at step 2 of onboarding
    """
    user = User(
        id=2,
        email="midway@example.com",
        full_name="Midway User",
        hashed_password="hashed_password",
        is_active=True,
        onboarding_completed=False,
        onboarding_step=2,
        onboarding_started_at=datetime.now(),
        onboarding_completed_at=None,
        subscription_tier="free",
        privacy_policy_accepted=True,
        data_processing_accepted=True,
        marketing_emails_accepted=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return user


@pytest.fixture
def user_completed_onboarding():
    """
    Create user who has completed onboarding

    @returns User instance with completed onboarding
    """
    user = User(
        id=3,
        email="completed@example.com",
        full_name="Completed User",
        hashed_password="hashed_password",
        is_active=True,
        onboarding_completed=True,
        onboarding_step=5,
        onboarding_started_at=datetime.now(),
        onboarding_completed_at=datetime.now(),
        subscription_tier="free",
        privacy_policy_accepted=True,
        data_processing_accepted=True,
        marketing_emails_accepted=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return user


class TestOnboardingService:
    """Test OnboardingService methods"""

    @pytest.mark.asyncio
    async def test_start_onboarding_new_user(self, mock_db, sample_user):
        """
        Test starting onboarding for a new user

        Verifies that onboarding_started_at is set and step is initialized to 0
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user
        service = OnboardingService(mock_db)

        # Execute
        result = await service.start_onboarding(user_id=1)

        # Assert
        assert result["user_id"] == 1
        assert result["current_step"] == 0
        assert result["current_step_name"] == "welcome"
        assert result["total_steps"] == 6
        assert result["is_completed"] is False
        assert result["progress_percentage"] == 0.0
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_start_onboarding_already_started(self, mock_db, user_mid_onboarding):
        """
        Test starting onboarding for user who already started

        Verifies that existing progress is preserved and not reset
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = user_mid_onboarding
        service = OnboardingService(mock_db)

        # Execute
        result = await service.start_onboarding(user_id=2)

        # Assert
        assert result["current_step"] == 2
        assert result["current_step_name"] == "feature_tour_profiles"
        assert mock_db.commit.call_count == 0  # Should not commit if already started

    @pytest.mark.asyncio
    async def test_start_onboarding_user_not_found(self, mock_db):
        """
        Test starting onboarding for non-existent user

        Verifies that ValueError is raised when user not found
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        service = OnboardingService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="User with id 999 not found"):
            await service.start_onboarding(user_id=999)

    @pytest.mark.asyncio
    async def test_progress_step_valid(self, mock_db, sample_user):
        """
        Test progressing to a valid onboarding step

        Verifies that step is updated correctly and progress percentage calculated
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user
        service = OnboardingService(mock_db)

        # Execute
        result = await service.progress_step(user_id=1, step=3)

        # Assert
        assert result["current_step"] == 3
        assert result["current_step_name"] == "feature_tour_comparisons"
        assert result["progress_percentage"] == pytest.approx(50.0, rel=0.1)
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_progress_step_invalid_step_too_high(self, mock_db, sample_user):
        """
        Test progressing to invalid step number (too high)

        Verifies that ValueError is raised for out-of-range step
        """
        # Setup
        service = OnboardingService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Invalid step 10"):
            await service.progress_step(user_id=1, step=10)

    @pytest.mark.asyncio
    async def test_progress_step_invalid_step_negative(self, mock_db, sample_user):
        """
        Test progressing to invalid step number (negative)

        Verifies that ValueError is raised for negative step
        """
        # Setup
        service = OnboardingService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Invalid step -1"):
            await service.progress_step(user_id=1, step=-1)

    @pytest.mark.asyncio
    async def test_complete_onboarding(self, mock_db, user_mid_onboarding):
        """
        Test completing onboarding flow

        Verifies that completion flag is set and timestamp recorded
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = user_mid_onboarding
        service = OnboardingService(mock_db)

        # Execute
        result = await service.complete_onboarding(user_id=2)

        # Assert
        assert result["user_id"] == 2
        assert result["is_completed"] is True
        assert "completed_at" in result
        assert result["message"] == "Onboarding completed successfully"
        assert mock_db.commit.called
        assert user_mid_onboarding.onboarding_completed is True
        assert user_mid_onboarding.onboarding_step == 5  # Final step

    @pytest.mark.asyncio
    async def test_skip_onboarding(self, mock_db, sample_user):
        """
        Test skipping onboarding flow

        Verifies that skip marks onboarding as completed
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user
        service = OnboardingService(mock_db)

        # Execute
        result = await service.skip_onboarding(user_id=1)

        # Assert
        assert result["is_completed"] is True
        assert "completed_at" in result
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_get_onboarding_status(self, mock_db, user_mid_onboarding):
        """
        Test retrieving onboarding status

        Verifies that all status fields are returned correctly
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = user_mid_onboarding
        service = OnboardingService(mock_db)

        # Execute
        result = await service.get_onboarding_status(user_id=2)

        # Assert
        assert result["user_id"] == 2
        assert result["current_step"] == 2
        assert result["current_step_name"] == "feature_tour_profiles"
        assert result["total_steps"] == 6
        assert result["is_completed"] is False
        assert "started_at" in result
        assert result["started_at"] is not None

    @pytest.mark.asyncio
    async def test_get_onboarding_status_completed(self, mock_db, user_completed_onboarding):
        """
        Test retrieving status for completed onboarding

        Verifies that completed status includes completion timestamp
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = user_completed_onboarding
        service = OnboardingService(mock_db)

        # Execute
        result = await service.get_onboarding_status(user_id=3)

        # Assert
        assert result["is_completed"] is True
        assert result["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_reset_onboarding(self, mock_db, user_completed_onboarding):
        """
        Test resetting onboarding progress

        Verifies that all onboarding fields are cleared
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = user_completed_onboarding
        service = OnboardingService(mock_db)

        # Execute
        result = await service.reset_onboarding(user_id=3)

        # Assert
        assert result["user_id"] == 3
        assert result["current_step"] == 0
        assert result["is_completed"] is False
        assert result["message"] == "Onboarding reset successfully"
        assert user_completed_onboarding.onboarding_completed is False
        assert user_completed_onboarding.onboarding_step == 0
        assert user_completed_onboarding.onboarding_started_at is None
        assert user_completed_onboarding.onboarding_completed_at is None
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_reset_onboarding_user_not_found(self, mock_db):
        """
        Test resetting onboarding for non-existent user

        Verifies that ValueError is raised when user not found
        """
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        service = OnboardingService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="User with id 999 not found"):
            await service.reset_onboarding(user_id=999)

    @pytest.mark.asyncio
    async def test_progress_percentage_calculation(self, mock_db, sample_user):
        """
        Test progress percentage calculation accuracy

        Verifies that percentage is calculated correctly at different steps
        """
        # Setup
        service = OnboardingService(mock_db)
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user

        # Test step 0 (0%)
        result = await service.progress_step(user_id=1, step=0)
        assert result["progress_percentage"] == 0.0

        # Test step 3 (50%)
        result = await service.progress_step(user_id=1, step=3)
        assert result["progress_percentage"] == pytest.approx(50.0, rel=0.1)

        # Test step 5 (83.33%)
        result = await service.progress_step(user_id=1, step=5)
        assert result["progress_percentage"] == pytest.approx(83.33, rel=0.1)
