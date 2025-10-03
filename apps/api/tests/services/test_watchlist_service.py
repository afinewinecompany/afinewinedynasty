"""
Test suite for WatchlistService

Tests watchlist operations including adding/removing prospects, updating notes,
toggling notifications, and retrieving watchlist entries.

@module test_watchlist_service
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.watchlist_service import WatchlistService
from app.db.models import Watchlist, Prospect, User


@pytest.fixture
def mock_db():
    """
    Create mock database session

    @returns Mock AsyncSession for testing
    """
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_prospect():
    """
    Create sample prospect for testing

    @returns Prospect instance
    """
    prospect = Prospect(
        id=1,
        name="John Doe",
        position="Forward",
        organization="Team A",
        birth_date=datetime(2000, 1, 1),
        height=72,
        weight=180,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    return prospect


@pytest.fixture
def sample_watchlist_entry():
    """
    Create sample watchlist entry for testing

    @returns Watchlist instance
    """
    entry = Watchlist(
        id=1,
        user_id=1,
        prospect_id=1,
        notes="Great potential",
        added_at=datetime.now(),
        notify_on_changes=True
    )
    return entry


class TestWatchlistService:
    """Test WatchlistService methods"""

    @pytest.mark.asyncio
    async def test_add_to_watchlist_success(self, mock_db, sample_prospect):
        """
        Test successfully adding a prospect to watchlist

        Verifies that prospect is added with correct attributes
        """
        # Setup - mock that prospect doesn't exist in watchlist
        mock_result_existing = AsyncMock()
        mock_result_existing.scalar_one_or_none.return_value = None

        # Mock that prospect exists
        mock_result_prospect = AsyncMock()
        mock_result_prospect.scalar_one_or_none.return_value = sample_prospect

        mock_db.execute.side_effect = [mock_result_existing, mock_result_prospect]

        service = WatchlistService(mock_db)

        # Execute
        result = await service.add_to_watchlist(
            user_id=1,
            prospect_id=1,
            notes="Great potential",
            notify_on_changes=True
        )

        # Assert
        assert result["user_id"] == 1
        assert result["prospect_id"] == 1
        assert result["notes"] == "Great potential"
        assert result["notify_on_changes"] is True
        assert "added_at" in result
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_add_to_watchlist_already_exists(self, mock_db, sample_watchlist_entry):
        """
        Test adding prospect that's already in watchlist

        Verifies that ValueError is raised for duplicate entry
        """
        # Setup - mock that prospect already exists in watchlist
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_watchlist_entry
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Prospect already in watchlist"):
            await service.add_to_watchlist(user_id=1, prospect_id=1)

    @pytest.mark.asyncio
    async def test_add_to_watchlist_prospect_not_found(self, mock_db):
        """
        Test adding non-existent prospect to watchlist

        Verifies that ValueError is raised when prospect doesn't exist
        """
        # Setup - mock no existing watchlist entry
        mock_result_existing = AsyncMock()
        mock_result_existing.scalar_one_or_none.return_value = None

        # Mock prospect doesn't exist
        mock_result_prospect = AsyncMock()
        mock_result_prospect.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_result_existing, mock_result_prospect]

        service = WatchlistService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Prospect 999 not found"):
            await service.add_to_watchlist(user_id=1, prospect_id=999)

    @pytest.mark.asyncio
    async def test_remove_from_watchlist_success(self, mock_db):
        """
        Test successfully removing a prospect from watchlist

        Verifies that prospect is removed and confirmation returned
        """
        # Setup - mock successful deletion
        mock_result = AsyncMock()
        mock_fetchone = MagicMock()
        mock_result.fetchone.return_value = mock_fetchone
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute
        result = await service.remove_from_watchlist(user_id=1, prospect_id=1)

        # Assert
        assert result["message"] == "Prospect removed from watchlist"
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_remove_from_watchlist_not_found(self, mock_db):
        """
        Test removing non-existent watchlist entry

        Verifies that ValueError is raised when entry doesn't exist
        """
        # Setup - mock no deletion (entry not found)
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Watchlist entry not found"):
            await service.remove_from_watchlist(user_id=1, prospect_id=999)

    @pytest.mark.asyncio
    async def test_get_user_watchlist_success(self, mock_db, sample_watchlist_entry, sample_prospect):
        """
        Test retrieving user's watchlist

        Verifies that all watchlist entries with prospect details are returned
        """
        # Setup - mock watchlist query result
        mock_result = AsyncMock()
        mock_result.__iter__ = lambda self: iter([(sample_watchlist_entry, sample_prospect)])
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute
        result = await service.get_user_watchlist(user_id=1)

        # Assert
        assert len(result) == 1
        assert result[0]["prospect_id"] == 1
        assert result[0]["prospect_name"] == "John Doe"
        assert result[0]["prospect_position"] == "Forward"
        assert result[0]["prospect_organization"] == "Team A"
        assert result[0]["notes"] == "Great potential"
        assert result[0]["notify_on_changes"] is True

    @pytest.mark.asyncio
    async def test_get_user_watchlist_empty(self, mock_db):
        """
        Test retrieving empty watchlist

        Verifies that empty list is returned when user has no watchlist entries
        """
        # Setup - mock empty result
        mock_result = AsyncMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute
        result = await service.get_user_watchlist(user_id=1)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_update_watchlist_notes_success(self, mock_db, sample_watchlist_entry):
        """
        Test updating notes for watchlist entry

        Verifies that notes are updated correctly
        """
        # Setup
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_watchlist_entry
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute
        result = await service.update_watchlist_notes(
            user_id=1,
            prospect_id=1,
            notes="Updated notes"
        )

        # Assert
        assert result["prospect_id"] == 1
        assert result["notes"] == "Updated notes"
        assert result["updated"] is True
        assert sample_watchlist_entry.notes == "Updated notes"
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_update_watchlist_notes_not_found(self, mock_db):
        """
        Test updating notes for non-existent watchlist entry

        Verifies that ValueError is raised when entry doesn't exist
        """
        # Setup
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Watchlist entry not found"):
            await service.update_watchlist_notes(
                user_id=1,
                prospect_id=999,
                notes="Test notes"
            )

    @pytest.mark.asyncio
    async def test_toggle_notifications_enable(self, mock_db, sample_watchlist_entry):
        """
        Test enabling notifications for watchlist entry

        Verifies that notifications can be enabled
        """
        # Setup
        sample_watchlist_entry.notify_on_changes = False
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_watchlist_entry
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute
        result = await service.toggle_notifications(
            user_id=1,
            prospect_id=1,
            enabled=True
        )

        # Assert
        assert result["prospect_id"] == 1
        assert result["notify_on_changes"] is True
        assert sample_watchlist_entry.notify_on_changes is True
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_toggle_notifications_disable(self, mock_db, sample_watchlist_entry):
        """
        Test disabling notifications for watchlist entry

        Verifies that notifications can be disabled
        """
        # Setup
        sample_watchlist_entry.notify_on_changes = True
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_watchlist_entry
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute
        result = await service.toggle_notifications(
            user_id=1,
            prospect_id=1,
            enabled=False
        )

        # Assert
        assert result["prospect_id"] == 1
        assert result["notify_on_changes"] is False
        assert sample_watchlist_entry.notify_on_changes is False
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_toggle_notifications_not_found(self, mock_db):
        """
        Test toggling notifications for non-existent watchlist entry

        Verifies that ValueError is raised when entry doesn't exist
        """
        # Setup
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = WatchlistService(mock_db)

        # Execute & Assert
        with pytest.raises(ValueError, match="Watchlist entry not found"):
            await service.toggle_notifications(
                user_id=1,
                prospect_id=999,
                enabled=True
            )

    @pytest.mark.asyncio
    async def test_add_to_watchlist_with_default_values(self, mock_db, sample_prospect):
        """
        Test adding prospect with default parameter values

        Verifies that default values are applied correctly
        """
        # Setup
        mock_result_existing = AsyncMock()
        mock_result_existing.scalar_one_or_none.return_value = None

        mock_result_prospect = AsyncMock()
        mock_result_prospect.scalar_one_or_none.return_value = sample_prospect

        mock_db.execute.side_effect = [mock_result_existing, mock_result_prospect]

        service = WatchlistService(mock_db)

        # Execute - use defaults (notes=None, notify_on_changes=True)
        result = await service.add_to_watchlist(user_id=1, prospect_id=1)

        # Assert
        assert result["notes"] is None
        assert result["notify_on_changes"] is True
