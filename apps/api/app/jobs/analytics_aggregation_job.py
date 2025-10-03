"""
Background job for aggregating analytics events.

This module handles scheduled analytics aggregation using APScheduler.

@module analytics_aggregation_job
@since 1.0.0
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class AnalyticsAggregationJob:
    """
    Background job for daily analytics event aggregation.

    Runs on a scheduled basis to aggregate and summarize analytics events
    for reporting and performance optimization.

    @class AnalyticsAggregationJob
    @since 1.0.0
    """

    def __init__(self):
        """Initialize analytics aggregation job."""
        self.is_running = False

    async def run_daily_aggregation(self) -> None:
        """
        Execute daily analytics aggregation job.

        Aggregates analytics events from the previous day, summarizes
        event counts by type, and logs aggregation results.

        @throws DatabaseError - If database connection fails

        @performance
        - Execution time: ~1-5 minutes depending on event volume
        - Database queries: Multiple aggregation queries
        - Optimized with bulk operations

        @since 1.0.0
        """
        if self.is_running:
            logger.warning("Analytics aggregation job already running, skipping")
            return

        self.is_running = True
        start_time = datetime.utcnow()

        logger.info("Starting daily analytics aggregation job")

        try:
            # Get database session
            async for db in get_db():
                from app.db.models import AnalyticsEvent

                # Define time range for yesterday's events
                yesterday = datetime.utcnow() - timedelta(days=1)
                start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

                logger.info(f"Aggregating events from {start_of_day} to {end_of_day}")

                # Get total event count
                total_count_stmt = select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.timestamp.between(start_of_day, end_of_day)
                )
                total_result = await db.execute(total_count_stmt)
                total_events = total_result.scalar() or 0

                logger.info(f"Total events to aggregate: {total_events}")

                # Aggregate events by type
                event_type_stmt = select(
                    AnalyticsEvent.event_name,
                    func.count(AnalyticsEvent.id).label('count')
                ).where(
                    AnalyticsEvent.timestamp.between(start_of_day, end_of_day)
                ).group_by(AnalyticsEvent.event_name).order_by(func.count(AnalyticsEvent.id).desc())

                event_type_result = await db.execute(event_type_stmt)
                event_types = event_type_result.all()

                # Log aggregation results by event type
                event_summary: Dict[str, int] = {}
                for event_name, count in event_types:
                    event_summary[event_name] = count
                    logger.info(f"  {event_name}: {count} events")

                # Aggregate unique users
                unique_users_stmt = select(
                    func.count(func.distinct(AnalyticsEvent.user_id))
                ).where(
                    AnalyticsEvent.timestamp.between(start_of_day, end_of_day),
                    AnalyticsEvent.user_id.isnot(None)
                )
                unique_users_result = await db.execute(unique_users_stmt)
                unique_users = unique_users_result.scalar() or 0

                logger.info(f"Unique active users: {unique_users}")

                # Calculate anonymous events
                anonymous_events_stmt = select(func.count(AnalyticsEvent.id)).where(
                    AnalyticsEvent.timestamp.between(start_of_day, end_of_day),
                    AnalyticsEvent.user_id.is_(None)
                )
                anonymous_result = await db.execute(anonymous_events_stmt)
                anonymous_events = anonymous_result.scalar() or 0

                logger.info(f"Anonymous events: {anonymous_events}")

                # Calculate top features
                top_features = list(event_summary.keys())[:5]
                logger.info(f"Top 5 features: {', '.join(top_features)}")

                # Log final summary
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Analytics aggregation completed in {duration:.2f}s: "
                    f"{total_events} events, {len(event_summary)} event types, "
                    f"{unique_users} unique users, {anonymous_events} anonymous events"
                )

                break  # Exit after first db session

        except Exception as e:
            logger.error(f"Analytics aggregation job failed: {str(e)}")
            raise

        finally:
            self.is_running = False


# Global job instance
analytics_aggregation_job = AnalyticsAggregationJob()


def schedule_analytics_aggregation(scheduler) -> None:
    """
    Schedule analytics aggregation job with APScheduler.

    @param scheduler - APScheduler instance
    @since 1.0.0
    """
    # Daily aggregation - Every day at midnight UTC
    scheduler.add_job(
        func=lambda: asyncio.create_task(analytics_aggregation_job.run_daily_aggregation()),
        trigger='cron',
        hour=0,
        minute=0,
        id='daily_analytics_aggregation',
        name='Daily Analytics Aggregation',
        replace_existing=True
    )

    logger.info("Analytics aggregation job scheduled successfully")
