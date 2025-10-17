"""
API endpoints for watchlist management

@module WatchlistEndpoints
@version 1.0.0
@since 1.0.0
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.database import get_db
from app.api.deps import get_current_user
from app.db.models import User
from app.services.watchlist_service import WatchlistService
from app.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistUpdateNotesRequest,
    WatchlistToggleNotificationsRequest,
    WatchlistEntry
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    request: WatchlistAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add prospect to watchlist

    @param request - Watchlist add request
    @param current_user - Authenticated user
    @param db - Database session
    @returns Created watchlist entry

    @since 1.0.0
    """
    try:
        service = WatchlistService(db)
        result = await service.add_to_watchlist(
            user_id=current_user.id,
            prospect_id=request.prospect_id,
            notes=request.notes,
            notify_on_changes=request.notify_on_changes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add to watchlist"
        )


@router.get("/", response_model=List[WatchlistEntry])
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's watchlist

    @param current_user - Authenticated user
    @param db - Database session
    @returns List of watchlist entries

    @since 1.0.0
    """
    try:
        service = WatchlistService(db)
        return await service.get_user_watchlist(user_id=current_user.id)
    except Exception as e:
        logger.error(f"Error getting watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve watchlist"
        )


@router.delete("/{prospect_id}")
async def remove_from_watchlist(
    prospect_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove prospect from watchlist

    @param prospect_id - Prospect ID to remove
    @param current_user - Authenticated user
    @param db - Database session
    @returns Confirmation message

    @since 1.0.0
    """
    try:
        service = WatchlistService(db)
        return await service.remove_from_watchlist(
            user_id=current_user.id,
            prospect_id=prospect_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove from watchlist"
        )


@router.patch("/{prospect_id}/notes")
async def update_watchlist_notes(
    prospect_id: int,
    request: WatchlistUpdateNotesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update watchlist entry notes

    @param prospect_id - Prospect ID
    @param request - Notes update request
    @param current_user - Authenticated user
    @param db - Database session
    @returns Updated entry

    @since 1.0.0
    """
    try:
        service = WatchlistService(db)
        return await service.update_watchlist_notes(
            user_id=current_user.id,
            prospect_id=prospect_id,
            notes=request.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating notes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notes"
        )


@router.patch("/{prospect_id}/notifications")
async def toggle_notifications(
    prospect_id: int,
    request: WatchlistToggleNotificationsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle change notifications

    @param prospect_id - Prospect ID
    @param request - Toggle request
    @param current_user - Authenticated user
    @param db - Database session
    @returns Updated notification status

    @since 1.0.0
    """
    try:
        service = WatchlistService(db)
        return await service.toggle_notifications(
            user_id=current_user.id,
            prospect_id=prospect_id,
            enabled=request.enabled
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error toggling notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle notifications"
        )
