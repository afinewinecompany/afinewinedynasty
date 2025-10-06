"""Service layer for user lineup management"""
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import UserLineup, LineupProspect, Prospect, User, FantraxLeague, FantraxRoster
from app.models.lineup import (
    UserLineupCreate,
    UserLineupUpdate,
    LineupProspectCreate,
    LineupProspectUpdate,
    UserLineupResponse,
    UserLineupDetailResponse,
    LineupProspectResponse,
    FantraxSyncRequest,
    FantraxSyncResponse
)


class LineupService:
    """Service for managing user lineups"""

    @staticmethod
    async def create_lineup(
        db: AsyncSession,
        user_email: str,
        lineup_data: UserLineupCreate
    ) -> UserLineup:
        """Create a new lineup for a user"""
        # Get user ID from email
        stmt = select(User).where(User.email == user_email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Create lineup
        new_lineup = UserLineup(
            user_id=user.id,
            name=lineup_data.name,
            description=lineup_data.description,
            is_public=lineup_data.is_public,
            lineup_type=lineup_data.lineup_type,
            settings=lineup_data.settings or {}
        )

        db.add(new_lineup)
        await db.commit()
        await db.refresh(new_lineup)

        return new_lineup

    @staticmethod
    async def get_user_lineups(
        db: AsyncSession,
        user_email: str,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[UserLineup], int]:
        """Get all lineups for a user with pagination"""
        # Get user
        user_stmt = select(User).where(User.email == user_email)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get lineups with prospect count
        stmt = (
            select(UserLineup, func.count(LineupProspect.id).label('prospect_count'))
            .outerjoin(LineupProspect, UserLineup.id == LineupProspect.lineup_id)
            .where(UserLineup.user_id == user.id)
            .group_by(UserLineup.id)
            .order_by(UserLineup.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        # Get total count
        count_stmt = select(func.count(UserLineup.id)).where(UserLineup.user_id == user.id)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar()

        # Build response with prospect counts
        lineups = []
        for lineup, prospect_count in rows:
            lineup.prospect_count = prospect_count
            lineups.append(lineup)

        return lineups, total

    @staticmethod
    async def get_lineup_by_id(
        db: AsyncSession,
        lineup_id: int,
        user_email: str,
        include_prospects: bool = True
    ) -> Optional[UserLineup]:
        """Get a specific lineup by ID (with authorization check)"""
        # Get user
        user_stmt = select(User).where(User.email == user_email)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Build query with optional prospect loading
        if include_prospects:
            stmt = (
                select(UserLineup)
                .options(selectinload(UserLineup.prospects).selectinload(LineupProspect.prospect))
                .where(and_(UserLineup.id == lineup_id, UserLineup.user_id == user.id))
            )
        else:
            stmt = select(UserLineup).where(and_(UserLineup.id == lineup_id, UserLineup.user_id == user.id))

        result = await db.execute(stmt)
        lineup = result.scalar_one_or_none()

        if not lineup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lineup not found or you don't have permission to access it"
            )

        return lineup

    @staticmethod
    async def update_lineup(
        db: AsyncSession,
        lineup_id: int,
        user_email: str,
        update_data: UserLineupUpdate
    ) -> UserLineup:
        """Update a lineup"""
        lineup = await LineupService.get_lineup_by_id(db, lineup_id, user_email, include_prospects=False)

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(lineup, field, value)

        lineup.updated_at = datetime.now()

        await db.commit()
        await db.refresh(lineup)

        return lineup

    @staticmethod
    async def delete_lineup(
        db: AsyncSession,
        lineup_id: int,
        user_email: str
    ) -> bool:
        """Delete a lineup"""
        lineup = await LineupService.get_lineup_by_id(db, lineup_id, user_email, include_prospects=False)

        await db.delete(lineup)
        await db.commit()

        return True

    @staticmethod
    async def add_prospect_to_lineup(
        db: AsyncSession,
        lineup_id: int,
        user_email: str,
        prospect_data: LineupProspectCreate
    ) -> LineupProspect:
        """Add a prospect to a lineup"""
        # Verify lineup ownership
        lineup = await LineupService.get_lineup_by_id(db, lineup_id, user_email, include_prospects=False)

        # Verify prospect exists
        prospect_stmt = select(Prospect).where(Prospect.id == prospect_data.prospect_id)
        prospect_result = await db.execute(prospect_stmt)
        prospect = prospect_result.scalar_one_or_none()

        if not prospect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prospect not found"
            )

        # Check if prospect already in lineup
        existing_stmt = select(LineupProspect).where(
            and_(
                LineupProspect.lineup_id == lineup_id,
                LineupProspect.prospect_id == prospect_data.prospect_id
            )
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prospect already in lineup"
            )

        # Add prospect to lineup
        lineup_prospect = LineupProspect(
            lineup_id=lineup_id,
            prospect_id=prospect_data.prospect_id,
            position=prospect_data.position,
            rank=prospect_data.rank,
            notes=prospect_data.notes
        )

        db.add(lineup_prospect)
        await db.commit()
        await db.refresh(lineup_prospect)

        return lineup_prospect

    @staticmethod
    async def update_lineup_prospect(
        db: AsyncSession,
        lineup_id: int,
        prospect_id: int,
        user_email: str,
        update_data: LineupProspectUpdate
    ) -> LineupProspect:
        """Update a prospect's position, rank, or notes in a lineup"""
        # Verify lineup ownership
        await LineupService.get_lineup_by_id(db, lineup_id, user_email, include_prospects=False)

        # Get lineup prospect
        stmt = select(LineupProspect).where(
            and_(
                LineupProspect.lineup_id == lineup_id,
                LineupProspect.prospect_id == prospect_id
            )
        )
        result = await db.execute(stmt)
        lineup_prospect = result.scalar_one_or_none()

        if not lineup_prospect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prospect not found in lineup"
            )

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(lineup_prospect, field, value)

        await db.commit()
        await db.refresh(lineup_prospect)

        return lineup_prospect

    @staticmethod
    async def remove_prospect_from_lineup(
        db: AsyncSession,
        lineup_id: int,
        prospect_id: int,
        user_email: str
    ) -> bool:
        """Remove a prospect from a lineup"""
        # Verify lineup ownership
        await LineupService.get_lineup_by_id(db, lineup_id, user_email, include_prospects=False)

        # Get lineup prospect
        stmt = select(LineupProspect).where(
            and_(
                LineupProspect.lineup_id == lineup_id,
                LineupProspect.prospect_id == prospect_id
            )
        )
        result = await db.execute(stmt)
        lineup_prospect = result.scalar_one_or_none()

        if not lineup_prospect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prospect not found in lineup"
            )

        await db.delete(lineup_prospect)
        await db.commit()

        return True

    @staticmethod
    async def sync_fantrax_lineup(
        db: AsyncSession,
        user_email: str,
        sync_request: FantraxSyncRequest
    ) -> FantraxSyncResponse:
        """Sync a Fantrax league roster to a user lineup"""
        # Get user
        user_stmt = select(User).where(User.email == user_email)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get Fantrax league
        league_stmt = select(FantraxLeague).where(
            and_(
                FantraxLeague.id == sync_request.league_id,
                FantraxLeague.user_id == user.id
            )
        )
        league_result = await db.execute(league_stmt)
        league = league_result.scalar_one_or_none()

        if not league:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fantrax league not found or you don't have access"
            )

        # Create or update lineup
        lineup_name = sync_request.lineup_name or f"{league.league_name} - Fantrax Sync"

        # Check for existing sync lineup
        existing_lineup_stmt = select(UserLineup).where(
            and_(
                UserLineup.user_id == user.id,
                UserLineup.lineup_type == 'fantrax_sync',
                UserLineup.settings['fantrax_league_id'].astext == str(sync_request.league_id)
            )
        )
        existing_result = await db.execute(existing_lineup_stmt)
        lineup = existing_result.scalar_one_or_none()

        if not lineup:
            # Create new lineup
            lineup = UserLineup(
                user_id=user.id,
                name=lineup_name,
                description=f"Auto-synced from Fantrax league: {league.league_name}",
                lineup_type='fantrax_sync',
                is_public=False,
                settings={'fantrax_league_id': sync_request.league_id}
            )
            db.add(lineup)
            await db.flush()

        # Get Fantrax roster players
        roster_stmt = select(FantraxRoster).where(FantraxRoster.league_id == league.id)
        roster_result = await db.execute(roster_stmt)
        fantrax_players = roster_result.scalars().all()

        prospects_synced = 0
        # TODO: Match Fantrax players to prospects in the database
        # This requires implementing player name/ID matching logic
        # For now, returning a placeholder response

        await db.commit()

        return FantraxSyncResponse(
            lineup_id=lineup.id,
            lineup_name=lineup.name,
            prospects_synced=prospects_synced,
            success=True,
            message=f"Lineup synced with {len(fantrax_players)} Fantrax roster players (matching to prospects pending implementation)"
        )
