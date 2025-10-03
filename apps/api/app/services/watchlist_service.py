"""
Watchlist service for managing user prospect watchlists

This module provides functionality for users to track favorite prospects,
add notes, and receive notifications about changes.

@module WatchlistService
@version 1.0.0
@since 1.0.0
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models import Watchlist, Prospect, User
import logging

logger = logging.getLogger(__name__)


class WatchlistService:
    """
    Manages user prospect watchlists

    @class WatchlistService
    @since 1.0.0
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize WatchlistService

        @param db - AsyncSession database connection
        """
        self.db = db

    async def add_to_watchlist(
        self,
        user_id: int,
        prospect_id: int,
        notes: Optional[str] = None,
        notify_on_changes: bool = True
    ) -> Dict[str, Any]:
        """
        Add prospect to user's watchlist

        @param user_id - User ID
        @param prospect_id - Prospect ID to watch
        @param notes - Optional notes about the prospect
        @param notify_on_changes - Whether to notify on changes
        @returns Watchlist entry details

        @throws ValueError - If prospect already in watchlist or not found

        @since 1.0.0
        """
        try:
            # Check if already in watchlist
            existing = await self.db.execute(
                select(Watchlist).where(
                    Watchlist.user_id == user_id,
                    Watchlist.prospect_id == prospect_id
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Prospect already in watchlist")

            # Verify prospect exists
            prospect = await self.db.execute(
                select(Prospect).where(Prospect.id == prospect_id)
            )
            if not prospect.scalar_one_or_none():
                raise ValueError(f"Prospect {prospect_id} not found")

            # Create watchlist entry
            watchlist_entry = Watchlist(
                user_id=user_id,
                prospect_id=prospect_id,
                notes=notes,
                notify_on_changes=notify_on_changes,
                added_at=datetime.now()
            )

            self.db.add(watchlist_entry)
            await self.db.commit()
            await self.db.refresh(watchlist_entry)

            return {
                "id": watchlist_entry.id,
                "user_id": watchlist_entry.user_id,
                "prospect_id": watchlist_entry.prospect_id,
                "notes": watchlist_entry.notes,
                "added_at": watchlist_entry.added_at.isoformat(),
                "notify_on_changes": watchlist_entry.notify_on_changes
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error adding to watchlist: {str(e)}")
            await self.db.rollback()
            raise

    async def remove_from_watchlist(self, user_id: int, prospect_id: int) -> Dict[str, str]:
        """
        Remove prospect from watchlist

        @param user_id - User ID
        @param prospect_id - Prospect ID to remove
        @returns Confirmation message

        @throws ValueError - If entry not found

        @since 1.0.0
        """
        try:
            result = await self.db.execute(
                delete(Watchlist).where(
                    Watchlist.user_id == user_id,
                    Watchlist.prospect_id == prospect_id
                ).returning(Watchlist.id)
            )

            if not result.fetchone():
                raise ValueError("Watchlist entry not found")

            await self.db.commit()

            return {"message": "Prospect removed from watchlist"}

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error removing from watchlist: {str(e)}")
            await self.db.rollback()
            raise

    async def get_user_watchlist(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all prospects in user's watchlist

        @param user_id - User ID
        @returns List of watchlist entries with prospect details

        @performance
        - Typical response time: 50-100ms
        - Database queries: 1 join query with prospect data

        @since 1.0.0
        """
        try:
            result = await self.db.execute(
                select(Watchlist, Prospect)
                .join(Prospect, Watchlist.prospect_id == Prospect.id)
                .where(Watchlist.user_id == user_id)
                .order_by(Watchlist.added_at.desc())
            )

            watchlist_entries = []
            for watchlist, prospect in result:
                watchlist_entries.append({
                    "id": watchlist.id,
                    "prospect_id": prospect.id,
                    "prospect_name": prospect.name,
                    "prospect_position": prospect.position,
                    "prospect_organization": prospect.organization,
                    "notes": watchlist.notes,
                    "added_at": watchlist.added_at.isoformat(),
                    "notify_on_changes": watchlist.notify_on_changes
                })

            return watchlist_entries

        except Exception as e:
            logger.error(f"Error getting watchlist: {str(e)}")
            raise

    async def update_watchlist_notes(
        self,
        user_id: int,
        prospect_id: int,
        notes: str
    ) -> Dict[str, Any]:
        """
        Update notes for watchlist entry

        @param user_id - User ID
        @param prospect_id - Prospect ID
        @param notes - New notes content
        @returns Updated watchlist entry

        @throws ValueError - If entry not found

        @since 1.0.0
        """
        try:
            result = await self.db.execute(
                select(Watchlist).where(
                    Watchlist.user_id == user_id,
                    Watchlist.prospect_id == prospect_id
                )
            )

            watchlist_entry = result.scalar_one_or_none()
            if not watchlist_entry:
                raise ValueError("Watchlist entry not found")

            watchlist_entry.notes = notes
            await self.db.commit()
            await self.db.refresh(watchlist_entry)

            return {
                "id": watchlist_entry.id,
                "prospect_id": watchlist_entry.prospect_id,
                "notes": watchlist_entry.notes,
                "updated": True
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating watchlist notes: {str(e)}")
            await self.db.rollback()
            raise

    async def toggle_notifications(
        self,
        user_id: int,
        prospect_id: int,
        enabled: bool
    ) -> Dict[str, Any]:
        """
        Toggle notifications for watchlist entry

        @param user_id - User ID
        @param prospect_id - Prospect ID
        @param enabled - Enable or disable notifications
        @returns Updated watchlist entry

        @throws ValueError - If entry not found

        @since 1.0.0
        """
        try:
            result = await self.db.execute(
                select(Watchlist).where(
                    Watchlist.user_id == user_id,
                    Watchlist.prospect_id == prospect_id
                )
            )

            watchlist_entry = result.scalar_one_or_none()
            if not watchlist_entry:
                raise ValueError("Watchlist entry not found")

            watchlist_entry.notify_on_changes = enabled
            await self.db.commit()

            return {
                "prospect_id": watchlist_entry.prospect_id,
                "notify_on_changes": watchlist_entry.notify_on_changes
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error toggling notifications: {str(e)}")
            await self.db.rollback()
            raise
