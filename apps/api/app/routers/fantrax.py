"""
Fantrax Integration API Endpoints

Handles Fantrax Official API integration using Secret ID authentication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.api.deps import get_current_user
from app.db.models import User
from app.services.fantrax_secret_api_service import (
    FantraxSecretAPIService,
    store_fantrax_secret_id,
    get_fantrax_secret_id
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Fantrax Integration"])


# Request/Response Models

class ConnectFantraxRequest(BaseModel):
    """Request to connect Fantrax account using Secret ID"""
    secret_id: str = Field(..., min_length=10, max_length=100, description="Fantrax User Secret ID from profile")


class FantraxConnectionStatus(BaseModel):
    """Fantrax connection status response"""
    connected: bool
    connected_at: Optional[str] = None
    leagues_count: Optional[int] = None


class FantraxLeagueResponse(BaseModel):
    """Fantrax league information"""
    league_id: str
    name: str
    sport: Optional[str] = None
    teams: List[dict]
    is_active: bool = False  # Whether user has selected this league
    my_team_id: Optional[str] = None  # User's team ID in this league
    my_team_name: Optional[str] = None  # User's team name in this league


class FantraxLeagueInfoResponse(BaseModel):
    """Detailed league information"""
    league_id: str
    name: str
    sport: Optional[str] = None
    teams: List[dict]
    matchups: List[dict]
    players: List[dict]
    settings: dict
    current_period: Optional[int] = None
    season: Optional[int] = None


class FantraxRosterResponse(BaseModel):
    """Team rosters response"""
    league_id: str
    period: Optional[int] = None
    rosters: dict  # Dictionary keyed by team ID


class FantraxStandingsResponse(BaseModel):
    """League standings response"""
    league_id: str
    standings: List[dict]


# API Endpoints

@router.post("/connect", response_model=FantraxConnectionStatus)
async def connect_fantrax(
    request: ConnectFantraxRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Connect Fantrax account using Secret ID

    Users can find their Secret ID on their Fantrax User Profile screen.
    """
    try:
        # Test the Secret ID by fetching leagues
        fantrax_service = FantraxSecretAPIService(request.secret_id)
        leagues = await fantrax_service.get_leagues()

        if leagues is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Secret ID or unable to fetch leagues. Please check your Secret ID."
            )

        # Store the Secret ID (encrypted)
        await store_fantrax_secret_id(db, current_user.id, request.secret_id)

        logger.info(f"User {current_user.id} connected Fantrax with {len(leagues)} leagues")

        # Refresh user to get updated fantrax_connected_at
        await db.refresh(current_user)

        return FantraxConnectionStatus(
            connected=True,
            connected_at=current_user.fantrax_connected_at.isoformat() if hasattr(current_user, 'fantrax_connected_at') and current_user.fantrax_connected_at else None,
            leagues_count=len(leagues)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect Fantrax for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect Fantrax account: {str(e)}"
        )


@router.get("/status", response_model=FantraxConnectionStatus)
async def get_fantrax_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current Fantrax connection status
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        return FantraxConnectionStatus(connected=False)

    # Optionally test the connection by fetching leagues
    try:
        fantrax_service = FantraxSecretAPIService(secret_id)
        leagues = await fantrax_service.get_leagues()

        return FantraxConnectionStatus(
            connected=True,
            connected_at=current_user.fantrax_connected_at.isoformat() if hasattr(current_user, 'fantrax_connected_at') and current_user.fantrax_connected_at else None,
            leagues_count=len(leagues) if leagues else 0
        )
    except Exception as e:
        logger.error(f"Failed to check Fantrax status for user {current_user.id}: {str(e)}")
        return FantraxConnectionStatus(
            connected=True,  # Secret ID exists but might be invalid
            connected_at=current_user.fantrax_connected_at.isoformat() if hasattr(current_user, 'fantrax_connected_at') and current_user.fantrax_connected_at else None
        )


