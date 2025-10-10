"""
Fantrax integration API endpoints

Handles OAuth flow, roster sync, and personalized recommendations
for Fantrax league integration.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.db.database import get_db
from app.api.deps import get_current_user
from app.core.security import require_premium_tier
from app.models.user import User as UserModel
from app.services.fantrax_oauth_service import FantraxOAuthService
from app.services.fantrax_api_service import FantraxAPIService
from app.services.roster_analysis_service import RosterAnalysisService
from app.services.personalized_recommendation_service import PersonalizedRecommendationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# === Request/Response Models ===

class FantraxAuthResponse(BaseModel):
    """Response containing OAuth authorization URL"""
    authorization_url: str = Field(description="URL to redirect user for OAuth authorization")
    state: str = Field(description="State token for CSRF protection")

    class Config:
        json_schema_extra = {
            "example": {
                "authorization_url": "https://www.fantrax.com/oauth/authorize?client_id=...",
                "state": "abc123xyz789"
            }
        }


class FantraxCallbackRequest(BaseModel):
    """OAuth callback request from Fantrax"""
    code: str = Field(description="Authorization code from Fantrax")
    state: str = Field(description="State token for validation")

    class Config:
        json_schema_extra = {
            "example": {
                "code": "auth_code_from_fantrax",
                "state": "123:abc123xyz789"
            }
        }


class FantraxCallbackResponse(BaseModel):
    """Response after successful OAuth callback"""
    success: bool = Field(description="Whether connection was successful")
    message: str = Field(description="Success or error message")
    fantrax_user_id: Optional[str] = Field(None, description="Connected Fantrax user ID")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully connected to Fantrax",
                "fantrax_user_id": "fantrax_user_123"
            }
        }


class FantraxLeague(BaseModel):
    """Fantrax league information"""
    league_id: str = Field(description="Unique league identifier")
    league_name: str = Field(description="Name of the league")
    league_type: str = Field(description="Type of league (dynasty, keeper, redraft)")
    team_count: int = Field(description="Number of teams in league")
    roster_size: int = Field(description="Total roster size")
    scoring_type: str = Field(description="Scoring system type")
    is_active: bool = Field(description="Whether league is currently active")
    last_sync: Optional[datetime] = Field(None, description="Last roster sync timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "league_id": "league_123",
                "league_name": "Dynasty Baseball Champions",
                "league_type": "dynasty",
                "team_count": 12,
                "roster_size": 40,
                "scoring_type": "H2H Points",
                "is_active": True,
                "last_sync": "2025-01-02T12:00:00Z"
            }
        }


class RosterSyncRequest(BaseModel):
    """Request to sync roster for a league"""
    league_id: str = Field(description="League ID to sync roster for")
    force_refresh: bool = Field(False, description="Force refresh even if recently synced")

    class Config:
        json_schema_extra = {
            "example": {
                "league_id": "league_123",
                "force_refresh": False
            }
        }


class RosterSyncResponse(BaseModel):
    """Response after roster sync"""
    success: bool = Field(description="Whether sync was successful")
    players_synced: int = Field(description="Number of players synced")
    sync_time: datetime = Field(description="Timestamp of sync")
    message: str = Field(description="Success or error message")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "players_synced": 40,
                "sync_time": "2025-01-02T12:00:00Z",
                "message": "Successfully synced 40 players"
            }
        }


class TeamAnalysis(BaseModel):
    """Team needs analysis result"""
    league_id: str = Field(description="League ID analyzed")
    strengths: List[str] = Field(description="Team strength positions")
    weaknesses: List[str] = Field(description="Team weakness positions")
    future_holes: List[Dict[str, Any]] = Field(description="Projected future roster holes")
    roster_timeline: str = Field(description="Team timeline (rebuilding, competing, etc)")
    available_spots: int = Field(description="Available roster spots for prospects")
    recommendations_count: int = Field(description="Number of recommended prospects")

    class Config:
        json_schema_extra = {
            "example": {
                "league_id": "league_123",
                "strengths": ["SP", "1B", "OF"],
                "weaknesses": ["C", "SS", "RP"],
                "future_holes": [
                    {"position": "2B", "year": 2026, "severity": "high"},
                    {"position": "CF", "year": 2027, "severity": "medium"}
                ],
                "roster_timeline": "competing",
                "available_spots": 5,
                "recommendations_count": 15
            }
        }


class ProspectRecommendation(BaseModel):
    """Personalized prospect recommendation"""
    prospect_id: int = Field(description="Prospect ID")
    prospect_name: str = Field(description="Name of prospect")
    position: str = Field(description="Primary position")
    organization: str = Field(description="MLB organization")
    fit_score: float = Field(description="How well prospect fits team needs (0-100)")
    eta_year: int = Field(description="Expected MLB arrival year")
    recommendation_reason: str = Field(description="Why this prospect is recommended")
    trade_value: str = Field(description="Current trade value tier")

    class Config:
        json_schema_extra = {
            "example": {
                "prospect_id": 123,
                "prospect_name": "John Doe",
                "position": "SS",
                "organization": "NYY",
                "fit_score": 92.5,
                "eta_year": 2026,
                "recommendation_reason": "Fills future SS need, high upside, matches competing timeline",
                "trade_value": "High"
            }
        }


# === OAuth Flow Endpoints ===

@router.get("/auth", response_model=FantraxAuthResponse)
# @limiter.limit("10/minute")
async def get_fantrax_auth_url(
    request: Request,
    current_user: UserModel = Depends(get_current_user)
) -> FantraxAuthResponse:
    """
    Generate Fantrax OAuth authorization URL

    Initiates the OAuth flow for connecting user's Fantrax account.
    Returns the authorization URL to redirect the user to.

    @performance
    - Response time: <100ms
    - No external API calls

    @since 1.0.0
    """
    try:
        auth_url, state = FantraxOAuthService.generate_oauth_url(current_user.id)
        return FantraxAuthResponse(
            authorization_url=auth_url,
            state=state
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.post("/callback", response_model=FantraxCallbackResponse)
# @limiter.limit("5/minute")
async def handle_fantrax_callback(
    request: Request,
    callback: FantraxCallbackRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FantraxCallbackResponse:
    """
    Handle Fantrax OAuth callback

    Processes the OAuth callback from Fantrax, exchanges the authorization
    code for tokens, and stores them securely.

    @performance
    - Response time: 500-1500ms
    - External API call to Fantrax for token exchange

    @since 1.0.0
    """
    # Validate state token for CSRF protection
    if not await FantraxOAuthService.validate_state_token(callback.state, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state token"
        )

    # Exchange code for tokens
    token_response = await FantraxOAuthService.exchange_code_for_tokens(callback.code)
    if not token_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code"
        )

    # Get user info from Fantrax
    user_info = await FantraxOAuthService.get_user_info(token_response["access_token"])
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user information from Fantrax"
        )

    # Store tokens securely
    success = await FantraxOAuthService.store_tokens(
        db,
        current_user.id,
        user_info.get("user_id"),
        token_response["refresh_token"]
    )

    if success:
        return FantraxCallbackResponse(
            success=True,
            message="Successfully connected to Fantrax",
            fantrax_user_id=user_info.get("user_id")
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store connection information"
        )


@router.post("/disconnect")
# @limiter.limit("5/minute")
async def disconnect_fantrax(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Disconnect Fantrax integration

    Revokes Fantrax access and removes stored tokens.

    @performance
    - Response time: <200ms
    - Database update only

    @since 1.0.0
    """
    success = await FantraxOAuthService.revoke_access(db, current_user.id)

    if success:
        return {"success": True, "message": "Fantrax account disconnected"}
    else:
        return {"success": False, "message": "No Fantrax account connected"}


