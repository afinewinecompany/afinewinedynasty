"""API endpoints for analytics operations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.analytics import AnalyticsEventCreate
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/track")
async def track_analytics_event(
    event: AnalyticsEventCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Track analytics event."""
    try:
        service = AnalyticsService(db)
        user_id = current_user.id if current_user else None

        success = await service.track_event(
            user_id=user_id,
            event_name=event.event_name,
            event_data=event.event_data
        )

        return {"success": success}
    except Exception as e:
        logger.error(f"Error tracking event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track event")
