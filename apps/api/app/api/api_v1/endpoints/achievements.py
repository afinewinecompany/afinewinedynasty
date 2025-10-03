"""
API endpoints for achievement operations.

@module achievements
@since 1.0.0
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.achievements import (
    AchievementResponse,
    UserAchievementResponse,
    AchievementProgressResponse
)
from app.services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/achievements", response_model=List[AchievementResponse])
async def get_all_achievements(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all available achievements.

    Returns complete list of achievements that users can unlock,
    regardless of authentication status.

    @param db - Database session
    @returns List of all achievement definitions

    @since 1.0.0
    """
    try:
        achievement_service = AchievementService(db)
        achievements = await achievement_service.get_all_achievements()

        return achievements

    except Exception as e:
        logger.error(f"Error fetching achievements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch achievements"
        )


@router.get("/users/achievements")
async def get_user_achievements(
    include_locked: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's achievements.

    Retrieves all unlocked achievements for the authenticated user,
    optionally including locked achievements with progress.

    @param include_locked - Include locked achievements with progress
    @param current_user - Authenticated user from JWT token
    @param db - Database session
    @returns List of user achievements

    @throws HTTPException(500) - If database error occurs

    @since 1.0.0
    """
    try:
        achievement_service = AchievementService(db)
        achievements = await achievement_service.get_user_achievements(
            user_id=current_user.id,
            include_locked=include_locked
        )

        return {
            "achievements": achievements,
            "total": len(achievements)
        }

    except Exception as e:
        logger.error(f"Error fetching user achievements for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user achievements"
        )


@router.get("/users/achievements/progress", response_model=AchievementProgressResponse)
async def get_achievement_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's achievement progress summary.

    Provides aggregate statistics including total unlocked, points earned,
    and next available achievement.

    @param current_user - Authenticated user from JWT token
    @param db - Database session
    @returns Achievement progress summary

    @throws HTTPException(500) - If database error occurs

    @example
    Response:
    ```json
    {
      "total_count": 12,
      "unlocked_count": 5,
      "total_points": 750,
      "earned_points": 200,
      "progress_percentage": 41.7,
      "next_achievement": {...},
      "recent_unlocks": [...]
    }
    ```

    @since 1.0.0
    """
    try:
        achievement_service = AchievementService(db)
        progress = await achievement_service.get_achievement_progress(
            user_id=current_user.id
        )

        return progress

    except Exception as e:
        logger.error(f"Error fetching achievement progress for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch achievement progress"
        )


@router.post("/admin/achievements/seed")
async def seed_achievements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Seed achievements table with predefined achievements.

    Admin endpoint for populating the achievements table with
    all available achievements during initial setup.

    @param current_user - Authenticated admin user
    @param db - Database session
    @returns Success message

    @throws HTTPException(403) - If user not admin
    @throws HTTPException(500) - If seeding fails

    @since 1.0.0
    """
    # Check if user is admin
    if current_user.subscription_tier != "admin":  # Adjust based on your admin logic
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        achievement_service = AchievementService(db)
        await achievement_service.seed_achievements()

        return {
            "success": True,
            "message": "Achievements seeded successfully"
        }

    except Exception as e:
        logger.error(f"Error seeding achievements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed achievements"
        )
