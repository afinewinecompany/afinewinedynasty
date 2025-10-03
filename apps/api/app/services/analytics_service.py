"""
Analytics service for event tracking and aggregation.

@module analytics_service
@since 1.0.0
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from collections import deque

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Manages analytics event tracking and aggregation.

    Implements batching for performance optimization.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._event_buffer: deque = deque(maxlen=10)  # Buffer for batch writes

    async def track_event(
        self,
        user_id: Optional[int],
        event_name: str,
        event_data: Dict[str, Any] = None
    ) -> bool:
        """
        Track analytics event.

        @param user_id - User ID (optional for anonymous events)
        @param event_name - Event name
        @param event_data - Event metadata (no PII)
        @returns Success status
        """
        event = {
            "user_id": user_id,
            "event_name": event_name,
            "event_data": event_data or {},
            "timestamp": datetime.utcnow()
        }

        self._event_buffer.append(event)

        # Flush buffer if full
        if len(self._event_buffer) >= 10:
            await self._flush_events()

        logger.debug(f"Tracked event: {event_name} for user {user_id}")
        return True

    async def _flush_events(self) -> None:
        """Flush buffered events to database."""
        if not self._event_buffer:
            return

        events_to_write = list(self._event_buffer)
        self._event_buffer.clear()

        try:
            from app.db.models import AnalyticsEvent

            # Batch insert events
            for event in events_to_write:
                analytics_event = AnalyticsEvent(
                    user_id=event["user_id"],
                    event_name=event["event_name"],
                    event_data=event["event_data"],
                    timestamp=event["timestamp"]
                )
                self.db.add(analytics_event)

            await self.db.commit()
            logger.info(f"Flushed {len(events_to_write)} analytics events")

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to flush analytics events: {str(e)}")
            # Re-add events to buffer for retry
            for event in events_to_write:
                if len(self._event_buffer) < self._event_buffer.maxlen:
                    self._event_buffer.append(event)

    async def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get user activity timeline.

        @param user_id - User ID
        @param days - Number of days to retrieve
        @returns List of events
        """
        try:
            from app.db.models import AnalyticsEvent

            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Query events for user within date range
            stmt = select(AnalyticsEvent).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.timestamp >= cutoff_date
                )
            ).order_by(AnalyticsEvent.timestamp.desc())

            result = await self.db.execute(stmt)
            events = result.scalars().all()

            # Convert to dict format
            activity_list = []
            for event in events:
                activity_list.append({
                    "id": event.id,
                    "event_name": event.event_name,
                    "event_data": event.event_data or {},
                    "timestamp": event.timestamp
                })

            logger.debug(f"Retrieved {len(activity_list)} events for user {user_id}")
            return activity_list

        except Exception as e:
            logger.error(f"Failed to get user activity for user {user_id}: {str(e)}")
            return []

    async def get_feature_adoption_stats(self) -> Dict[str, int]:
        """Get feature adoption metrics."""
        try:
            from app.db.models import AnalyticsEvent

            # Define feature event mappings
            feature_events = {
                "watchlist_usage": ["watchlist_add", "watchlist_view", "watchlist_remove"],
                "comparison_usage": ["prospect_comparison", "comparison_view"],
                "search_usage": ["prospect_search", "advanced_search"]
            }

            stats = {}

            # Get counts for each feature category
            for feature_name, event_names in feature_events.items():
                stmt = select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.event_name.in_(event_names)
                )
                result = await self.db.execute(stmt)
                count = result.scalar() or 0
                stats[feature_name] = count

            logger.debug(f"Retrieved feature adoption stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get feature adoption stats: {str(e)}")
            return {
                "watchlist_usage": 0,
                "comparison_usage": 0,
                "search_usage": 0
            }
