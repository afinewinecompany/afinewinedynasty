"""
Fantrax Integration Endpoints (Cookie-based Authentication)

API endpoints for connecting Fantrax leagues using cookie-based authentication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
import pickle
import tempfile

from app.db.database import get_async_session
from app.db.models import User
from app.api.deps import get_current_premium_user
from app.services.fantrax_integration_service import FantraxIntegrationService
from app.services.fantrax_cookie_service import FantraxCookieService
from app.schemas.fantrax import (
    FantraxConnectionResponse,
    FantraxLeagueInfo,
    FantraxRosterResponse,
    FantraxStandingsResponse,
    FantraxTransactionsResponse
)

router = APIRouter()


@router.post("/connect", response_model=FantraxConnectionResponse)
async def connect_fantrax_account(
    cookie_file: UploadFile = File(..., description="Fantrax cookie file"),
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Connect Fantrax account using cookie file

    **Premium users only**

    Upload a Fantrax cookie file to connect your account.

    To generate a cookie file:
    1. Run the cookie generation script (provided separately)
    2. Log in to Fantrax within 30 seconds
    3. Upload the generated .cookie file here

    @param cookie_file - Fantrax cookie file (.cookie)

    @returns Connection status

    @premium Required
    @security JWT Bearer token

    @since 1.0.0
    """
    # Validate file type
    if not cookie_file.filename.endswith('.cookie'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a .cookie file"
        )

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.cookie') as temp_file:
            content = await cookie_file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Validate cookie file
        try:
            with open(temp_path, "rb") as f:
                cookies = pickle.load(f)
                if not isinstance(cookies, list):
                    raise ValueError("Invalid cookie file format")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cookie file: {str(e)}"
            )

        # Store cookies in database
        success = await FantraxCookieService.store_user_cookies(
            db, current_user.id, temp_path
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to store Fantrax cookies"
            )

        return FantraxConnectionResponse(
            success=True,
            message="Successfully connected to Fantrax",
            connected_at=current_user.fantrax_connected_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect Fantrax account: {str(e)}"
        )


@router.delete("/disconnect")
async def disconnect_fantrax_account(
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Disconnect Fantrax account

    **Premium users only**

    Removes stored Fantrax cookies and disconnects all leagues.

    @returns Disconnect status

    @premium Required
    @security JWT Bearer token

    @since 1.0.0
    """
    success = await FantraxCookieService.clear_user_cookies(db, current_user.id)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to disconnect Fantrax account"
        )

    return {
        "success": True,
        "message": "Successfully disconnected from Fantrax"
    }


@router.post("/leagues/{league_id}/connect", response_model=FantraxLeagueInfo)
async def connect_league(
    league_id: str,
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Connect a specific Fantrax league

    **Premium users only**

    Connect to a Fantrax league using its league ID.
    You must have already connected your Fantrax account via cookie upload.

    @param league_id - Fantrax league ID (found in your league URL)

    @returns League information

    @premium Required
    @security JWT Bearer token

    @since 1.0.0
    """
    service = FantraxIntegrationService(db, current_user.id)
    result = await service.connect_league(league_id)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to connect league")
        )

    return result["league_info"]


@router.post("/leagues/{league_id}/teams/{team_id}/roster/sync", response_model=FantraxRosterResponse)
async def sync_team_roster(
    league_id: str,
    team_id: str,
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Sync roster data for a specific team

    **Premium users only**

    Fetches and synchronizes roster data from Fantrax for the specified team.

    @param league_id - Fantrax league ID
    @param team_id - Team ID within the league

    @returns Roster data with sync status

    @premium Required
    @security JWT Bearer token
    @performance 2-5 seconds for 40-player roster

    @since 1.0.0
    """
    service = FantraxIntegrationService(db, current_user.id)
    result = await service.sync_roster(league_id, team_id)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to sync roster")
        )

    return result


@router.get("/leagues/{league_id}/standings", response_model=FantraxStandingsResponse)
async def get_league_standings(
    league_id: str,
    week: Optional[int] = None,
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get league standings

    **Premium users only**

    Retrieve current or historical standings for the league.

    @param league_id - Fantrax league ID
    @param week - Optional week number (defaults to current week)

    @returns League standings

    @premium Required
    @security JWT Bearer token

    @since 1.0.0
    """
    service = FantraxIntegrationService(db, current_user.id)
    result = await service.get_standings(league_id, week)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to get standings")
        )

    return result


@router.get("/leagues/{league_id}/transactions", response_model=FantraxTransactionsResponse)
async def get_league_transactions(
    league_id: str,
    count: int = 100,
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get recent league transactions

    **Premium users only**

    Retrieve recent transactions (trades, adds, drops) from the league.

    @param league_id - Fantrax league ID
    @param count - Number of transactions to retrieve (default 100, max 500)

    @returns List of transactions

    @premium Required
    @security JWT Bearer token

    @since 1.0.0
    """
    if count > 500:
        raise HTTPException(
            status_code=400,
            detail="Maximum count is 500 transactions"
        )

    service = FantraxIntegrationService(db, current_user.id)
    result = await service.get_transactions(league_id, count)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to get transactions")
        )

    return result


@router.get("/leagues/{league_id}/trade-block")
async def get_trade_block(
    league_id: str,
    current_user: User = Depends(get_current_premium_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get trade block for league

    **Premium users only**

    Retrieve list of players currently on the trade block.

    @param league_id - Fantrax league ID

    @returns List of players on trade block

    @premium Required
    @security JWT Bearer token

    @since 1.0.0
    """
    service = FantraxIntegrationService(db, current_user.id)
    result = await service.get_trade_block(league_id)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Failed to get trade block")
        )

    return result
