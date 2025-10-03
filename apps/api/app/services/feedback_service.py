"""
Feedback service for collecting and categorizing user feedback.

@module feedback_service
@since 1.0.0
"""

from datetime import datetime
from typing import List, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class FeedbackService:
    """Manages user feedback collection and categorization."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_feedback(
        self,
        user_id: int,
        feedback_type: str,
        rating: int = None,
        message: str = None,
        feature_request: str = None
    ) -> Dict[str, Any]:
        """Submit user feedback."""
        try:
            from app.db.models import Feedback

            # Create feedback record
            feedback = Feedback(
                user_id=user_id,
                type=feedback_type,
                rating=rating,
                message=message,
                feature_request=feature_request,
                submitted_at=datetime.utcnow()
            )

            self.db.add(feedback)
            await self.db.commit()
            await self.db.refresh(feedback)

            logger.info(f"User {user_id} submitted {feedback_type} feedback (ID: {feedback.id})")

            return {
                "id": feedback.id,
                "user_id": feedback.user_id,
                "type": feedback.type,
                "rating": feedback.rating,
                "message": feedback.message,
                "feature_request": feedback.feature_request,
                "submitted_at": feedback.submitted_at
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to submit feedback for user {user_id}: {str(e)}")
            raise

    async def get_user_feedback(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all feedback submitted by user."""
        try:
            from app.db.models import Feedback

            # Query all feedback for user, ordered by most recent first
            stmt = select(Feedback).where(
                Feedback.user_id == user_id
            ).order_by(Feedback.submitted_at.desc())

            result = await self.db.execute(stmt)
            feedback_records = result.scalars().all()

            # Convert to dict format
            feedback_list = []
            for feedback in feedback_records:
                feedback_list.append({
                    "id": feedback.id,
                    "user_id": feedback.user_id,
                    "type": feedback.type,
                    "rating": feedback.rating,
                    "message": feedback.message,
                    "feature_request": feedback.feature_request,
                    "submitted_at": feedback.submitted_at
                })

            logger.debug(f"Retrieved {len(feedback_list)} feedback records for user {user_id}")
            return feedback_list

        except Exception as e:
            logger.error(f"Failed to get feedback for user {user_id}: {str(e)}")
            return []