@router.delete("/disconnect")
async def disconnect_fantrax(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect Fantrax account
    """
    try:
        from sqlalchemy import update

        # Update user to remove fantrax connection
        stmt = (
            update(User)
            .where(User.id == current_user.id)
            .values(
                fantrax_secret_id=None,
                fantrax_connected_at=None
            )
        )
        await db.execute(stmt)

        # Also delete any stored leagues for this user
        from app.db.models import FantraxLeague as FantraxLeagueModel
        from sqlalchemy import delete

        stmt = delete(FantraxLeagueModel).where(
            FantraxLeagueModel.user_id == current_user.id
        )
        await db.execute(stmt)

        await db.commit()

        logger.info(f"User {current_user.id} disconnected Fantrax")

        return {"message": "Fantrax account disconnected successfully"}

    except Exception as e:
        logger.error(f"Failed to disconnect Fantrax for user {current_user.id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect Fantrax account"
        )


@router.get("/leagues", response_model=List[FantraxLeagueResponse])
async def get_leagues(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all leagues for the connected Fantrax account

    Returns leagues from the database if available, otherwise fetches from Fantrax API.
    Includes is_active flag to indicate which leagues user has selected.
    """
    try:
        secret_id = await get_fantrax_secret_id(db, current_user.id)
    except Exception as e:
        logger.error(f"Failed to get secret ID for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve Fantrax credentials"
        )

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected. Please connect your account first."
        )

    try:
        from sqlalchemy import select
        from app.db.models import FantraxLeague as FantraxLeagueModel

        # Fetch leagues from Fantrax API
        fantrax_service = FantraxSecretAPIService(secret_id)
        api_leagues = await fantrax_service.get_leagues()

        if api_leagues is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch leagues from Fantrax"
            )

        # Get saved leagues from database to merge is_active status
        stmt = select(FantraxLeagueModel).where(
            FantraxLeagueModel.user_id == current_user.id
        )
        result = await db.execute(stmt)
        db_leagues = {league.league_id: league for league in result.scalars().all()}

        # Check if this is the first time we're fetching leagues (no leagues in DB)
        is_first_fetch = len(db_leagues) == 0

        # Merge data - add is_active from database
        merged_leagues = []
        for league in api_leagues:
            league_id = league.get('league_id')
            if not league_id:
                # This shouldn't happen with the updated service, but keep for safety
                logger.warning(f"League missing league_id: {league}")
                continue

            db_league = db_leagues.get(league_id)

            # Create properly structured response
            # Default to active=True on first fetch, otherwise use DB value
            # Extract my_team_id and my_team_name from db_league or from teams array
            my_team_id = None
            my_team_name = None

            if db_league:
                # Use values from database if available
                my_team_id = db_league.my_team_id
                my_team_name = db_league.my_team_name

                # If database values are NULL, update them from API response
                if not my_team_id and league.get('teams') and len(league.get('teams', [])) > 0:
                    first_team = league.get('teams')[0]
                    my_team_id = first_team.get('team_id')
                    my_team_name = first_team.get('team_name')

                    # Update the database league with the team info
                    if my_team_id:
                        db_league.my_team_id = my_team_id
                        db_league.my_team_name = my_team_name
                        logger.info(f"Auto-updated team ID for league {league_id}: {my_team_name}")
            elif league.get('teams') and len(league.get('teams', [])) > 0:
                # Fallback to first team from API response if not in DB yet
                first_team = league.get('teams')[0]
                my_team_id = first_team.get('team_id')
                my_team_name = first_team.get('team_name')

            league_data = FantraxLeagueResponse(
                league_id=league_id,
                name=league.get('name', 'Unknown League'),
                sport=league.get('sport', 'MLB'),
                teams=league.get('teams', []),
                is_active=True if is_first_fetch else (db_league.is_active if db_league else False),
                my_team_id=my_team_id,
                my_team_name=my_team_name
            )
            merged_leagues.append(league_data)

        # Commit any auto-updates to team IDs
        if not is_first_fetch:
            await db.commit()

        # If this is first fetch, save all leagues as active to database
        if is_first_fetch and merged_leagues:
            logger.info(f"First league fetch for user {current_user.id}, saving all {len(merged_leagues)} leagues as active")
            for league_data in merged_leagues:
                # Map sport to valid league_type (dynasty, keeper, redraft)
                # Default to 'dynasty' if sport is not mapped
                league_type = 'dynasty'  # Default for most fantasy baseball leagues

                # Extract user's team ID and name from the teams array
                # The Secret ID API returns only the user's teams in the league
                my_team_id = None
                my_team_name = None
                if league_data.teams and len(league_data.teams) > 0:
                    # Use the first team (usually there's only one team per user per league)
                    first_team = league_data.teams[0]
                    my_team_id = first_team.get('team_id')
                    my_team_name = first_team.get('team_name')

                new_league = FantraxLeagueModel(
                    user_id=current_user.id,
                    league_id=league_data.league_id,
                    league_name=league_data.name,
                    league_type=league_type,
                    my_team_id=my_team_id,
                    my_team_name=my_team_name,
                    is_active=True  # All active by default
                )
                db.add(new_league)
            await db.commit()

        logger.info(f"Returning {len(merged_leagues)} leagues for user {current_user.id}")
        return merged_leagues

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Failed to fetch leagues for user {current_user.id}: {str(e)}\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch leagues: {str(e)}"
        )


