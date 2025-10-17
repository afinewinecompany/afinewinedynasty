"""
Pydantic schemas for Fantrax integration

Defines request and response models for Fantrax API endpoints.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class FantraxLeagueBase(BaseModel):
    """Base schema for Fantrax league"""
    league_id: str = Field(..., description="Unique Fantrax league ID")
    league_name: str = Field(..., description="League name")
    league_type: str = Field(..., description="League type (dynasty, keeper, redraft)")

    @validator('league_type')
    def validate_league_type(cls, v):
        allowed = ['dynasty', 'keeper', 'redraft']
        if v not in allowed:
            raise ValueError(f'league_type must be one of {allowed}')
        return v


class FantraxLeagueCreate(FantraxLeagueBase):
    """Schema for creating a Fantrax league"""
    scoring_system: Optional[Dict[str, Any]] = None
    roster_settings: Optional[Dict[str, Any]] = None


class FantraxLeagueInDB(FantraxLeagueBase):
    """Schema for Fantrax league from database"""
    id: int
    user_id: int
    scoring_system: Optional[Dict[str, Any]] = None
    roster_settings: Optional[Dict[str, Any]] = None
    is_active: bool = True
    last_sync: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FantraxRosterPlayerBase(BaseModel):
    """Base schema for roster player"""
    player_id: str = Field(..., description="Fantrax player ID")
    player_name: str = Field(..., description="Player name")
    positions: Optional[List[str]] = Field(None, description="Eligible positions")
    team: str = Field(..., description="MLB team")
    status: str = Field(..., description="Player status")

    @validator('status')
    def validate_status(cls, v):
        allowed = ['active', 'injured', 'minors', 'suspended', 'il']
        if v not in allowed:
            raise ValueError(f'status must be one of {allowed}')
        return v


class FantraxRosterPlayerCreate(FantraxRosterPlayerBase):
    """Schema for creating roster player"""
    contract_years: Optional[int] = None
    contract_value: Optional[float] = None
    age: Optional[int] = None
    minor_league_eligible: bool = False


class FantraxRosterPlayerInDB(FantraxRosterPlayerBase):
    """Schema for roster player from database"""
    id: int
    league_id: int
    contract_years: Optional[int] = None
    contract_value: Optional[float] = None
    age: Optional[int] = None
    minor_league_eligible: bool = False
    synced_at: datetime

    class Config:
        from_attributes = True


class FantraxSyncHistoryBase(BaseModel):
    """Base schema for sync history"""
    sync_type: str = Field(..., description="Type of sync performed")
    players_synced: int = Field(0, description="Number of players synced")
    success: bool = Field(True, description="Whether sync was successful")

    @validator('sync_type')
    def validate_sync_type(cls, v):
        allowed = ['roster', 'settings', 'transactions', 'full']
        if v not in allowed:
            raise ValueError(f'sync_type must be one of {allowed}')
        return v


class FantraxSyncHistoryCreate(FantraxSyncHistoryBase):
    """Schema for creating sync history"""
    error_message: Optional[str] = None
    sync_duration_ms: Optional[int] = None


class FantraxSyncHistoryInDB(FantraxSyncHistoryBase):
    """Schema for sync history from database"""
    id: int
    league_id: int
    error_message: Optional[str] = None
    sync_duration_ms: Optional[int] = None
    synced_at: datetime

    class Config:
        from_attributes = True


# API Request/Response Schemas

class OAuthStateResponse(BaseModel):
    """Response for OAuth state generation"""
    authorization_url: str = Field(..., description="OAuth authorization URL")
    state: str = Field(..., description="State token for CSRF protection")


class OAuthCallbackRequest(BaseModel):
    """Request for OAuth callback"""
    code: str = Field(..., description="Authorization code from Fantrax")
    state: str = Field(..., description="State token from initial request")


class OAuthCallbackResponse(BaseModel):
    """Response after OAuth callback"""
    success: bool = Field(..., description="Whether connection was successful")
    message: str = Field(..., description="Status message")
    fantrax_user_id: Optional[str] = Field(None, description="Connected Fantrax user ID")


class LeagueListResponse(BaseModel):
    """Response for list of user's leagues"""
    leagues: List[FantraxLeagueInDB] = Field(..., description="List of user's Fantrax leagues")


class RosterSyncRequest(BaseModel):
    """Request to sync a roster"""
    league_id: str = Field(..., description="League ID to sync")
    force_refresh: bool = Field(False, description="Force refresh even if cached")


class RosterSyncResponse(BaseModel):
    """Response after roster sync"""
    success: bool = Field(..., description="Whether sync was successful")
    players_synced: int = Field(..., description="Number of players synced")
    sync_time: datetime = Field(..., description="Timestamp of sync")
    message: str = Field(..., description="Status message")


class TeamNeedsAnalysis(BaseModel):
    """Analysis of team needs"""
    league_id: str = Field(..., description="League ID")
    strengths: List[str] = Field(..., description="Strong positions")
    weaknesses: List[str] = Field(..., description="Weak positions")
    future_holes: List[Dict[str, Any]] = Field(..., description="Projected future needs")
    roster_timeline: str = Field(..., description="Team competitive timeline")
    available_spots: int = Field(..., description="Available roster spots")
    recommendations_count: int = Field(..., description="Number of matching prospects")


