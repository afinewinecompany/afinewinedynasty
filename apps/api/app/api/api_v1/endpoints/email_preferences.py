"""
API endpoints for email preferences management.

@module email_preferences
@since 1.0.0
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.engagement import EmailPreferences
from app.schemas.email import (
    EmailPreferencesResponse,
    EmailPreferencesUpdate,
    UnsubscribeRequest
)
from app.services.email_digest_service import EmailDigestService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/email-preferences", response_model=EmailPreferencesResponse)
async def get_email_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's email preferences.

    Returns the user's email digest settings including frequency,
    enabled status, and custom preferences.

    @param current_user - Authenticated user from JWT token
    @param db - Database session
    @returns EmailPreferencesResponse object

    @throws HTTPException(404) - If preferences not found
    @throws HTTPException(500) - If database error occurs

    @since 1.0.0
    """
    try:
        # Query email preferences
        stmt = select(EmailPreferences).where(
            EmailPreferences.user_id == current_user.id
        )
        result = await db.execute(stmt)
        preferences = result.scalar_one_or_none()

        if not preferences:
            # Create default preferences if none exist
            from datetime import datetime

            new_prefs = EmailPreferences(
                user_id=current_user.id,
                digest_enabled=True,
                frequency="weekly",
                preferences={},
                last_sent=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # For now, return default values
            # TODO: Actually insert into database when using SQLAlchemy ORM models
            logger.info(f"Created default email preferences for user {current_user.id}")

            return EmailPreferencesResponse(
                id=0,
                user_id=current_user.id,
                digest_enabled=True,
                frequency="weekly",
                preferences={},
                last_sent=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

        return EmailPreferencesResponse.from_orm(preferences)

    except Exception as e:
        logger.error(f"Error fetching email preferences for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email preferences"
        )


@router.put("/email-preferences", response_model=EmailPreferencesResponse)
async def update_email_preferences(
    preferences_update: EmailPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's email preferences.

    Allows users to modify digest frequency, enable/disable digests,
    and customize preference settings.

    @param preferences_update - Updated preference values
    @param current_user - Authenticated user from JWT token
    @param db - Database session
    @returns Updated EmailPreferencesResponse object

    @throws HTTPException(400) - If invalid frequency value
    @throws HTTPException(404) - If preferences not found
    @throws HTTPException(500) - If database error occurs

    @since 1.0.0
    """
    try:
        # Validate frequency if provided
        valid_frequencies = ['daily', 'weekly', 'monthly']
        if preferences_update.frequency and preferences_update.frequency not in valid_frequencies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"
            )

        # Build update values
        update_values = {}
        if preferences_update.digest_enabled is not None:
            update_values['digest_enabled'] = preferences_update.digest_enabled
        if preferences_update.frequency is not None:
            update_values['frequency'] = preferences_update.frequency
        if preferences_update.preferences is not None:
            update_values['preferences'] = preferences_update.preferences

        if not update_values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update values provided"
            )

        # Update timestamp
        from datetime import datetime
        update_values['updated_at'] = datetime.utcnow()

        # Update preferences
        stmt = (
            update(EmailPreferences)
            .where(EmailPreferences.user_id == current_user.id)
            .values(**update_values)
            .returning(EmailPreferences)
        )

        result = await db.execute(stmt)
        updated_prefs = result.scalar_one_or_none()

        if not updated_prefs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email preferences not found"
            )

        await db.commit()

        logger.info(f"Updated email preferences for user {current_user.id}")

        return EmailPreferencesResponse.from_orm(updated_prefs)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating email preferences for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email preferences"
        )


@router.post("/unsubscribe")
async def unsubscribe_from_digest(
    unsubscribe_request: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Unsubscribe user from email digests via token.

    Processes unsubscribe requests from email links. Uses JWT token
    to identify user without requiring authentication.

    @param unsubscribe_request - Unsubscribe token from email link
    @param db - Database session
    @returns Success message

    @throws HTTPException(400) - If token invalid or expired
    @throws HTTPException(500) - If database error occurs

    @since 1.0.0
    """
    try:
        # Verify unsubscribe token
        digest_service = EmailDigestService(db)
        user_id = digest_service.verify_unsubscribe_token(unsubscribe_request.token)

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired unsubscribe token"
            )

        # Unsubscribe user
        success = await digest_service.unsubscribe_user(user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process unsubscribe request"
            )

        logger.info(f"User {user_id} unsubscribed via token")

        return {
            "success": True,
            "message": "You have been successfully unsubscribed from email digests"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing unsubscribe request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process unsubscribe request"
        )


@router.get("/preview-digest")
async def preview_email_digest(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Preview email digest content without sending.

    Generates and returns digest content for the current user,
    useful for testing and preview functionality in UI.

    @param current_user - Authenticated user from JWT token
    @param db - Database session
    @returns Digest content dictionary

    @throws HTTPException(404) - If user data not found
    @throws HTTPException(500) - If content generation fails

    @since 1.0.0
    """
    try:
        digest_service = EmailDigestService(db)

        content = await digest_service.generate_digest_content(current_user.id)

        if content is None:
            return {
                "message": "Email digests are disabled for your account",
                "content": None
            }

        return {
            "message": "Digest preview generated successfully",
            "content": content
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating digest preview for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate digest preview"
        )