# === Data Sync Endpoints ===

@router.get("/leagues", response_model=List[FantraxLeague])
# @limiter.limit("20/minute")
# @require_premium_tier
async def get_user_leagues(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[FantraxLeague]:
    """
    Get user's Fantrax leagues

    Retrieves all leagues the user is part of on Fantrax.

    @performance
    - Response time: 200-500ms with caching
    - External API call to Fantrax (cached for 24 hours)

    @since 1.0.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Validate Fantrax connection
    if not await FantraxOAuthService.validate_connection(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fantrax account not connected"
        )

    # Get leagues from Fantrax API service
    api_service = FantraxAPIService(db, current_user.id)
    leagues = await api_service.get_user_leagues()

    return [
        FantraxLeague(
            league_id=league["league_id"],
            league_name=league["name"],
            league_type=league["type"],
            team_count=league["team_count"],
            roster_size=league["roster_size"],
            scoring_type=league["scoring_type"],
            is_active=league["is_active"],
            last_sync=league.get("last_sync")
        )
        for league in leagues
    ]


@router.post("/roster/sync", response_model=RosterSyncResponse)
# @limiter.limit("10/minute")
# @require_premium_tier
async def sync_roster(
    request: Request,
    sync_request: RosterSyncRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RosterSyncResponse:
    """
    Sync roster for a specific league

    Fetches and stores the current roster for the specified league.

    @performance
    - Response time: 2-5 seconds for typical 40-player roster
    - External API calls to Fantrax

    @since 1.0.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Validate Fantrax connection
    if not await FantraxOAuthService.validate_connection(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fantrax account not connected"
        )

    # Sync roster using API service
    api_service = FantraxAPIService(db, current_user.id)
    sync_result = await api_service.sync_roster(
        sync_request.league_id,
        force_refresh=sync_request.force_refresh
    )

    if sync_result["success"]:
        return RosterSyncResponse(
            success=True,
            players_synced=sync_result["players_count"],
            sync_time=datetime.utcnow(),
            message=f"Successfully synced {sync_result['players_count']} players"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sync_result.get("error", "Roster sync failed")
        )


@router.get("/roster/{league_id}")
# @limiter.limit("30/minute")
# @require_premium_tier
async def get_roster(
    league_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get cached roster for a league

    Returns the most recently synced roster data.

    @performance
    - Response time: <100ms (cached data)
    - No external API calls

    @since 1.0.0
    """
    # Premium tier check
    require_premium_tier(current_user)
    
    # Validate Fantrax connection
    if not await FantraxOAuthService.validate_connection(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fantrax account not connected"
        )

    # Get roster from API service
    api_service = FantraxAPIService(db, current_user.id)
    roster = await api_service.get_roster(league_id)

    if not roster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roster not found. Please sync first."
        )

    return roster


# === Analysis & Recommendations Endpoints ===

@router.get("/analysis/{league_id}", response_model=TeamAnalysis)
# @limiter.limit("20/minute")
# @require_premium_tier
async def get_team_analysis(
    league_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TeamAnalysis:
    """
    Get team needs analysis

    Analyzes the team roster to identify strengths, weaknesses,
    and future roster holes.

    @performance
    - Response time: 500-1000ms
    - Cached for 1 hour

    @since 1.0.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Validate Fantrax connection
    if not await FantraxOAuthService.validate_connection(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fantrax account not connected"
        )

    # Perform analysis
    analysis_service = RosterAnalysisService(db, current_user.id)
    analysis = await analysis_service.analyze_team(league_id)

    return TeamAnalysis(
        league_id=league_id,
        strengths=analysis["strengths"],
        weaknesses=analysis["weaknesses"],
        future_holes=analysis["future_holes"],
        roster_timeline=analysis["timeline"],
        available_spots=analysis["available_spots"],
        recommendations_count=analysis["recommendations_count"]
    )


@router.get("/recommendations/{league_id}", response_model=List[ProspectRecommendation])
# @limiter.limit("20/minute")
# @require_premium_tier
async def get_personalized_recommendations(
    league_id: str,
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations to return"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[ProspectRecommendation]:
    """
    Get personalized prospect recommendations

    Returns prospects that best fit the team's needs and timeline.

    @performance
    - Response time: 1-2 seconds
    - Cached for 30 minutes

    @since 1.0.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Validate Fantrax connection
    if not await FantraxOAuthService.validate_connection(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fantrax account not connected"
        )

    # Get recommendations
    recommendation_service = PersonalizedRecommendationService(db, current_user.id)
    recommendations = await recommendation_service.get_recommendations(
        league_id,
        limit=limit
    )

    return [
        ProspectRecommendation(
            prospect_id=rec["prospect_id"],
            prospect_name=rec["name"],
            position=rec["position"],
            organization=rec["organization"],
            fit_score=rec["fit_score"],
            eta_year=rec["eta_year"],
            recommendation_reason=rec["reason"],
            trade_value=rec["trade_value"]
        )
        for rec in recommendations
    ]


@router.post("/trade-analysis")
# @limiter.limit("10/minute")
# @require_premium_tier
async def analyze_trade(
    request: Request,
    trade_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze potential trade

    Evaluates a potential trade based on team needs and values.

    @performance
    - Response time: 1-2 seconds
    - Complex calculation with multiple data sources

    @since 1.0.0
    """
    # Premium tier check
    require_premium_tier(current_user)
    
    # Validate Fantrax connection
    if not await FantraxOAuthService.validate_connection(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fantrax account not connected"
        )

    # Perform trade analysis
    recommendation_service = PersonalizedRecommendationService(db, current_user.id)
    analysis = await recommendation_service.analyze_trade(trade_data)

    return analysis