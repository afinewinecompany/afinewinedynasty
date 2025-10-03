"""
Achievement service for tracking and unlocking user achievements.

This service handles achievement definitions, unlock detection, progress tracking,
and notification triggers for the gamification system.

@module achievement_service
@since 1.0.0
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, insert
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


# Achievement definitions
ACHIEVEMENTS_CONFIG = [
    {
        "id": "first_login",
        "name": "Welcome Aboard",
        "description": "Complete your first login",
        "criteria": "user_login",
        "icon": "🎉",
        "points": 10,
        "threshold": 1
    },
    {
        "id": "watchlist_starter",
        "name": "Watchlist Starter",
        "description": "Add 5 prospects to your watchlist",
        "criteria": "watchlist_add",
        "icon": "⭐",
        "points": 25,
        "threshold": 5
    },
    {
        "id": "watchlist_master",
        "name": "Watchlist Master",
        "description": "Add 25 prospects to your watchlist",
        "criteria": "watchlist_add",
        "icon": "🌟",
        "points": 100,
        "threshold": 25
    },
    {
        "id": "comparison_explorer",
        "name": "Comparison Explorer",
        "description": "Complete 5 prospect comparisons",
        "criteria": "prospect_comparison",
        "icon": "🔍",
        "points": 30,
        "threshold": 5
    },
    {
        "id": "comparison_expert",
        "name": "Comparison Expert",
        "description": "Complete 25 prospect comparisons",
        "criteria": "prospect_comparison",
        "icon": "🔬",
        "points": 75,
        "threshold": 25
    },
    {
        "id": "search_novice",
        "name": "Search Novice",
        "description": "Perform 10 prospect searches",
        "criteria": "prospect_search",
        "icon": "🔎",
        "points": 20,
        "threshold": 10
    },
    {
        "id": "week_streak",
        "name": "Weekly Regular",
        "description": "Log in for 7 consecutive days",
        "criteria": "login_streak",
        "icon": "🔥",
        "points": 100,
        "threshold": 7
    },
    {
        "id": "premium_subscriber",
        "name": "Premium Member",
        "description": "Upgrade to premium subscription",
        "criteria": "premium_upgrade",
        "icon": "💎",
        "points": 50,
        "threshold": 1
    },
    {
        "id": "referral_champion",
        "name": "Referral Champion",
        "description": "Refer 5 friends who sign up",
        "criteria": "successful_referral",
        "icon": "🤝",
        "points": 150,
        "threshold": 5
    },
    {
        "id": "feedback_contributor",
        "name": "Feedback Contributor",
        "description": "Submit 3 pieces of feedback",
        "criteria": "feedback_submission",
        "icon": "💬",
        "points": 40,
        "threshold": 3
    },
    {
        "id": "dynasty_enthusiast",
        "name": "Dynasty Enthusiast",
        "description": "Earn 500 achievement points",
        "criteria": "total_points",
        "icon": "🏆",
        "points": 200,
        "threshold": 500
    },
    {
        "id": "early_adopter",
        "name": "Early Adopter",
        "description": "Join during beta period",
        "criteria": "early_signup",
        "icon": "🚀",
        "points": 75,
        "threshold": 1
    }
]


class AchievementService:
    """
    Manages achievement tracking and unlocking.

    Handles achievement definitions, progress tracking, unlock detection,
    and integration with analytics events for automatic unlocking.

    @class AchievementService
    @since 1.0.0
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize achievement service.

        @param db - Database session for querying achievement data
        """
        self.db = db

    async def get_all_achievements(self) -> List[Dict[str, Any]]:
        """
        Get all available achievements.

        Returns complete list of achievements that users can unlock.

        @returns List of achievement definitions

        @example
        ```python
        achievements = await service.get_all_achievements()
        print(f"Total achievements: {len(achievements)}")
        ```

        @since 1.0.0
        """
        # For now, return config directly
        # In production, this would query the achievements table
        return ACHIEVEMENTS_CONFIG

    async def get_user_achievements(
        self,
        user_id: int,
        include_locked: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get user's unlocked achievements.

        Retrieves all achievements the user has earned, optionally including
        locked achievements with progress information.

        @param user_id - User ID
        @param include_locked - Include locked achievements with progress
        @returns List of achievement objects with unlock timestamps

        @example
        ```python
        unlocked = await service.get_user_achievements(user_id=123)
        for achievement in unlocked:
            print(f"{achievement['name']}: {achievement['unlocked_at']}")
        ```

        @since 1.0.0
        """
        from app.db.models import UserAchievement, Achievement

        # Query unlocked achievements with join to get achievement details
        stmt = (
            select(UserAchievement, Achievement)
            .join(Achievement, UserAchievement.achievement_id == Achievement.id)
            .where(UserAchievement.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # Build map of unlocked achievements
        unlocked_criteria = {}
        for user_ach, ach in rows:
            unlocked_criteria[ach.criteria] = {
                "achievement_id": ach.id,
                "unlocked_at": user_ach.unlocked_at
            }

        achievements_list = []

        for config in ACHIEVEMENTS_CONFIG:
            criteria_id = config["id"]

            if criteria_id in unlocked_criteria:
                achievements_list.append({
                    **config,
                    "unlocked": True,
                    "unlocked_at": unlocked_criteria[criteria_id]["unlocked_at"],
                    "progress": 100
                })
            elif include_locked:
                # Calculate progress for locked achievements
                progress = await self._calculate_progress(user_id, config)
                achievements_list.append({
                    **config,
                    "unlocked": False,
                    "unlocked_at": None,
                    "progress": progress
                })

        logger.debug(f"Retrieved {len(achievements_list)} achievements for user {user_id}")
        return achievements_list

    async def _calculate_progress(
        self,
        user_id: int,
        achievement_config: Dict[str, Any]
    ) -> int:
        """
        Calculate progress percentage for an achievement.

        @param user_id - User ID
        @param achievement_config - Achievement configuration
        @returns Progress percentage (0-100)

        @since 1.0.0
        """
        try:
            criteria = achievement_config["criteria"]
            threshold = achievement_config.get("threshold", 1)

            # Query analytics events for progress
            from app.db.models import AnalyticsEvent

            stmt = select(func.count(AnalyticsEvent.id)).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.event_name == criteria
                )
            )

            result = await self.db.execute(stmt)
            count = result.scalar() or 0

            progress = min(100, int((count / threshold) * 100))
            return progress

        except Exception as e:
            logger.error(f"Failed to calculate progress for achievement {achievement_config.get('id')}: {str(e)}")
            return 0

    async def get_achievement_progress(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's overall achievement progress summary.

        Provides aggregate statistics about achievement completion including
        total unlocked, points earned, and next available achievement.

        @param user_id - User ID
        @returns Progress summary with statistics

        @example
        ```python
        progress = await service.get_achievement_progress(user_id=123)
        print(f"Unlocked: {progress['unlocked_count']}/{progress['total_count']}")
        print(f"Points: {progress['earned_points']}/{progress['total_points']}")
        ```

        @since 1.0.0
        """
        all_achievements = await self.get_user_achievements(
            user_id, include_locked=True
        )

        unlocked = [a for a in all_achievements if a.get("unlocked")]
        locked = [a for a in all_achievements if not a.get("unlocked")]

        total_points = sum(a["points"] for a in ACHIEVEMENTS_CONFIG)
        earned_points = sum(a["points"] for a in unlocked)

        # Find next achievement (closest to completion)
        next_achievement = None
        if locked:
            locked_sorted = sorted(locked, key=lambda a: a.get("progress", 0), reverse=True)
            next_achievement = locked_sorted[0] if locked_sorted else None

        # Recent unlocks (last 5)
        recent_unlocks = sorted(
            unlocked,
            key=lambda a: a.get("unlocked_at", datetime.min),
            reverse=True
        )[:5]

        return {
            "total_count": len(ACHIEVEMENTS_CONFIG),
            "unlocked_count": len(unlocked),
            "total_points": total_points,
            "earned_points": earned_points,
            "progress_percentage": (len(unlocked) / len(ACHIEVEMENTS_CONFIG) * 100) if ACHIEVEMENTS_CONFIG else 0,
            "next_achievement": next_achievement,
            "recent_unlocks": recent_unlocks
        }

    async def check_and_unlock_achievement(
        self,
        user_id: int,
        event_name: str,
        event_count: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Check if user qualifies for achievement unlock based on event.

        Automatically checks all relevant achievements for the given event
        and unlocks any that meet the threshold criteria.

        @param user_id - User ID
        @param event_name - Event name that triggered check (e.g., "watchlist_add")
        @param event_count - Current count of events (for threshold checking)
        @returns List of newly unlocked achievements

        @throws ValueError - If user not found
        @throws DatabaseError - If database operation fails

        @example
        ```python
        # After user adds to watchlist
        unlocked = await service.check_and_unlock_achievement(
            user_id=123,
            event_name="watchlist_add",
            event_count=5
        )
        if unlocked:
            print(f"Unlocked: {unlocked[0]['name']}")
        ```

        @since 1.0.0
        """
        newly_unlocked = []

        # Find matching achievements
        matching_achievements = [
            a for a in ACHIEVEMENTS_CONFIG
            if a["criteria"] == event_name
        ]

        for achievement_config in matching_achievements:
            threshold = achievement_config.get("threshold", 1)

            # Check if threshold met
            if event_count >= threshold:
                # Check if already unlocked
                is_unlocked = await self._is_achievement_unlocked(
                    user_id, achievement_config["id"]
                )

                if not is_unlocked:
                    # Unlock achievement
                    unlocked = await self.unlock_achievement(
                        user_id, achievement_config["id"]
                    )
                    if unlocked:
                        newly_unlocked.append({
                            **achievement_config,
                            "unlocked_at": datetime.utcnow()
                        })

        if newly_unlocked:
            logger.info(
                f"User {user_id} unlocked {len(newly_unlocked)} achievements "
                f"for event {event_name}"
            )

        return newly_unlocked

    async def _is_achievement_unlocked(
        self,
        user_id: int,
        achievement_id: str
    ) -> bool:
        """
        Check if user has already unlocked an achievement.

        @param user_id - User ID
        @param achievement_id - Achievement identifier
        @returns True if already unlocked

        @since 1.0.0
        """
        try:
            from app.db.models import UserAchievement, Achievement

            # First get the achievement database ID
            stmt = select(Achievement.id).where(Achievement.criteria == achievement_id)
            result = await self.db.execute(stmt)
            db_achievement_id = result.scalar_one_or_none()

            if not db_achievement_id:
                logger.debug(f"Achievement {achievement_id} not found in database")
                return False

            # Check if user has unlocked it
            stmt = select(UserAchievement).where(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.achievement_id == db_achievement_id
                )
            )

            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            return existing is not None

        except Exception as e:
            logger.error(f"Failed to check if achievement {achievement_id} unlocked for user {user_id}: {str(e)}")
            return False

    async def unlock_achievement(
        self,
        user_id: int,
        achievement_id: str
    ) -> bool:
        """
        Unlock an achievement for a user.

        Creates user_achievement record and triggers notification.

        @param user_id - User ID
        @param achievement_id - Achievement identifier
        @returns True if successfully unlocked

        @throws ValueError - If achievement not found
        @throws DatabaseError - If database operation fails

        @example
        ```python
        success = await service.unlock_achievement(
            user_id=123,
            achievement_id="first_login"
        )
        ```

        @since 1.0.0
        """
        try:
            from app.db.models import Achievement, UserAchievement

            # Get achievement database ID
            stmt = select(Achievement.id).where(Achievement.criteria == achievement_id)
            result = await self.db.execute(stmt)
            db_achievement_id = result.scalar_one_or_none()

            if not db_achievement_id:
                logger.warning(f"Achievement {achievement_id} not found in database")
                return False

            # Check if already unlocked to avoid duplicate
            stmt = select(UserAchievement).where(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.achievement_id == db_achievement_id
                )
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(f"Achievement {achievement_id} already unlocked for user {user_id}")
                return True

            # Insert user achievement record
            user_achievement = UserAchievement(
                user_id=user_id,
                achievement_id=db_achievement_id,
                unlocked_at=datetime.utcnow()
            )
            self.db.add(user_achievement)
            await self.db.commit()

            logger.info(f"User {user_id} unlocked achievement: {achievement_id}")

            # TODO: Trigger notification
            # await self._send_achievement_notification(user_id, achievement_id)

            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to unlock achievement {achievement_id} for user {user_id}: {str(e)}")
            return False

    async def seed_achievements(self) -> None:
        """
        Seed achievements table with predefined achievements.

        Should be run during initial database setup to populate
        the achievements table with all available achievements.

        @since 1.0.0
        """
        from app.db.models import Achievement

        try:
            for config in ACHIEVEMENTS_CONFIG:
                # Check if achievement already exists
                stmt = select(Achievement).where(Achievement.criteria == config["id"])
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                if not existing:
                    # Insert new achievement
                    new_achievement = Achievement(
                        name=config["name"],
                        description=config["description"],
                        criteria=config["id"],
                        icon=config["icon"],
                        points=config["points"]
                    )
                    self.db.add(new_achievement)

            await self.db.commit()
            logger.info(f"Seeded {len(ACHIEVEMENTS_CONFIG)} achievements")

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to seed achievements: {str(e)}")
            raise