class ProspectRecommendation(BaseModel):
    """Personalized prospect recommendation"""
    prospect_id: int = Field(..., description="Prospect database ID")
    name: str = Field(..., description="Prospect name")
    position: str = Field(..., description="Primary position")
    organization: str = Field(..., description="MLB organization")
    eta_year: int = Field(..., description="Expected MLB arrival year")
    fit_score: float = Field(..., description="How well prospect fits team (0-100)")
    recommendation_reason: str = Field(..., description="Why this prospect is recommended")
    trade_value: str = Field(..., description="Trade value tier")


class ProspectRecommendationsResponse(BaseModel):
    """Response with prospect recommendations"""
    league_id: str = Field(..., description="League ID")
    recommendations: List[ProspectRecommendation] = Field(..., description="Recommended prospects")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="When recommendations were generated")


class TradeAnalysisRequest(BaseModel):
    """Request for trade analysis"""
    league_id: str = Field(..., description="League ID for context")
    acquiring: List[Dict[str, Any]] = Field(..., description="Players being acquired")
    giving: List[Dict[str, Any]] = Field(..., description="Players being given up")


class TradeAnalysisResponse(BaseModel):
    """Response with trade analysis"""
    acquiring_value: float = Field(..., description="Total value of players acquired")
    giving_value: float = Field(..., description="Total value of players given up")
    value_difference: float = Field(..., description="Net value change")
    fit_improvement: float = Field(..., description="How trade improves team fit")
    recommendation: str = Field(..., description="Trade recommendation")
    confidence: str = Field(..., description="Confidence level (high, medium, low)")
    analysis: Dict[str, Any] = Field(..., description="Detailed analysis breakdown")


class ConnectionStatusResponse(BaseModel):
    """Response for Fantrax connection status"""
    connected: bool = Field(..., description="Whether Fantrax is connected")
    fantrax_user_id: Optional[str] = Field(None, description="Connected Fantrax user ID")
    connected_at: Optional[datetime] = Field(None, description="When connection was established")
    leagues_count: Optional[int] = Field(None, description="Number of leagues found")


# In-Browser Authentication Schemas

class AuthInitiateResponse(BaseModel):
    """Response when initiating in-browser authentication"""
    session_id: str = Field(..., description="Unique session identifier for polling")
    status_url: str = Field(..., description="URL to poll for authentication status")
    expires_in: int = Field(..., description="Seconds until session expires")
    message: str = Field(..., description="User-friendly status message")


class AuthStatusResponse(BaseModel):
    """Response for authentication status polling"""
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Current status (initializing, ready, authenticating, success, failed, timeout)")
    current_url: Optional[str] = Field(None, description="Current browser URL")
    elapsed_seconds: int = Field(..., description="Seconds since session started")
    expires_in: int = Field(..., description="Seconds until session expires")
    message: str = Field(..., description="User-friendly status message")

    @validator('status')
    def validate_status(cls, v):
        allowed = ['initializing', 'ready', 'authenticating', 'success', 'failed', 'timeout', 'cancelled']
        if v not in allowed:
            raise ValueError(f'status must be one of {allowed}')
        return v


class AuthCompleteResponse(BaseModel):
    """Response after completing authentication"""
    success: bool = Field(..., description="Whether authentication was successful")
    message: str = Field(..., description="Success message")
    connected_at: datetime = Field(..., description="Timestamp of successful connection")


class AuthCancelResponse(BaseModel):
    """Response after cancelling authentication"""
    success: bool = Field(..., description="Whether cancellation was successful")
    message: str = Field(..., description="Cancellation message")


class FantraxConnectionResponse(BaseModel):
    """Response for Fantrax connection via cookie upload"""
    success: bool = Field(..., description="Whether connection was successful")
    message: str = Field(..., description="Status message")
    connected_at: Optional[datetime] = Field(None, description="Connection timestamp")


class FantraxLeagueInfo(BaseModel):
    """Information about a Fantrax league"""
    league_id: str = Field(..., description="Unique league identifier")
    league_name: str = Field(..., description="League name")
    league_type: str = Field(..., description="League type (dynasty, keeper, redraft)")
    team_name: Optional[str] = Field(None, description="User's team name in this league")
    roster_size: Optional[int] = Field(None, description="Total roster spots")
    scoring_categories: Optional[List[str]] = Field(None, description="Scoring categories")


class FantraxRosterResponse(BaseModel):
    """Response with roster data"""
    league_id: str = Field(..., description="League identifier")
    players: List[FantraxRosterPlayerInDB] = Field(..., description="Roster players")
    last_sync: datetime = Field(..., description="Last sync timestamp")
    total_players: int = Field(..., description="Total number of players on roster")


class FantraxSecretAPIRosterResponse(BaseModel):
    """Response with roster data from Secret ID API"""
    league_id: str = Field(..., description="League identifier")
    period: Optional[int] = Field(None, description="Period number")
    rosters: List[Dict[str, Any]] = Field(..., description="Team rosters")


class FantraxStandingsResponse(BaseModel):
    """Response with league standings"""
    league_id: str = Field(..., description="League identifier")
    standings: List[Dict[str, Any]] = Field(..., description="Team standings")
    user_rank: int = Field(..., description="User's current rank")
    total_teams: int = Field(..., description="Total teams in league")


class FantraxTransactionsResponse(BaseModel):
    """Response with recent transactions"""
    league_id: str = Field(..., description="League identifier")
    transactions: List[Dict[str, Any]] = Field(..., description="Recent transactions")
    last_updated: datetime = Field(..., description="Last update timestamp")
