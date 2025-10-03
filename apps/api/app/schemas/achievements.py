"""
Pydantic schemas for achievement operations.

@module achievements
@since 1.0.0
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class AchievementBase(BaseModel):
    """
    Base schema for achievements.

    @since 1.0.0
    """
    name: str
    description: str
    criteria: str
    icon: str
    points: int = 10


class AchievementCreate(AchievementBase):
    """
    Schema for creating achievements.

    @since 1.0.0
    """
    pass


class AchievementResponse(AchievementBase):
    """
    Schema for achievement API response.

    @since 1.0.0
    """
    id: int

    class Config:
        from_attributes = True


class UserAchievementBase(BaseModel):
    """
    Base schema for user achievements.

    @since 1.0.0
    """
    achievement_id: int


class UserAchievementCreate(UserAchievementBase):
    """
    Schema for unlocking user achievement.

    @since 1.0.0
    """
    user_id: int


class UserAchievementResponse(BaseModel):
    """
    Schema for user achievement API response.

    @since 1.0.0
    """
    id: int
    user_id: int
    achievement_id: int
    unlocked_at: datetime
    achievement: Optional[AchievementResponse] = None

    class Config:
        from_attributes = True


class AchievementProgressResponse(BaseModel):
    """
    Schema for achievement progress summary.

    @since 1.0.0
    """
    total_achievements: int
    unlocked_count: int
    total_points: int
    earned_points: int
    progress_percentage: float
    next_achievement: Optional[AchievementResponse] = None
    recent_unlocks: List[UserAchievementResponse] = []


class UnlockAchievementRequest(BaseModel):
    """
    Schema for achievement unlock event.

    @since 1.0.0
    """
    user_id: int
    achievement_criteria: str
    event_data: Optional[Dict[str, Any]] = None
