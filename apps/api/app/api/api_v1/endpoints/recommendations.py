"""
Recommendations API Endpoints

Personalized prospect recommendations based on team needs, timeline,
and user preferences for optimal fantasy baseball decision-making.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.api import deps
from app.db.session import get_db
from app.db.models import User, UserRecommendationPreference, RecommendationHistory, FantraxLeague
from app.schemas.recommendations import (
    TeamNeedsResponse,
    ProspectRecommendationResponse,
    TradeTargetsResponse,
    DraftStrategyResponse,
    StashCandidatesResponse,
    UserPreferencesResponse,
    UserPreferencesUpdate
)
from app.services.roster_analysis_service import RosterAnalysisService
from app.services.personalized_recommendation_service import PersonalizedRecommendationService
from app.services.fit_scoring_service import FitScoringService
from app.core.security import require_premium_tier
from app.core.rate_limiter import limiter

router = APIRouter()


@router.get("/team-needs/{league_id}", response_model=TeamNeedsResponse)
@limiter.limit("60/hour")
async def get_team_needs(
    request: Request,
    league_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TeamNeedsResponse:
    """
    Get detailed team needs analysis for a league

    Provides comprehensive positional needs, depth analysis, competitive window,
    and future needs projections to guide prospect targeting.

    @param league_id - Fantrax league ID
    @returns Detailed team needs breakdown

    @since 4.4.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Get team analysis
    roster_service = RosterAnalysisService(db, current_user.id)
    analysis = await roster_service.analyze_team(league_id)

    return TeamNeedsResponse(
        league_id=league_id,
        positional_needs=analysis.get("positional_gap_scores", {}),
        depth_analysis=analysis.get("position_depth", {}),
        competitive_window=analysis.get("competitive_window", {}),
        future_needs=analysis.get("future_needs", {}),
        quality_tiers=analysis.get("quality_tiers", {})
    )


