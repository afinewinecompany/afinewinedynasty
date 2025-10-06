"""API endpoints for user lineup management"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import UserLogin
from app.models.lineup import (
    UserLineupCreate,
    UserLineupUpdate,
    UserLineupResponse,
    UserLineupDetailResponse,
    UserLineupListResponse,
    LineupProspectCreate,
    LineupProspectUpdate,
    LineupProspectResponse,
    FantraxSyncRequest,
    FantraxSyncResponse,
    BulkAddProspectsRequest,
    BulkAddProspectsResponse
)
from app.services.lineup_service import LineupService

router = APIRouter()


@router.post(
    "/",
    response_model=UserLineupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lineup",
    description="Create a new prospect lineup for the authenticated user"
)
async def create_lineup(
    lineup_data: UserLineupCreate,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserLineupResponse:
    """Create a new lineup"""
    lineup = await LineupService.create_lineup(db, current_user.email, lineup_data)

    return UserLineupResponse(
        id=lineup.id,
        user_id=lineup.user_id,
        name=lineup.name,
        description=lineup.description,
        is_public=lineup.is_public,
        lineup_type=lineup.lineup_type,
        settings=lineup.settings,
        created_at=lineup.created_at,
        updated_at=lineup.updated_at,
        prospect_count=0
    )


@router.get(
    "/",
    response_model=UserLineupListResponse,
    summary="Get all user lineups",
    description="Get all lineups for the authenticated user with pagination"
)
async def get_user_lineups(
    skip: int = Query(0, ge=0, description="Number of lineups to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of lineups to return"),
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserLineupListResponse:
    """Get all lineups for the current user"""
    lineups, total = await LineupService.get_user_lineups(db, current_user.email, skip, limit)

    lineup_responses = [
        UserLineupResponse(
            id=lineup.id,
            user_id=lineup.user_id,
            name=lineup.name,
            description=lineup.description,
            is_public=lineup.is_public,
            lineup_type=lineup.lineup_type,
            settings=lineup.settings,
            created_at=lineup.created_at,
            updated_at=lineup.updated_at,
            prospect_count=getattr(lineup, 'prospect_count', 0)
        )
        for lineup in lineups
    ]

    return UserLineupListResponse(
        lineups=lineup_responses,
        total=total
    )


@router.get(
    "/{lineup_id}",
    response_model=UserLineupDetailResponse,
    summary="Get lineup by ID",
    description="Get a specific lineup with all prospects"
)
async def get_lineup(
    lineup_id: int,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserLineupDetailResponse:
    """Get a lineup by ID with full prospect details"""
    lineup = await LineupService.get_lineup_by_id(db, lineup_id, current_user.email, include_prospects=True)

    # Build prospect responses with details
    prospect_responses = []
    for lp in lineup.prospects:
        prospect_responses.append(LineupProspectResponse(
            id=lp.id,
            lineup_id=lp.lineup_id,
            prospect_id=lp.prospect_id,
            position=lp.position,
            rank=lp.rank,
            notes=lp.notes,
            added_at=lp.added_at,
            prospect_name=lp.prospect.name if lp.prospect else None,
            prospect_position=lp.prospect.position if lp.prospect else None,
            prospect_organization=lp.prospect.organization if lp.prospect else None,
            prospect_eta=lp.prospect.eta_year if lp.prospect else None
        ))

    return UserLineupDetailResponse(
        id=lineup.id,
        user_id=lineup.user_id,
        name=lineup.name,
        description=lineup.description,
        is_public=lineup.is_public,
        lineup_type=lineup.lineup_type,
        settings=lineup.settings,
        created_at=lineup.created_at,
        updated_at=lineup.updated_at,
        prospect_count=len(prospect_responses),
        prospects=prospect_responses
    )


@router.put(
    "/{lineup_id}",
    response_model=UserLineupResponse,
    summary="Update lineup",
    description="Update lineup metadata (name, description, settings)"
)
async def update_lineup(
    lineup_id: int,
    update_data: UserLineupUpdate,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserLineupResponse:
    """Update a lineup"""
    lineup = await LineupService.update_lineup(db, lineup_id, current_user.email, update_data)

    return UserLineupResponse(
        id=lineup.id,
        user_id=lineup.user_id,
        name=lineup.name,
        description=lineup.description,
        is_public=lineup.is_public,
        lineup_type=lineup.lineup_type,
        settings=lineup.settings,
        created_at=lineup.created_at,
        updated_at=lineup.updated_at
    )


@router.delete(
    "/{lineup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete lineup",
    description="Delete a lineup and all associated prospect entries"
)
async def delete_lineup(
    lineup_id: int,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a lineup"""
    await LineupService.delete_lineup(db, lineup_id, current_user.email)
    return None


# Prospect Management Endpoints

