"""
@fileoverview API endpoints for user onboarding flow management

Provides REST API endpoints for tracking and managing user onboarding progress,
including step progression, completion, skip, and reset functionality.

@module OnboardingEndpoints
@version 1.0.0
@author A Fine Wine Dynasty Team
@since 1.0.0
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import UserLogin
from app.services.onboarding_service import OnboardingService
from app.schemas.onboarding import (
    OnboardingStatus,
    OnboardingProgressRequest,
    OnboardingCompletionResponse,
    OnboardingResetResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=OnboardingStatus, status_code=status.HTTP_200_OK)
async def start_onboarding(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OnboardingStatus:
    """
    Start onboarding flow for current user

    Initializes onboarding tracking for the authenticated user. Safe to call
    multiple times - only sets start timestamp on first call.

    @param current_user - Authenticated user from JWT token
    @param db - Database session dependency
    @returns OnboardingStatus with current progress

    @throws HTTPException 404 - User not found
    @throws HTTPException 500 - Server error during onboarding start

    @example
    ```bash
    curl -X POST http://localhost:8000/api/v1/onboarding/start \
      -H "Authorization: Bearer <token>"
    ```

    @since 1.0.0
    """
    try:
        service = OnboardingService(db)
        status_data = await service.start_onboarding(user_id=current_user.id)
        return OnboardingStatus(**status_data)
    except ValueError as e:
        logger.error(f"User not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start onboarding"
        )


@router.get("/status", response_model=OnboardingStatus, status_code=status.HTTP_200_OK)
async def get_onboarding_status(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OnboardingStatus:
    """
    Get current onboarding status for authenticated user

    Retrieves comprehensive onboarding progress including current step,
    completion status, and progress metrics.

    @param current_user - Authenticated user from JWT token
    @param db - Database session dependency
    @returns OnboardingStatus with complete progress information

    @throws HTTPException 404 - User not found
    @throws HTTPException 500 - Server error during status retrieval

    @performance
    - Typical response time: 10-30ms
    - Database queries: 1 indexed query

    @example
    ```bash
    curl http://localhost:8000/api/v1/onboarding/status \
      -H "Authorization: Bearer <token>"
    ```

    @since 1.0.0
    """
    try:
        service = OnboardingService(db)
        status_data = await service.get_onboarding_status(user_id=current_user.id)
        return OnboardingStatus(**status_data)
    except ValueError as e:
        logger.error(f"User not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting onboarding status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get onboarding status"
        )


@router.post("/progress", response_model=OnboardingStatus, status_code=status.HTTP_200_OK)
async def progress_onboarding(
    request: OnboardingProgressRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OnboardingStatus:
    """
    Progress user to specified onboarding step

    Updates the authenticated user's onboarding progress to the specified step.
    Validates that the step number is within valid range.

    @param request - Request containing step number to progress to
    @param current_user - Authenticated user from JWT token
    @param db - Database session dependency
    @returns OnboardingStatus with updated progress

    @throws HTTPException 400 - Invalid step number
    @throws HTTPException 404 - User not found
    @throws HTTPException 500 - Server error during progress update

    @example
    ```bash
    curl -X POST http://localhost:8000/api/v1/onboarding/progress \
      -H "Authorization: Bearer <token>" \
      -H "Content-Type: application/json" \
      -d '{"step": 3}'
    ```

    @since 1.0.0
    """
    try:
        service = OnboardingService(db)
        status_data = await service.progress_step(user_id=current_user.id, step=request.step)
        return OnboardingStatus(**status_data)
    except ValueError as e:
        logger.error(f"Invalid step or user not found: {str(e)}")
        # Determine if it's a step validation error or user not found
        if "Invalid step" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
    except Exception as e:
        logger.error(f"Error progressing onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to progress onboarding"
        )


@router.post("/complete", response_model=OnboardingCompletionResponse, status_code=status.HTTP_200_OK)
async def complete_onboarding(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OnboardingCompletionResponse:
    """
    Mark onboarding as completed for authenticated user

    Sets onboarding completion flag and records completion timestamp.
    User will no longer see onboarding prompts after completion.

    @param current_user - Authenticated user from JWT token
    @param db - Database session dependency
    @returns OnboardingCompletionResponse with completion confirmation

    @throws HTTPException 404 - User not found
    @throws HTTPException 500 - Server error during completion

    @example
    ```bash
    curl -X POST http://localhost:8000/api/v1/onboarding/complete \
      -H "Authorization: Bearer <token>"
    ```

    @since 1.0.0
    """
    try:
        service = OnboardingService(db)
        completion_data = await service.complete_onboarding(user_id=current_user.id)
        return OnboardingCompletionResponse(**completion_data)
    except ValueError as e:
        logger.error(f"User not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error completing onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete onboarding"
        )


@router.post("/skip", response_model=OnboardingCompletionResponse, status_code=status.HTTP_200_OK)
async def skip_onboarding(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OnboardingCompletionResponse:
    """
    Skip onboarding flow for authenticated user

    Marks onboarding as completed without requiring step progression.
    User can access onboarding content later if desired.

    @param current_user - Authenticated user from JWT token
    @param db - Database session dependency
    @returns OnboardingCompletionResponse with skip confirmation

    @throws HTTPException 404 - User not found
    @throws HTTPException 500 - Server error during skip

    @example
    ```bash
    curl -X POST http://localhost:8000/api/v1/onboarding/skip \
      -H "Authorization: Bearer <token>"
    ```

    @since 1.0.0
    """
    try:
        service = OnboardingService(db)
        skip_data = await service.skip_onboarding(user_id=current_user.id)
        return OnboardingCompletionResponse(**skip_data)
    except ValueError as e:
        logger.error(f"User not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error skipping onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip onboarding"
        )


@router.post("/reset", response_model=OnboardingResetResponse, status_code=status.HTTP_200_OK)
async def reset_onboarding(
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> OnboardingResetResponse:
    """
    Reset onboarding progress for authenticated user

    Clears all onboarding progress, allowing user to restart from beginning.
    Useful for users who want to review onboarding content again.

    @param current_user - Authenticated user from JWT token
    @param db - Database session dependency
    @returns OnboardingResetResponse with reset confirmation

    @throws HTTPException 404 - User not found
    @throws HTTPException 500 - Server error during reset

    @example
    ```bash
    curl -X POST http://localhost:8000/api/v1/onboarding/reset \
      -H "Authorization: Bearer <token>"
    ```

    @since 1.0.0
    """
    try:
        service = OnboardingService(db)
        reset_data = await service.reset_onboarding(user_id=current_user.id)
        return OnboardingResetResponse(**reset_data)
    except ValueError as e:
        logger.error(f"User not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error resetting onboarding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset onboarding"
        )