@router.get("/leagues/{league_id}", response_model=FantraxLeagueInfoResponse)
async def get_league_info(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific league
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected"
        )

    try:
        fantrax_service = FantraxSecretAPIService(secret_id)
        league_info = await fantrax_service.get_league_info(league_id)

        if league_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"League {league_id} not found"
            )

        return league_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch league info for user {current_user.id}, league {league_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch league info: {str(e)}"
        )


@router.get("/leagues/{league_id}/rosters", response_model=FantraxRosterResponse)
async def get_team_rosters(
    league_id: str,
    period: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get team rosters for a league

    Args:
        league_id: Fantrax League ID
        period: Optional lineup period (defaults to current/upcoming)
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected"
        )

    try:
        fantrax_service = FantraxSecretAPIService(secret_id)
        rosters = await fantrax_service.get_team_rosters(league_id, period)

        if rosters is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rosters not found for league {league_id}"
            )

        return rosters

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch rosters for user {current_user.id}, league {league_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch rosters: {str(e)}"
        )


@router.get("/leagues/{league_id}/standings", response_model=FantraxStandingsResponse)
async def get_standings(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get league standings
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected"
        )

    try:
        fantrax_service = FantraxSecretAPIService(secret_id)
        standings = await fantrax_service.get_standings(league_id)

        if standings is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Standings not found for league {league_id}"
            )

        return standings

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch standings for user {current_user.id}, league {league_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch standings: {str(e)}"
        )


@router.get("/leagues/{league_id}/draft-results")
async def get_draft_results(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get draft results for a league
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected"
        )

    try:
        fantrax_service = FantraxSecretAPIService(secret_id)
        draft_results = await fantrax_service.get_draft_results(league_id)

        if draft_results is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft results not found for league {league_id}"
            )

        return draft_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch draft results for user {current_user.id}, league {league_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch draft results: {str(e)}"
        )


class LeagueSelectionsRequest(BaseModel):
    """Request to update league selections"""
    league_ids: List[str] = Field(..., description="List of league IDs to mark as active/selected")


@router.post("/leagues/select")
async def update_league_selections(
    request: LeagueSelectionsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update which leagues are selected/active for the user

    This endpoint saves the user's selected leagues to the database.
    Only the leagues in the provided list will be marked as active (is_active=True),
    all other leagues for this user will be marked as inactive.

    Args:
        league_ids: List of Fantrax league IDs to mark as selected
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected"
        )

    try:
        from sqlalchemy import select, update
        from app.db.models import FantraxLeague as FantraxLeagueModel

        # First, fetch all leagues from Fantrax API to ensure we have latest data
        fantrax_service = FantraxSecretAPIService(secret_id)
        fantrax_leagues = await fantrax_service.get_leagues()

        if fantrax_leagues is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch leagues from Fantrax"
            )

        # Upsert leagues to database
        for league in fantrax_leagues:
            # Check if league already exists
            stmt = select(FantraxLeagueModel).where(
                FantraxLeagueModel.user_id == current_user.id,
                FantraxLeagueModel.league_id == league['league_id']
            )
            result = await db.execute(stmt)
            existing_league = result.scalar_one_or_none()

            is_active = league['league_id'] in request.league_ids

            # Extract user's team ID and name from the teams array
            my_team_id = None
            my_team_name = None
            teams = league.get('teams', [])
            if teams and len(teams) > 0:
                # Use the first team (usually there's only one team per user per league)
                first_team = teams[0]
                my_team_id = first_team.get('team_id')
                my_team_name = first_team.get('team_name')

            if existing_league:
                # Update existing league - keep existing league_type, just update name, team info and active status
                existing_league.league_name = league['name']
                existing_league.is_active = is_active
                # Update team info if available
                if my_team_id:
                    existing_league.my_team_id = my_team_id
                    existing_league.my_team_name = my_team_name
            else:
                # Create new league - default to 'dynasty' type
                new_league = FantraxLeagueModel(
                    user_id=current_user.id,
                    league_id=league['league_id'],
                    league_name=league['name'],
                    league_type='dynasty',  # Default to dynasty (valid values: dynasty, keeper, redraft)
                    my_team_id=my_team_id,
                    my_team_name=my_team_name,
                    is_active=is_active
                )
                db.add(new_league)

        await db.commit()

        # Get count of selected leagues
        stmt = select(FantraxLeagueModel).where(
            FantraxLeagueModel.user_id == current_user.id,
            FantraxLeagueModel.is_active == True
        )
        result = await db.execute(stmt)
        selected_count = len(result.scalars().all())

        logger.info(f"User {current_user.id} updated league selections: {selected_count} leagues selected")

        return {
            "success": True,
            "message": f"Successfully updated league selections",
            "selected_count": selected_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update league selections for user {current_user.id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update league selections: {str(e)}"
        )
