"""
Test suite for AnalyticsService.

@module test_analytics_service
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock
from app.services.analytics_service import AnalyticsService


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def analytics_service(mock_db):
    """Create AnalyticsService instance."""
    return AnalyticsService(mock_db)


class TestTrackEvent:
    """Test suite for track_event."""

    @pytest.mark.asyncio
    async def test_track_event_success(self, analytics_service):
        """Test successful event tracking."""
        success = await analytics_service.track_event(
            user_id=1,
            event_name="prospect_search",
            event_data={"query": "pitcher"}
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_track_event_anonymous(self, analytics_service):
        """Test tracking anonymous event without user_id."""
        success = await analytics_service.track_event(
            user_id=None,
            event_name="page_view",
            event_data={"page": "/prospects"}
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_track_event_buffers_events(self, analytics_service):
        """Test that events are buffered before flush."""
        for i in range(5):
            await analytics_service.track_event(
                user_id=1,
                event_name=f"test_event_{i}"
            )

        # Buffer should contain events
        assert len(analytics_service._event_buffer) == 5

    @pytest.mark.asyncio
    async def test_track_event_auto_flush_at_limit(self, analytics_service):
        """Test that buffer auto-flushes at 10 events."""
        for i in range(10):
            await analytics_service.track_event(
                user_id=1,
                event_name=f"test_event_{i}"
            )

        # Buffer should be cleared after flush
        assert len(analytics_service._event_buffer) == 0


class TestFlushEvents:
    """Test suite for _flush_events."""

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self, analytics_service):
        """Test flushing empty buffer doesn't error."""
        await analytics_service._flush_events()

        # Should complete without error
        assert len(analytics_service._event_buffer) == 0
