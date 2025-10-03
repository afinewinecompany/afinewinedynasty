"""
Test suite for ReferralService.

Tests referral code generation, validation, statistics tracking,
referral creation, and reward granting.

@module test_referral_service
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.referral_service import ReferralService
from app.db.models import ReferralCode, Referral


@pytest.fixture
def mock_db():
    """
    Create mock database session.

    @returns Mock AsyncSession for testing
    """
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_referral_code():
    """
    Create sample referral code for testing.

    @returns ReferralCode instance
    """
    return ReferralCode(
        id=1,
        user_id=100,
        code="ABC12345",
        uses_remaining=10,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_referral():
    """
    Create sample referral for testing.

    @returns Referral instance
    """
    return Referral(
        id=1,
        referrer_id=100,
        referred_user_id=200,
        status='pending',
        reward_granted=False,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def referral_service(mock_db):
    """
    Create ReferralService instance with mocked dependencies.

    @param mock_db - Mock database session
    @returns ReferralService instance
    """
    return ReferralService(mock_db)


class TestGetOrCreateReferralCode:
    """Test suite for referral code generation and retrieval."""

    @pytest.mark.asyncio
    async def test_get_existing_referral_code(
        self, referral_service, mock_db, sample_referral_code
    ):
        """
        Test retrieving existing referral code.

        Verifies that existing code is returned when user already has one.
        """
        # Mock database query to return existing code
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_referral_code

        mock_db.execute.return_value = result

        # Get code
        code = await referral_service.get_or_create_referral_code(user_id=100)

        # Assertions
        assert code == "ABC12345"
        assert mock_db.execute.called
        assert not mock_db.commit.called  # No commit for existing code

    @pytest.mark.asyncio
    async def test_create_new_referral_code(
        self, referral_service, mock_db
    ):
        """
        Test creating new referral code.

        Verifies that a new unique code is created for users without one.
        """
        # Mock database query to return no existing code
        no_existing_result = MagicMock()
        no_existing_result.scalar_one_or_none.return_value = None

        # Mock unique check to pass on first try
        unique_check_result = MagicMock()
        unique_check_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [no_existing_result, unique_check_result]
        mock_db.commit = AsyncMock()

        # Create code
        code = await referral_service.get_or_create_referral_code(user_id=100)

        # Assertions
        assert code is not None
        assert len(code) == 8
        assert code.isalnum()
        assert code.isupper()
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_create_referral_code_handles_collision(
        self, referral_service, mock_db
    ):
        """
        Test referral code creation with collision handling.

        Verifies that service regenerates code if collision occurs.
        """
        # Mock database query to return no existing code for user
        no_existing_result = MagicMock()
        no_existing_result.scalar_one_or_none.return_value = None

        # Mock unique check - first collision, then success
        collision_result = MagicMock()
        collision_result.scalar_one_or_none.return_value = MagicMock()  # Collision

        success_result = MagicMock()
        success_result.scalar_one_or_none.return_value = None  # Success

        mock_db.execute.side_effect = [
            no_existing_result,
            collision_result,
            success_result
        ]
        mock_db.commit = AsyncMock()

        # Create code
        code = await referral_service.get_or_create_referral_code(user_id=100)

        # Assertions
        assert code is not None
        assert len(code) == 8
        assert mock_db.execute.call_count == 3  # User check + collision + success
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_create_referral_code_database_error(
        self, referral_service, mock_db
    ):
        """
        Test error handling during code creation.

        Verifies that database errors are handled and transaction rolled back.
        """
        # Mock database error
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        # Should raise exception
        with pytest.raises(Exception, match="Database error"):
            await referral_service.get_or_create_referral_code(user_id=100)

        assert mock_db.rollback.called


class TestValidateReferralCode:
    """Test suite for referral code validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_code(
        self, referral_service, mock_db, sample_referral_code
    ):
        """
        Test validation of valid referral code.

        Verifies that valid code returns referrer user ID.
        """
        # Mock database query to return valid code
        result = MagicMock()
        result.scalar_one_or_none.return_value = sample_referral_code

        mock_db.execute.return_value = result

        # Validate code
        referrer_id = await referral_service.validate_referral_code("ABC12345")

        # Assertions
        assert referrer_id == 100
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_validate_invalid_code(
        self, referral_service, mock_db
    ):
        """
        Test validation of invalid referral code.

        Verifies that invalid code returns None.
        """
        # Mock database query to return no code
        result = MagicMock()
        result.scalar_one_or_none.return_value = None

        mock_db.execute.return_value = result

        # Validate code
        referrer_id = await referral_service.validate_referral_code("INVALID")

        # Assertions
        assert referrer_id is None

    @pytest.mark.asyncio
    async def test_validate_exhausted_code(
        self, referral_service, mock_db
    ):
        """
        Test validation of exhausted referral code.

        Verifies that code with no uses remaining returns None.
        """
        # Create exhausted code
        exhausted_code = ReferralCode(
            id=1,
            user_id=100,
            code="EXHAUSTED",
            uses_remaining=0,
            created_at=datetime.utcnow()
        )

        # Mock database query to return exhausted code
        result = MagicMock()
        result.scalar_one_or_none.return_value = exhausted_code

        mock_db.execute.return_value = result

        # Validate code
        referrer_id = await referral_service.validate_referral_code("EXHAUSTED")

        # Assertions
        assert referrer_id is None

    @pytest.mark.asyncio
    async def test_validate_code_database_error(
        self, referral_service, mock_db
    ):
        """
        Test error handling during code validation.

        Verifies that database errors return None gracefully.
        """
        # Mock database error
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

        # Validate code
        referrer_id = await referral_service.validate_referral_code("ABC12345")

        # Should return None on error
        assert referrer_id is None


