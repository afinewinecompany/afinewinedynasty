"""API endpoints for referral operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.referrals import ReferralCodeResponse, ReferralStatsResponse
from app.services.referral_service import ReferralService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=ReferralCodeResponse)
async def generate_referral_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate or get existing referral code for user."""
    try:
        service = ReferralService(db)
        code = await service.get_or_create_referral_code(current_user.id)

        return {
            "id": 1,
            "user_id": current_user.id,
            "code": code,
            "uses_remaining": 10,
            "created_at": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Error generating referral code: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate referral code")


@router.get("/stats", response_model=ReferralStatsResponse)
async def get_referral_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get referral statistics for current user."""
    try:
        service = ReferralService(db)
        stats = await service.get_referral_stats(current_user.id)
        return stats
    except Exception as e:
        logger.error(f"Error fetching referral stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch referral stats")
