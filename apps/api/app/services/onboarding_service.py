"""
@fileoverview Onboarding service for managing user onboarding state and progress

This module provides core functionality for tracking and managing the user onboarding
flow, including step progression, completion tracking, and skip/resume capabilities.

@module OnboardingService
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.models import User

import logging

logger = logging.getLogger(__name__)


class OnboardingService:
    """
    Manages user onboarding flow progression and state tracking

    Handles onboarding step progression, completion tracking, skip functionality,
    and resume capabilities for new users learning the platform features.

    @class OnboardingService
    @since 1.0.0

    @example
    ```python
    service = OnboardingService(db_session)
    await service.start_onboarding(user_id=123)
    await service.progress_step(user_id=123, step=1)
    await service.complete_onboarding(user_id=123)
    ```
    """

    # Onboarding step definitions
    ONBOARDING_STEPS = {
        0: "welcome",
        1: "feature_tour_rankings",
        2: "feature_tour_profiles",
        3: "feature_tour_comparisons",
        4: "subscription_selection",
        5: "fantrax_integration_optional"
    }

    TOTAL_STEPS = len(ONBOARDING_STEPS)

    def __init__(self, db: AsyncSession):
        """
        Initialize OnboardingService with database session

        @param db - SQLAlchemy async database session for user queries
        """
        self.db = db

    async def start_onboarding(self, user_id: int) -> Dict[str, Any]:
        """
        Start onboarding flow for a user

        Sets the onboarding_started_at timestamp and initializes step to 0.
        Safe to call multiple times - only sets timestamp on first call.

        @param user_id - ID of the user starting onboarding
        @returns Dictionary containing current onboarding status

        @throws ValueError - When user_id is invalid or user not found

        @example
        ```python
        status = await service.start_onboarding(user_id=123)
        print(status["current_step"])  # 0
        print(status["total_steps"])   # 6
        ```

        @since 1.0.0
        """
        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User with id {user_id} not found")

            # Only set started_at if not already set
            if user.onboarding_started_at is None:
                user.onboarding_started_at = datetime.now()
                user.onboarding_step = 0
                await self.db.commit()
                await self.db.refresh(user)

            return {
                "user_id": user_id,
                "current_step": user.onboarding_step,
                "current_step_name": self.ONBOARDING_STEPS[user.onboarding_step],
                "total_steps": self.TOTAL_STEPS,
                "is_completed": user.onboarding_completed,
                "progress_percentage": (user.onboarding_step / self.TOTAL_STEPS) * 100
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error starting onboarding for user {user_id}: {str(e)}")
            raise

    async def progress_step(self, user_id: int, step: int) -> Dict[str, Any]:
        """
        Progress user to specified onboarding step

        Updates the user's current onboarding step. Validates that the step
        number is within valid range.

        @param user_id - ID of the user
        @param step - Step number to progress to (0-indexed)
        @returns Dictionary containing updated onboarding status

        @throws ValueError - When step is out of range or user not found

        @example
        ```python
        status = await service.progress_step(user_id=123, step=2)
        print(status["current_step_name"])  # "feature_tour_profiles"
        ```

        @since 1.0.0
        """
        if step < 0 or step >= self.TOTAL_STEPS:
            raise ValueError(f"Invalid step {step}. Must be between 0 and {self.TOTAL_STEPS - 1}")

        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User with id {user_id} not found")

            # Update step
            user.onboarding_step = step
            await self.db.commit()
            await self.db.refresh(user)

            return {
                "user_id": user_id,
                "current_step": user.onboarding_step,
                "current_step_name": self.ONBOARDING_STEPS[user.onboarding_step],
                "total_steps": self.TOTAL_STEPS,
                "is_completed": user.onboarding_completed,
                "progress_percentage": (user.onboarding_step / self.TOTAL_STEPS) * 100
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error progressing onboarding step for user {user_id}: {str(e)}")
            await self.db.rollback()
            raise

    async def complete_onboarding(self, user_id: int) -> Dict[str, Any]:
        """
        Mark onboarding as completed for user

        Sets onboarding_completed flag to true and records completion timestamp.
        Also sets the step to the final step number.

        @param user_id - ID of the user completing onboarding
        @returns Dictionary containing final onboarding status

        @throws ValueError - When user not found

        @example
        ```python
        status = await service.complete_onboarding(user_id=123)
        print(status["is_completed"])  # True
        ```

        @since 1.0.0
        """
        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User with id {user_id} not found")

            # Mark as completed
            user.onboarding_completed = True
            user.onboarding_completed_at = datetime.now()
            user.onboarding_step = self.TOTAL_STEPS - 1
            await self.db.commit()

            return {
                "user_id": user_id,
                "is_completed": True,
                "completed_at": user.onboarding_completed_at.isoformat(),
                "message": "Onboarding completed successfully"
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error completing onboarding for user {user_id}: {str(e)}")
            await self.db.rollback()
            raise

    async def skip_onboarding(self, user_id: int) -> Dict[str, Any]:
        """
        Skip onboarding flow for user

        Marks onboarding as completed without requiring step progression.
        User can still access onboarding content later if needed.

        @param user_id - ID of the user skipping onboarding
        @returns Dictionary containing skip confirmation

        @example
        ```python
        status = await service.skip_onboarding(user_id=123)
        print(status["message"])  # "Onboarding completed successfully"
        ```

        @since 1.0.0
        """
        return await self.complete_onboarding(user_id)

    async def get_onboarding_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get current onboarding status for user

        Retrieves all onboarding-related data for the specified user including
        current step, completion status, and progress metrics.

        @param user_id - ID of the user
        @returns Dictionary containing comprehensive onboarding status

        @throws ValueError - When user not found

        @example
        ```python
        status = await service.get_onboarding_status(user_id=123)
        print(f"Step {status['current_step']} of {status['total_steps']}")
        ```

        @performance
        - Typical response time: 10-30ms (single database query)
        - Database queries: 1 indexed query on user_id

        @since 1.0.0
        """
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User with id {user_id} not found")

            return {
                "user_id": user_id,
                "current_step": user.onboarding_step,
                "current_step_name": self.ONBOARDING_STEPS.get(user.onboarding_step, "unknown"),
                "total_steps": self.TOTAL_STEPS,
                "is_completed": user.onboarding_completed,
                "progress_percentage": (user.onboarding_step / self.TOTAL_STEPS) * 100,
                "started_at": user.onboarding_started_at.isoformat() if user.onboarding_started_at else None,
                "completed_at": user.onboarding_completed_at.isoformat() if user.onboarding_completed_at else None
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error getting onboarding status for user {user_id}: {str(e)}")
            raise

    async def reset_onboarding(self, user_id: int) -> Dict[str, Any]:
        """
        Reset onboarding progress for user

        Clears all onboarding progress, allowing user to restart from beginning.
        Useful for users who want to review the onboarding content again.

        @param user_id - ID of the user
        @returns Dictionary containing reset confirmation

        @throws ValueError - When user not found

        @example
        ```python
        status = await service.reset_onboarding(user_id=123)
        print(status["current_step"])  # 0
        ```

        @since 1.0.0
        """
        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User with id {user_id} not found")

            # Reset onboarding
            user.onboarding_completed = False
            user.onboarding_step = 0
            user.onboarding_started_at = None
            user.onboarding_completed_at = None
            await self.db.commit()

            return {
                "user_id": user_id,
                "current_step": 0,
                "is_completed": False,
                "message": "Onboarding reset successfully"
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error resetting onboarding for user {user_id}: {str(e)}")
            await self.db.rollback()
            raise