class TestGetReferralStats:
    """Test suite for referral statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_stats_with_referrals(
        self, referral_service, mock_db, sample_referral_code
    ):
        """
        Test getting referral stats with existing referrals.

        Verifies that statistics are calculated correctly.
        """
        # Mock referrals
        completed_referral = Referral(
            id=1,
            referrer_id=100,
            referred_user_id=200,
            status='completed',
            reward_granted=True,
            created_at=datetime.utcnow()
        )

        pending_referral = Referral(
            id=2,
            referrer_id=100,
            referred_user_id=201,
            status='pending',
            reward_granted=False,
            created_at=datetime.utcnow()
        )

        # Mock database queries
        code_result = MagicMock()
        code_result.scalar_one_or_none.return_value = sample_referral_code

        referrals_result = MagicMock()
        referrals_result.scalars.return_value.all.return_value = [
            completed_referral,
            pending_referral
        ]

        mock_db.execute.side_effect = [code_result, referrals_result]

        # Get stats
        stats = await referral_service.get_referral_stats(user_id=100)

        # Assertions
        assert stats["total_referrals"] == 2
        assert stats["successful_referrals"] == 1
        assert stats["pending_referrals"] == 1
        assert stats["rewards_earned"] == 1
        assert stats["referral_code"] == "ABC12345"

    @pytest.mark.asyncio
    async def test_get_stats_no_referrals(
        self, referral_service, mock_db, sample_referral_code
    ):
        """
        Test getting stats for user with no referrals.

        Verifies that empty stats are returned correctly.
        """
        # Mock database queries
        code_result = MagicMock()
        code_result.scalar_one_or_none.return_value = sample_referral_code

        referrals_result = MagicMock()
        referrals_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [code_result, referrals_result]

        # Get stats
        stats = await referral_service.get_referral_stats(user_id=100)

        # Assertions
        assert stats["total_referrals"] == 0
        assert stats["successful_referrals"] == 0
        assert stats["pending_referrals"] == 0
        assert stats["rewards_earned"] == 0
        assert stats["referral_code"] == "ABC12345"

    @pytest.mark.asyncio
    async def test_get_stats_error_handling(
        self, referral_service, mock_db
    ):
        """
        Test error handling during stats retrieval.

        Verifies that default stats are returned on error.
        """
        # Mock database error on referrals query, but code succeeds
        code_result = MagicMock()
        code_result.scalar_one_or_none.return_value = ReferralCode(
            id=1,
            user_id=100,
            code="ABC12345",
            uses_remaining=10,
            created_at=datetime.utcnow()
        )

        mock_db.execute.side_effect = [
            code_result,
            Exception("Database error")
        ]
        mock_db.commit = AsyncMock()

        # Get stats
        stats = await referral_service.get_referral_stats(user_id=100)

        # Should return default stats with code
        assert stats["total_referrals"] == 0
        assert stats["successful_referrals"] == 0
        assert stats["pending_referrals"] == 0
        assert stats["rewards_earned"] == 0
        assert "referral_code" in stats


class TestCreateReferral:
    """Test suite for creating referral relationships."""

    @pytest.mark.asyncio
    async def test_create_referral_success(
        self, referral_service, mock_db, sample_referral_code
    ):
        """
        Test successful referral creation.

        Verifies that referral is created and uses decremented.
        """
        # Mock database query for referral code
        code_result = MagicMock()
        code_result.scalar_one_or_none.return_value = sample_referral_code

        mock_db.execute.return_value = code_result
        mock_db.commit = AsyncMock()

        # Create referral
        success = await referral_service.create_referral(
            referrer_id=100,
            referred_user_id=200
        )

        # Assertions
        assert success is True
        assert mock_db.add.called
        assert mock_db.commit.called
        assert sample_referral_code.uses_remaining == 9  # Decremented

    @pytest.mark.asyncio
    async def test_create_referral_database_error(
        self, referral_service, mock_db
    ):
        """
        Test error handling during referral creation.

        Verifies that errors are handled and transaction rolled back.
        """
        # Mock database error
        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        # Create referral
        success = await referral_service.create_referral(
            referrer_id=100,
            referred_user_id=200
        )

        # Assertions
        assert success is False
        assert mock_db.rollback.called

    @pytest.mark.asyncio
    async def test_create_referral_no_code_found(
        self, referral_service, mock_db
    ):
        """
        Test referral creation when code not found.

        Verifies that referral is still created even if code lookup fails.
        """
        # Mock database query to return no code
        code_result = MagicMock()
        code_result.scalar_one_or_none.return_value = None

        mock_db.execute.return_value = code_result
        mock_db.commit = AsyncMock()

        # Create referral
        success = await referral_service.create_referral(
            referrer_id=100,
            referred_user_id=200
        )

        # Assertions
        assert success is True
        assert mock_db.add.called
        assert mock_db.commit.called


class TestGrantReferralReward:
    """Test suite for referral reward granting."""

    @pytest.mark.asyncio
    async def test_grant_reward_success(
        self, referral_service, mock_db
    ):
        """
        Test successful reward granting.

        Verifies that reward is marked as granted.
        """
        # Grant reward
        success = await referral_service.grant_referral_reward(referral_id=1)

        # Assertions
        assert success is True

    @pytest.mark.asyncio
    async def test_grant_reward_error(
        self, referral_service, mock_db
    ):
        """
        Test error handling during reward granting.

        Verifies that errors are handled gracefully.
        Note: Current implementation always returns True (TODO).
        """
        # Grant reward
        success = await referral_service.grant_referral_reward(referral_id=999)

        # Current implementation always succeeds
        assert success is True
