"""
Background job for churn prediction and retention campaigns.

This module handles scheduled churn risk calculation and retention
interventions using APScheduler.

@module churn_prediction_job
@since 1.0.0
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.services.churn_prediction_service import ChurnPredictionService
from app.services.retention_campaign_service import RetentionCampaignService

logger = logging.getLogger(__name__)


class ChurnPredictionJob:
    """
    Background job for churn prediction and user engagement updates.

    Runs on a scheduled basis to update engagement metrics, calculate
    churn risk scores, and trigger retention campaigns for at-risk users.

    @class ChurnPredictionJob
    @since 1.0.0
    """

    def __init__(self):
        """Initialize churn prediction job."""
        self.is_running = False

    async def run_daily_update(self) -> None:
        """
        Execute daily churn prediction and engagement update job.

        Iterates through all active users to:
        1. Update engagement metrics
        2. Calculate churn risk scores
        3. Identify at-risk users (risk >= 60)
        4. Trigger retention campaigns for high-risk users

        @throws DatabaseError - If database connection fails

        @performance
        - Execution time: ~10-30 minutes for 1000 users
        - Database queries: 3-5 queries per user
        - Rate limiting: Processes users sequentially

        @since 1.0.0
        """
        if self.is_running:
            logger.warning("Churn prediction job already running, skipping")
            return

        self.is_running = True
        start_time = datetime.utcnow()

        logger.info("Starting daily churn prediction job")

        try:
            # Get database session
            async for db in get_db():
                from app.db.models import User

                churn_service = ChurnPredictionService(db)
                retention_service = RetentionCampaignService(db)

                # Get all active users
                stmt = select(User).where(User.is_active == True)
                result = await db.execute(stmt)
                users = result.scalars().all()

                logger.info(f"Processing engagement metrics for {len(users)} active users")

                # Track processing stats
                success_count = 0
                fail_count = 0
                at_risk_users: List[Dict[str, Any]] = []

                # Process each user
                for user in users:
                    try:
                        # Update engagement metrics and calculate churn risk
                        await churn_service.update_engagement_metrics(user.id)

                        # Get updated metrics to check risk score
                        from app.db.models import UserEngagementMetrics

                        metrics_stmt = select(UserEngagementMetrics).where(
                            UserEngagementMetrics.user_id == user.id
                        )
                        metrics_result = await db.execute(metrics_stmt)
                        metrics = metrics_result.scalar_one_or_none()

                        if metrics and metrics.churn_risk_score >= 60:
                            at_risk_users.append({
                                "user_id": user.id,
                                "email": user.email,
                                "full_name": user.full_name,
                                "churn_risk_score": metrics.churn_risk_score
                            })

                        success_count += 1

                        # Small delay to prevent database overload
                        await asyncio.sleep(0.05)  # 20 users per second

                    except Exception as e:
                        logger.error(f"Failed to update metrics for user {user.id}: {str(e)}")
                        fail_count += 1
                        continue

                # Log processing results
                logger.info(
                    f"Engagement metrics updated: {success_count} succeeded, {fail_count} failed"
                )
                logger.info(f"Identified {len(at_risk_users)} at-risk users (risk >= 60)")

                # Trigger retention campaigns for at-risk users
                if at_risk_users:
                    logger.info("Triggering retention campaigns for at-risk users")

                    campaign_success = 0
                    campaign_fail = 0

                    for at_risk_user in at_risk_users:
                        try:
                            user_id = at_risk_user["user_id"]
                            risk_score = at_risk_user["churn_risk_score"]

                            # Determine campaign type based on risk level
                            if risk_score >= 80:
                                campaign_type = "high_risk"
                            elif risk_score >= 60:
                                campaign_type = "medium_risk"
                            else:
                                continue  # Should not happen but safety check

                            # Send retention email
                            success = await retention_service.send_retention_email(
                                user_id=user_id,
                                campaign_type=campaign_type
                            )

                            if success:
                                campaign_success += 1
                                logger.info(
                                    f"Sent {campaign_type} retention email to user {user_id} "
                                    f"(risk: {risk_score:.1f})"
                                )
                            else:
                                campaign_fail += 1

                            # Rate limiting for email sending
                            await asyncio.sleep(0.2)  # 5 emails per second

                        except Exception as e:
                            logger.error(
                                f"Failed to send retention campaign for user {user_id}: {str(e)}"
                            )
                            campaign_fail += 1
                            continue

                    logger.info(
                        f"Retention campaigns sent: {campaign_success} succeeded, "
                        f"{campaign_fail} failed"
                    )

                # Log final summary
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Churn prediction job completed in {duration:.2f}s: "
                    f"{success_count} users processed, {len(at_risk_users)} at-risk, "
                    f"retention campaigns sent to {campaign_success} users"
                )

                break  # Exit after first db session

        except Exception as e:
            logger.error(f"Churn prediction job failed: {str(e)}")
            raise

        finally:
            self.is_running = False


# Global job instance
churn_prediction_job = ChurnPredictionJob()


def schedule_churn_prediction(scheduler) -> None:
    """
    Schedule churn prediction job with APScheduler.

    @param scheduler - APScheduler instance
    @since 1.0.0
    """
    # Daily churn prediction - Every day at 2:00 AM UTC
    scheduler.add_job(
        func=lambda: asyncio.create_task(churn_prediction_job.run_daily_update()),
        trigger='cron',
        hour=2,
        minute=0,
        id='daily_churn_prediction',
        name='Daily Churn Prediction',
        replace_existing=True
    )

    logger.info("Churn prediction job scheduled successfully")
