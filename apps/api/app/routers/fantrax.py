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

router = APIRouter(prefix="/fantrax", tags=["Fantrax Integration"])


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
    rosters: List[dict]


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

        return FantraxConnectionStatus(
            connected=True,
            connected_at=current_user.fantrax_connected_at.isoformat() if current_user.fantrax_connected_at else None,
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
            connected_at=current_user.fantrax_connected_at.isoformat() if current_user.fantrax_connected_at else None,
            leagues_count=len(leagues) if leagues else 0
        )
    except Exception as e:
        logger.error(f"Failed to check Fantrax status for user {current_user.id}: {str(e)}")
        return FantraxConnectionStatus(
            connected=True,  # Secret ID exists but might be invalid
            connected_at=current_user.fantrax_connected_at.isoformat() if current_user.fantrax_connected_at else None
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
        current_user.fantrax_secret_id = None
        current_user.fantrax_connected = False
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
    """
    secret_id = await get_fantrax_secret_id(db, current_user.id)

    if not secret_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fantrax account not connected. Please connect your account first."
        )

    try:
        fantrax_service = FantraxSecretAPIService(secret_id)
        leagues = await fantrax_service.get_leagues()

        if leagues is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch leagues from Fantrax"
            )

        return leagues

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch leagues for user {current_user.id}: {str(e)}")
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
