"""API endpoints for feedback operations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit user feedback."""
    try:
        service = FeedbackService(db)
        result = await service.submit_feedback(
            user_id=current_user.id,
            feedback_type=feedback.type,
            rating=feedback.rating,
            message=feedback.message,
            feature_request=feedback.feature_request
        )
        return result
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")