@router.get("/prospects/{league_id}", response_model=ProspectRecommendationResponse)
@limiter.limit("60/hour")
async def get_prospect_recommendations(
    request: Request,
    league_id: str,
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations"),
    risk_tolerance: Optional[str] = Query(None, regex="^(conservative|balanced|aggressive)$"),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ProspectRecommendationResponse:
    """
    Get personalized prospect recommendations for a league

    Returns ranked prospect list with fit scores, explanations, and confidence levels
    tailored to team needs, competitive window, and user preferences.

    @param league_id - Fantrax league ID
    @param limit - Maximum number of recommendations (1-50)
    @param risk_tolerance - Override user's risk tolerance setting

    @returns Ranked prospect recommendations

    @since 4.4.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Get recommendations
    rec_service = PersonalizedRecommendationService(db, current_user.id)
    recommendations = await rec_service.get_recommendations(league_id, limit)

    # Apply risk tolerance filter if specified
    # (Would integrate with user preferences here)

    # Persist recommendations to history for quality monitoring
    from sqlalchemy import select
    stmt = select(FantraxLeague).where(FantraxLeague.league_id == league_id)
    result = await db.execute(stmt)
    league = result.scalar_one_or_none()

    if league and recommendations:
        # Save top recommendations to history
        for rec in recommendations[:5]:  # Track top 5 for monitoring
            history_entry = RecommendationHistory(
                user_id=current_user.id,
                league_id=league.id,
                prospect_id=rec.get('prospect_id'),
                recommendation_type='fit',
                fit_score=rec.get('fit_score', 0),
                reasoning=rec.get('reason', '')
            )
            db.add(history_entry)
        await db.commit()

    return ProspectRecommendationResponse(
        league_id=league_id,
        recommendations=recommendations,
        count=len(recommendations)
    )


@router.get("/trade-targets/{league_id}", response_model=TradeTargetsResponse)
@limiter.limit("60/hour")
async def get_trade_targets(
    request: Request,
    league_id: str,
    category: str = Query("all", regex="^(all|buy_low|sell_high|arbitrage)$"),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TradeTargetsResponse:
    """
    Identify trade opportunities matching team needs

    Analyzes undervalued prospects (buy-low), overperforming assets (sell-high),
    and value arbitrage opportunities based on team-specific context.

    @param league_id - Fantrax league ID
    @param category - Trade category filter (all, buy_low, sell_high, arbitrage)

    @returns Trade opportunity recommendations

    @since 4.4.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Get trade opportunities
    rec_service = PersonalizedRecommendationService(db, current_user.id)
    opportunities = await rec_service.identify_trade_opportunities(league_id, category)

    return TradeTargetsResponse(
        league_id=league_id,
        buy_low_candidates=opportunities.get("buy_low_candidates", []),
        sell_high_opportunities=opportunities.get("sell_high_opportunities", []),
        value_arbitrage=opportunities.get("value_arbitrage", [])
    )


@router.get("/draft-strategy/{league_id}", response_model=DraftStrategyResponse)
@limiter.limit("60/hour")
async def get_draft_strategy(
    request: Request,
    league_id: str,
    pick_number: Optional[int] = Query(None, ge=1, le=500),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> DraftStrategyResponse:
    """
    Get draft strategy recommendations for rookie drafts

    Provides tiered draft board based on team needs, BPA vs need analysis,
    and sleeper candidate identification for optimal draft execution.

    @param league_id - Fantrax league ID
    @param pick_number - Current draft pick position

    @returns Draft strategy guidance

    @since 4.4.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Get draft strategy
    rec_service = PersonalizedRecommendationService(db, current_user.id)
    roster_service = RosterAnalysisService(db, current_user.id)

    # Get team analysis
    analysis = await roster_service.analyze_team(league_id)

    # Get top prospects
    recommendations = await rec_service.get_recommendations(league_id, limit=50)

    # Tier prospects (simplified for now)
    tier_1 = [r for r in recommendations[:10]]
    tier_2 = [r for r in recommendations[10:25]]
    tier_3 = [r for r in recommendations[25:40]]

    return DraftStrategyResponse(
        league_id=league_id,
        pick_number=pick_number,
        tier_1=tier_1,
        tier_2=tier_2,
        tier_3=tier_3,
        bpa_vs_need_advice="Draft BPA if tier drop after your pick, otherwise fill need",
        sleeper_candidates=recommendations[40:50] if len(recommendations) > 40 else []
    )


@router.get("/stash-candidates/{league_id}", response_model=StashCandidatesResponse)
@limiter.limit("60/hour")
async def get_stash_candidates(
    request: Request,
    league_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> StashCandidatesResponse:
    """
    Get prospect stashing recommendations

    Identifies high-upside stashing targets based on available roster spots,
    team timeline, and opportunity cost analysis.

    @param league_id - Fantrax league ID

    @returns Stash candidate recommendations

    @since 4.4.0
    """
    # Premium tier check
    require_premium_tier(current_user)

    # Get team analysis
    roster_service = RosterAnalysisService(db, current_user.id)
    analysis = await roster_service.analyze_team(league_id)

    available_spots = analysis.get("available_spots", 0)
    competitive_window = analysis.get("competitive_window", {})

    # Get high-upside prospects appropriate for stashing
    rec_service = PersonalizedRecommendationService(db, current_user.id)

    # Only recommend stashing if rebuilding/transitional
    if competitive_window.get("window") in ["rebuilding", "transitional"]:
        stash_candidates = await rec_service.get_recommendations(league_id, limit=15)
    else:
        stash_candidates = []

    return StashCandidatesResponse(
        league_id=league_id,
        available_spots=available_spots,
        stash_candidates=stash_candidates,
        recommendation="Focus on high-upside prospects with 2-4 year ETA" if available_spots > 0 else "No roster spots available for stashing"
    )


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserPreferencesResponse:
    """
    Get user's recommendation preferences

    @returns User preference settings

    @since 4.4.0
    """
    from sqlalchemy import select

    stmt = select(UserRecommendationPreference).where(
        UserRecommendationPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Return defaults
        return UserPreferencesResponse(
            user_id=current_user.id,
            risk_tolerance="balanced",
            prefer_win_now=False,
            prefer_rebuild=False,
            position_priorities=None,
            prefer_buy_low=True,
            prefer_sell_high=True
        )

    return UserPreferencesResponse(
        user_id=prefs.user_id,
        risk_tolerance=prefs.risk_tolerance,
        prefer_win_now=prefs.prefer_win_now,
        prefer_rebuild=prefs.prefer_rebuild,
        position_priorities=prefs.position_priorities,
        prefer_buy_low=prefs.prefer_buy_low,
        prefer_sell_high=prefs.prefer_sell_high
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserPreferencesResponse:
    """
    Update user's recommendation preferences

    @param preferences - Updated preference settings

    @returns Updated preferences

    @since 4.4.0
    """
    from sqlalchemy import select
    from datetime import datetime

    stmt = select(UserRecommendationPreference).where(
        UserRecommendationPreference.user_id == current_user.id
    )
    result = await db.execute(stmt)
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create new preferences
        prefs = UserRecommendationPreference(
            user_id=current_user.id,
            risk_tolerance=preferences.risk_tolerance or "balanced",
            prefer_win_now=preferences.prefer_win_now or False,
            prefer_rebuild=preferences.prefer_rebuild or False,
            position_priorities=preferences.position_priorities,
            prefer_buy_low=preferences.prefer_buy_low if preferences.prefer_buy_low is not None else True,
            prefer_sell_high=preferences.prefer_sell_high if preferences.prefer_sell_high is not None else True
        )
        db.add(prefs)
    else:
        # Update existing
        if preferences.risk_tolerance:
            prefs.risk_tolerance = preferences.risk_tolerance
        if preferences.prefer_win_now is not None:
            prefs.prefer_win_now = preferences.prefer_win_now
        if preferences.prefer_rebuild is not None:
            prefs.prefer_rebuild = preferences.prefer_rebuild
        if preferences.position_priorities is not None:
            prefs.position_priorities = preferences.position_priorities
        if preferences.prefer_buy_low is not None:
            prefs.prefer_buy_low = preferences.prefer_buy_low
        if preferences.prefer_sell_high is not None:
            prefs.prefer_sell_high = preferences.prefer_sell_high

        prefs.updated_at = datetime.now()

    await db.commit()
    await db.refresh(prefs)

    return UserPreferencesResponse(
        user_id=prefs.user_id,
        risk_tolerance=prefs.risk_tolerance,
        prefer_win_now=prefs.prefer_win_now,
        prefer_rebuild=prefs.prefer_rebuild,
        position_priorities=prefs.position_priorities,
        prefer_buy_low=prefs.prefer_buy_low,
        prefer_sell_high=prefs.prefer_sell_high
    )
