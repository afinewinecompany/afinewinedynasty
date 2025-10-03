"""
Recommendation Schemas

Pydantic schemas for personalized recommendation API requests and responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TeamNeedsResponse(BaseModel):
    """Team needs analysis response"""
    league_id: str
    positional_needs: Dict[str, Any]
    depth_analysis: Dict[str, Any]
    competitive_window: Dict[str, Any]
    future_needs: Dict[str, Any]
    quality_tiers: Dict[str, Any]


class ProspectRecommendationResponse(BaseModel):
    """Prospect recommendations response"""
    league_id: str
    recommendations: List[Dict[str, Any]]
    count: int


class TradeTargetsResponse(BaseModel):
    """Trade targets response"""
    league_id: str
    buy_low_candidates: List[Dict[str, Any]]
    sell_high_opportunities: List[Dict[str, Any]]
    value_arbitrage: List[Dict[str, Any]]


class DraftStrategyResponse(BaseModel):
    """Draft strategy response"""
    league_id: str
    pick_number: Optional[int]
    tier_1: List[Dict[str, Any]]
    tier_2: List[Dict[str, Any]]
    tier_3: List[Dict[str, Any]]
    bpa_vs_need_advice: str
    sleeper_candidates: List[Dict[str, Any]]


class StashCandidatesResponse(BaseModel):
    """Stash candidates response"""
    league_id: str
    available_spots: int
    stash_candidates: List[Dict[str, Any]]
    recommendation: str


class UserPreferencesResponse(BaseModel):
    """User preferences response"""
    user_id: int
    risk_tolerance: str
    prefer_win_now: bool
    prefer_rebuild: bool
    position_priorities: Optional[Dict[str, Any]]
    prefer_buy_low: bool
    prefer_sell_high: bool


class UserPreferencesUpdate(BaseModel):
    """User preferences update request"""
    risk_tolerance: Optional[str] = Field(None, regex="^(conservative|balanced|aggressive)$")
    prefer_win_now: Optional[bool] = None
    prefer_rebuild: Optional[bool] = None
    position_priorities: Optional[Dict[str, Any]] = None
    prefer_buy_low: Optional[bool] = None
    prefer_sell_high: Optional[bool] = None
