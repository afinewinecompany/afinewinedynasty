"""
Background job for generating and sending weekly email digests.

This module handles scheduled email digest generation using APScheduler.

@module email_digest_job
@since 1.0.0
"""

import asyncio
import logging
from datetime import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.email_digest_service import EmailDigestService

logger = logging.getLogger(__name__)


class EmailDigestJob:
    """
    Background job for weekly email digest generation.

    Runs on a scheduled basis to send personalized digest emails to users
    based on their email preferences.

    @class EmailDigestJob
    @since 1.0.0
    """

    def __init__(self):
        """Initialize email digest job."""
        self.is_running = False

    async def run_weekly_digest(self) -> None:
        """
        Execute weekly email digest job.

        Queries all users eligible for weekly digest, generates personalized
        content, and sends emails via EmailDigestService.

        @throws DatabaseError - If database connection fails
        @throws EmailProviderError - If bulk email sending fails

        @performance
        - Execution time: ~5-10 minutes for 1000 users
        - Database queries: 1 query per user + 1 initial query
        - Rate limiting: 10 emails per second max

        @since 1.0.0
        """
        if self.is_running:
            logger.warning("Weekly digest job already running, skipping")
            return

        self.is_running = True
        start_time = datetime.utcnow()

        logger.info("Starting weekly email digest job")

        try:
            # Get database session
            async for db in get_db():
                digest_service = EmailDigestService(db)

                # Get users who need weekly digest
                user_ids = await digest_service.get_users_for_digest(frequency="weekly")

                logger.info(f"Processing digests for {len(user_ids)} users")

                # Send digests with batch processing
                success_count = 0
                fail_count = 0

                for user_id in user_ids:
                    try:
                        success = await digest_service.send_digest(user_id)
                        if success:
                            success_count += 1
                        else:
                            fail_count += 1

                        # Rate limiting: small delay between emails
                        await asyncio.sleep(0.1)  # 10 emails per second

                    except Exception as e:
                        logger.error(f"Failed to send digest for user {user_id}: {str(e)}")
                        fail_count += 1
                        continue

                # Log results
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Weekly digest job completed in {duration:.2f}s: "
                    f"{success_count} sent, {fail_count} failed"
                )

                break  # Exit after first db session

        except Exception as e:
            logger.error(f"Weekly digest job failed: {str(e)}")
            raise

        finally:
            self.is_running = False

    async def run_daily_digest(self) -> None:
        """
        Execute daily email digest job.

        Similar to weekly digest but for users with daily frequency preference.

        @since 1.0.0
        """
        if self.is_running:
            logger.warning("Daily digest job already running, skipping")
            return

        self.is_running = True
        start_time = datetime.utcnow()

        logger.info("Starting daily email digest job")

        try:
            async for db in get_db():
                digest_service = EmailDigestService(db)

                user_ids = await digest_service.get_users_for_digest(frequency="daily")

                logger.info(f"Processing daily digests for {len(user_ids)} users")

                success_count = 0
                fail_count = 0

                for user_id in user_ids:
                    try:
                        success = await digest_service.send_digest(user_id)
                        if success:
                            success_count += 1
                        else:
                            fail_count += 1

                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"Failed to send daily digest for user {user_id}: {str(e)}")
                        fail_count += 1
                        continue

                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Daily digest job completed in {duration:.2f}s: "
                    f"{success_count} sent, {fail_count} failed"
                )

                break

        except Exception as e:
            logger.error(f"Daily digest job failed: {str(e)}")
            raise

        finally:
            self.is_running = False


# Global job instance
email_digest_job = EmailDigestJob()


def schedule_email_digests(scheduler) -> None:
    """
    Schedule email digest jobs with APScheduler.

    @param scheduler - APScheduler instance
    @since 1.0.0
    """
    # Weekly digest - Every Monday at 6:00 AM UTC
    scheduler.add_job(
        func=lambda: asyncio.create_task(email_digest_job.run_weekly_digest()),
        trigger='cron',
        day_of_week='mon',
        hour=6,
        minute=0,
        id='weekly_email_digest',
        name='Weekly Email Digest',
        replace_existing=True
    )

    # Daily digest - Every day at 7:00 AM UTC
    scheduler.add_job(
        func=lambda: asyncio.create_task(email_digest_job.run_daily_digest()),
        trigger='cron',
        hour=7,
        minute=0,
        id='daily_email_digest',
        name='Daily Email Digest',
        replace_existing=True
    )

    logger.info("Email digest jobs scheduled successfully")
