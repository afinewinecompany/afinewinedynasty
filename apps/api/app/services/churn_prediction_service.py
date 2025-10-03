"""
Churn prediction service for identifying at-risk users.

@module churn_prediction_service
@since 1.0.0
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

logger = logging.getLogger(__name__)


class ChurnPredictionService:
    """
    Manages churn risk scoring and retention interventions.

    Implements algorithm for calculating churn risk based on
    user engagement patterns.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_churn_risk(self, user_id: int) -> float:
        """
        Calculate churn risk score for user (0-100).

        Algorithm factors:
        - Days since last login (30% weight)
        - Login frequency in last 30 days (25% weight)
        - Unique features used (20% weight)
        - Email engagement (15% weight)
        - Watchlist activity (10% weight)

        @param user_id - User ID
        @returns Churn risk score (0-100, higher = more risk)
        """
        try:
            from app.db.models import UserEngagementMetrics, AnalyticsEvent, User

            # Query user engagement metrics
            stmt = select(UserEngagementMetrics).where(
                UserEngagementMetrics.user_id == user_id
            )
            result = await self.db.execute(stmt)
            metrics = result.scalar_one_or_none()

            # If no metrics exist, calculate from scratch
            if not metrics:
                # Get user last login
                stmt = select(User).where(User.id == user_id)
                result = await self.db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    logger.warning(f"User {user_id} not found")
                    return 50.0  # Default moderate risk

                # Calculate days since last login
                last_login = metrics.last_login if metrics else user.updated_at
                days_since_login = (datetime.utcnow() - last_login).days if last_login else 30

                # Count login events in last 30 days
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                stmt = select(func.count(AnalyticsEvent.id)).where(
                    and_(
                        AnalyticsEvent.user_id == user_id,
                        AnalyticsEvent.event_name == 'user_login',
                        AnalyticsEvent.timestamp >= cutoff_date
                    )
                )
                result = await self.db.execute(stmt)
                logins_last_30_days = result.scalar() or 0

                # Count unique features used
                stmt = select(func.count(func.distinct(AnalyticsEvent.event_name))).where(
                    and_(
                        AnalyticsEvent.user_id == user_id,
                        AnalyticsEvent.timestamp >= cutoff_date
                    )
                )
                result = await self.db.execute(stmt)
                features_used = result.scalar() or 0
            else:
                # Use cached metrics
                days_since_login = (datetime.utcnow() - metrics.last_login).days if metrics.last_login else 30
                logins_last_30_days = metrics.login_frequency
                features_used = int(metrics.feature_usage_score)

            # Calculate weighted score
            # Normalize each factor to 0-100 scale
            login_recency_score = min(100, (days_since_login / 30) * 100)  # 30+ days = max risk
            login_frequency_score = max(0, (1 - (logins_last_30_days / 30)) * 100)  # Less than 30 logins
            feature_usage_score = max(0, (1 - (features_used / 10)) * 100)  # Less than 10 unique features

            # Apply weights
            score = (
                (login_recency_score * 0.3) +
                (login_frequency_score * 0.25) +
                (feature_usage_score * 0.2)
            )

            churn_risk = min(100, max(0, score))

            logger.debug(f"User {user_id} churn risk: {churn_risk:.2f} (days: {days_since_login}, logins: {logins_last_30_days}, features: {features_used})")
            return churn_risk

        except Exception as e:
            logger.error(f"Failed to calculate churn risk for user {user_id}: {str(e)}")
            return 50.0  # Default moderate risk on error

    async def get_at_risk_users(
        self,
        risk_threshold: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get list of users at risk of churning.

        @param risk_threshold - Minimum risk score (0-100)
        @returns List of at-risk users with scores
        """
        try:
            from app.db.models import UserEngagementMetrics, User

            # Query users with high churn risk scores
            stmt = select(UserEngagementMetrics, User).join(
                User, UserEngagementMetrics.user_id == User.id
            ).where(
                UserEngagementMetrics.churn_risk_score >= risk_threshold
            ).order_by(UserEngagementMetrics.churn_risk_score.desc())

            result = await self.db.execute(stmt)
            rows = result.all()

            at_risk_users = []
            for metrics, user in rows:
                at_risk_users.append({
                    "user_id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "churn_risk_score": metrics.churn_risk_score,
                    "last_login": metrics.last_login,
                    "login_frequency": metrics.login_frequency,
                    "feature_usage_score": metrics.feature_usage_score
                })

            logger.info(f"Found {len(at_risk_users)} at-risk users with threshold {risk_threshold}")
            return at_risk_users

        except Exception as e:
            logger.error(f"Failed to get at-risk users: {str(e)}")
            return []

    async def update_engagement_metrics(self, user_id: int) -> None:
        """
        Update user engagement metrics table.

        Should be called periodically to keep metrics current.

        @param user_id - User ID
        """
        try:
            from app.db.models import UserEngagementMetrics, AnalyticsEvent, User

            # Get user info
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {user_id} not found")
                return

            # Calculate last login from analytics events
            stmt = select(AnalyticsEvent.timestamp).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.event_name == 'user_login'
                )
            ).order_by(AnalyticsEvent.timestamp.desc()).limit(1)
            result = await self.db.execute(stmt)
            last_login = result.scalar_one_or_none() or user.updated_at

            # Calculate login frequency (last 30 days)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            stmt = select(func.count(AnalyticsEvent.id)).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.event_name == 'user_login',
                    AnalyticsEvent.timestamp >= cutoff_date
                )
            )
            result = await self.db.execute(stmt)
            login_frequency = result.scalar() or 0

            # Calculate feature usage score (unique features used in last 30 days)
            stmt = select(func.count(func.distinct(AnalyticsEvent.event_name))).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.timestamp >= cutoff_date
                )
            )
            result = await self.db.execute(stmt)
            feature_usage_score = float(result.scalar() or 0)

            # Calculate churn risk score
            churn_risk_score = await self.calculate_churn_risk(user_id)

            # Check if metrics record exists
            stmt = select(UserEngagementMetrics).where(
                UserEngagementMetrics.user_id == user_id
            )
            result = await self.db.execute(stmt)
            metrics = result.scalar_one_or_none()

            if metrics:
                # Update existing record
                metrics.last_login = last_login
                metrics.login_frequency = login_frequency
                metrics.feature_usage_score = feature_usage_score
                metrics.churn_risk_score = churn_risk_score
                metrics.updated_at = datetime.utcnow()
            else:
                # Create new record
                metrics = UserEngagementMetrics(
                    user_id=user_id,
                    last_login=last_login,
                    login_frequency=login_frequency,
                    feature_usage_score=feature_usage_score,
                    churn_risk_score=churn_risk_score
                )
                self.db.add(metrics)

            await self.db.commit()
            logger.info(f"Updated engagement metrics for user {user_id}: risk={churn_risk_score:.2f}, logins={login_frequency}, features={feature_usage_score}")

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update engagement metrics for user {user_id}: {str(e)}")