@router.post(
    "/{lineup_id}/prospects",
    response_model=LineupProspectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add prospect to lineup",
    description="Add a prospect to a lineup with optional position, rank, and notes"
)
async def add_prospect_to_lineup(
    lineup_id: int,
    prospect_data: LineupProspectCreate,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> LineupProspectResponse:
    """Add a prospect to a lineup"""
    lineup_prospect = await LineupService.add_prospect_to_lineup(
        db, lineup_id, current_user.email, prospect_data
    )

    # Load prospect details
    await db.refresh(lineup_prospect, ['prospect'])

    return LineupProspectResponse(
        id=lineup_prospect.id,
        lineup_id=lineup_prospect.lineup_id,
        prospect_id=lineup_prospect.prospect_id,
        position=lineup_prospect.position,
        rank=lineup_prospect.rank,
        notes=lineup_prospect.notes,
        added_at=lineup_prospect.added_at,
        prospect_name=lineup_prospect.prospect.name if lineup_prospect.prospect else None,
        prospect_position=lineup_prospect.prospect.position if lineup_prospect.prospect else None,
        prospect_organization=lineup_prospect.prospect.organization if lineup_prospect.prospect else None,
        prospect_eta=lineup_prospect.prospect.eta_year if lineup_prospect.prospect else None
    )


@router.put(
    "/{lineup_id}/prospects/{prospect_id}",
    response_model=LineupProspectResponse,
    summary="Update prospect in lineup",
    description="Update a prospect's position, rank, or notes in a lineup"
)
async def update_lineup_prospect(
    lineup_id: int,
    prospect_id: int,
    update_data: LineupProspectUpdate,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> LineupProspectResponse:
    """Update a prospect in a lineup"""
    lineup_prospect = await LineupService.update_lineup_prospect(
        db, lineup_id, prospect_id, current_user.email, update_data
    )

    # Load prospect details
    await db.refresh(lineup_prospect, ['prospect'])

    return LineupProspectResponse(
        id=lineup_prospect.id,
        lineup_id=lineup_prospect.lineup_id,
        prospect_id=lineup_prospect.prospect_id,
        position=lineup_prospect.position,
        rank=lineup_prospect.rank,
        notes=lineup_prospect.notes,
        added_at=lineup_prospect.added_at,
        prospect_name=lineup_prospect.prospect.name if lineup_prospect.prospect else None,
        prospect_position=lineup_prospect.prospect.position if lineup_prospect.prospect else None,
        prospect_organization=lineup_prospect.prospect.organization if lineup_prospect.prospect else None,
        prospect_eta=lineup_prospect.prospect.eta_year if lineup_prospect.prospect else None
    )


@router.delete(
    "/{lineup_id}/prospects/{prospect_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove prospect from lineup",
    description="Remove a prospect from a lineup"
)
async def remove_prospect_from_lineup(
    lineup_id: int,
    prospect_id: int,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a prospect from a lineup"""
    await LineupService.remove_prospect_from_lineup(
        db, lineup_id, prospect_id, current_user.email
    )
    return None


# Bulk Operations

@router.post(
    "/{lineup_id}/prospects/bulk",
    response_model=BulkAddProspectsResponse,
    summary="Bulk add prospects to lineup",
    description="Add multiple prospects to a lineup at once (max 100)"
)
async def bulk_add_prospects(
    lineup_id: int,
    bulk_request: BulkAddProspectsRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> BulkAddProspectsResponse:
    """Bulk add prospects to a lineup"""
    added_count = 0
    skipped_count = 0
    errors = []

    for prospect_id in bulk_request.prospect_ids:
        try:
            prospect_data = LineupProspectCreate(prospect_id=prospect_id)
            await LineupService.add_prospect_to_lineup(
                db, lineup_id, current_user.email, prospect_data
            )
            added_count += 1
        except HTTPException as e:
            if e.status_code == status.HTTP_400_BAD_REQUEST:
                # Already in lineup - skip
                skipped_count += 1
            else:
                errors.append(f"Prospect {prospect_id}: {e.detail}")
        except Exception as e:
            errors.append(f"Prospect {prospect_id}: {str(e)}")

    return BulkAddProspectsResponse(
        lineup_id=lineup_id,
        added_count=added_count,
        skipped_count=skipped_count,
        errors=errors
    )


# Fantrax Integration

@router.post(
    "/sync/fantrax",
    response_model=FantraxSyncResponse,
    summary="Sync Fantrax league to lineup",
    description="Create or update a lineup with players from a Fantrax league roster"
)
async def sync_fantrax_lineup(
    sync_request: FantraxSyncRequest,
    current_user: UserLogin = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FantraxSyncResponse:
    """Sync a Fantrax league to a lineup"""
    return await LineupService.sync_fantrax_lineup(
        db, current_user.email, sync_request
    )
