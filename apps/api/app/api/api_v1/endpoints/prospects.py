from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import json
import logging
import io
from datetime import datetime

from app.api.deps import get_current_user, get_current_user_optional
from app.db.database import get_db
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction, User
from app.services.dynasty_ranking_service import DynastyRankingService
from app.services.prospect_search_service import ProspectSearchService
from app.services.prospect_stats_service import ProspectStatsService
from app.services.prospect_comparisons_service import ProspectComparisonsService
from app.core.cache_manager import cache_manager
from app.core.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


class ProspectRankingResponse(BaseModel):
    """Response model for prospect rankings."""
    id: int
    mlb_id: str
    name: str
    position: str
    organization: Optional[str]
    level: Optional[str]
    age: Optional[int]
    eta_year: Optional[int]
    dynasty_rank: int = Field(description="Overall dynasty ranking")
    dynasty_score: float = Field(description="Dynasty score (0-100)")
    ml_score: float = Field(description="ML prediction component")
    scouting_score: float = Field(description="Scouting grade component")
    confidence_level: str = Field(description="Prediction confidence (High/Medium/Low)")

    # Latest stats summary
    batting_avg: Optional[float] = None
    on_base_pct: Optional[float] = None
    slugging_pct: Optional[float] = None
    era: Optional[float] = None
    whip: Optional[float] = None

    # Scouting grade summary
    overall_grade: Optional[int] = None
    future_value: Optional[int] = None


class ProspectRankingsPage(BaseModel):
    """Paginated response for prospect rankings."""
    prospects: List[ProspectRankingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProspectSearchSuggestion(BaseModel):
    """Autocomplete suggestion for prospect search."""
    name: str
    organization: Optional[str]
    position: str
    display: str


@router.get("/", response_model=ProspectRankingsPage)
# @limiter.limit("100/minute")
async def get_prospect_rankings(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (25, 50, 100)"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Total limit of prospects (premium: up to 500)"),

    # Filtering
    position: Optional[List[str]] = Query(None, description="Filter by positions"),
    organization: Optional[List[str]] = Query(None, description="Filter by organizations"),
    level: Optional[List[str]] = Query(None, description="Filter by minor league levels"),
    eta_min: Optional[int] = Query(None, ge=2024, le=2035, description="Minimum ETA year"),
    eta_max: Optional[int] = Query(None, ge=2024, le=2035, description="Maximum ETA year"),
    age_min: Optional[int] = Query(None, ge=16, le=50, description="Minimum age"),
    age_max: Optional[int] = Query(None, ge=16, le=50, description="Maximum age"),

    # Search
    search: Optional[str] = Query(None, min_length=2, description="Search query for name/organization"),

    # Sorting
    sort_by: str = Query("dynasty_rank", description="Sort field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),

    # Dependencies
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
) -> ProspectRankingsPage:
    """
    Get paginated, filtered, and sorted prospect rankings.

    Features:
    - Real-time dynasty-specific scoring algorithm
    - Advanced filtering by position, organization, level, ETA, age
    - Fuzzy search on names and organizations
    - Configurable pagination (25, 50, 100 per page)
    - Sortable by multiple metrics
    - 30-minute Redis caching for performance
    - Free tier: Top 100 prospects
    - Premium tier: Full top 500 prospects
    """

    # Validate page_size
    if page_size not in [25, 50, 100]:
        page_size = 50

    # Check user subscription tier to determine prospect limit
    from app.api.deps import check_subscription_feature
    from sqlalchemy import select

    # Get user from database to check subscription tier
    if current_user:
        stmt = select(User).where(User.email == current_user.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        user_tier = user.subscription_tier if user else "free"
    else:
        # Unauthenticated users default to free tier
        user_tier = "free"

    # Determine prospect limit based on tier
    if limit is None:
        if user_tier == "premium":
            max_prospects = 500
        else:
            max_prospects = 100
    else:
        # User specified a limit, validate based on tier
        if user_tier == "premium":
            max_prospects = min(limit, 500)
        else:
            max_prospects = min(limit, 100)

    # Generate cache key for this specific query
    cache_key = f"rankings:{user_tier}:{page}:{page_size}:{max_prospects}:{sort_by}:{sort_order}"
    filter_dict = {
        "position": position,
        "organization": organization,
        "level": level,
        "eta_min": eta_min,
        "eta_max": eta_max,
        "age_min": age_min,
        "age_max": age_max,
        "search": search
    }
    cache_key += f":{json.dumps(filter_dict, sort_keys=True)}"

    # Try to get from cache
    cached_result = await cache_manager.get_cached_features(cache_key)
    if cached_result:
        logger.info(f"Cache hit for rankings query: {cache_key}")
        return ProspectRankingsPage(**cached_result)

    # Build base query with eager loading
    query = select(Prospect).options(
        selectinload(Prospect.stats),
        selectinload(Prospect.scouting_grades)
    )

    # Apply search filter
    if search:
        # Use the search service for fuzzy matching
        search_prospects = await ProspectSearchService.search_prospects(db, search, limit=500)
        if search_prospects:
            prospect_ids = [p.id for p in search_prospects]
            query = query.where(Prospect.id.in_(prospect_ids))
        else:
            # No matches found
            return ProspectRankingsPage(
                prospects=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )

    # Apply filters
    filters = []

    if position:
        filters.append(Prospect.position.in_(position))

    if organization:
        filters.append(Prospect.organization.in_(organization))

    if level:
        filters.append(Prospect.level.in_(level))

    if eta_min is not None:
        filters.append(Prospect.eta_year >= eta_min)

    if eta_max is not None:
        filters.append(Prospect.eta_year <= eta_max)

    if age_min is not None:
        filters.append(Prospect.age >= age_min)

    if age_max is not None:
        filters.append(Prospect.age <= age_max)

    if filters:
        query = query.where(and_(*filters))

    # Execute query
    result = await db.execute(query)
    prospects = result.scalars().all()

    # Get ML predictions for all prospects
    prospect_ids = [p.id for p in prospects]
    ml_predictions_query = select(MLPrediction).where(
        and_(
            MLPrediction.prospect_id.in_(prospect_ids),
            MLPrediction.prediction_type == 'success_rating'
        )
    )
    ml_result = await db.execute(ml_predictions_query)
    ml_predictions = {pred.prospect_id: pred for pred in ml_result.scalars().all()}

    # Calculate dynasty scores and rankings
    prospects_with_scores = []

    for prospect in prospects:
        # Get latest stats
        latest_stats = None
        if prospect.stats:
            latest_stats = max(prospect.stats, key=lambda s: s.date_recorded)

        # Get best scouting grade
        best_grade = None
        if prospect.scouting_grades:
            # Prioritize Fangraphs, then MLB Pipeline
            for source_priority in ['Fangraphs', 'MLB Pipeline', 'Baseball America']:
                grades = [g for g in prospect.scouting_grades if g.source == source_priority]
                if grades:
                    best_grade = grades[0]
                    break

        # Get ML prediction
        ml_prediction = ml_predictions.get(prospect.id)

        # Calculate dynasty score
        score_components = DynastyRankingService.calculate_dynasty_score(
            prospect=prospect,
            ml_prediction=ml_prediction,
            latest_stats=latest_stats,
            scouting_grade=best_grade
        )

        prospects_with_scores.append((prospect, score_components, latest_stats, best_grade))

    # Rank prospects
    ranked_prospects = DynastyRankingService.rank_prospects(
        [(p, s) for p, s, _, _ in prospects_with_scores]
    )

    # Apply prospect limit based on subscription tier (before sorting)
    # First sort by dynasty rank to get top N prospects
    ranked_prospects.sort(key=lambda x: x[1]['dynasty_rank'])
    ranked_prospects = ranked_prospects[:max_prospects]

    # Apply sorting
    sort_key_map = {
        'dynasty_rank': lambda x: x[1]['dynasty_rank'],
        'dynasty_score': lambda x: x[1]['total_score'],
        'ml_score': lambda x: x[1]['ml_score'],
        'scouting_score': lambda x: x[1]['scouting_score'],
        'age': lambda x: x[0].age or 99,
        'eta_year': lambda x: x[0].eta_year or 2099,
        'name': lambda x: x[0].name
    }

    if sort_by in sort_key_map:
        reverse = (sort_order == 'desc')
        if sort_by == 'dynasty_rank':  # Rank should be ascending by default
            reverse = not reverse
        ranked_prospects.sort(key=sort_key_map[sort_by], reverse=reverse)

    # Pagination
    total = len(ranked_prospects)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_prospects = ranked_prospects[start_idx:end_idx]

    # Build response
    response_prospects = []

    for prospect, scores in paginated_prospects:
        # Find corresponding stats and grade from original list
        orig_data = next((item for item in prospects_with_scores if item[0].id == prospect.id), None)
        if orig_data:
            _, _, latest_stats, best_grade = orig_data

            response = ProspectRankingResponse(
                id=prospect.id,
                mlb_id=prospect.mlb_id,
                name=prospect.name,
                position=prospect.position,
                organization=prospect.organization,
                level=prospect.level,
                age=prospect.age,
                eta_year=prospect.eta_year,
                dynasty_rank=scores['dynasty_rank'],
                dynasty_score=round(scores['total_score'], 2),
                ml_score=round(scores['ml_score'], 2),
                scouting_score=round(scores['scouting_score'], 2),
                confidence_level=scores['confidence_level']
            )

            # Add stats if available
            if latest_stats:
                if prospect.position not in ['SP', 'RP']:
                    response.batting_avg = latest_stats.batting_avg
                    response.on_base_pct = latest_stats.on_base_pct
                    response.slugging_pct = latest_stats.slugging_pct
                else:
                    response.era = latest_stats.era
                    response.whip = latest_stats.whip

            # Add scouting grades if available
            if best_grade:
                response.overall_grade = best_grade.overall
                response.future_value = best_grade.future_value

            response_prospects.append(response)

    result = ProspectRankingsPage(
        prospects=response_prospects,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0
    )

    # Cache the result for 30 minutes
    await cache_manager.cache_prospect_features(
        cache_key,
        result.dict(),
        ttl=1800  # 30 minutes
    )

    return result


@router.get("/search/autocomplete", response_model=List[ProspectSearchSuggestion])
# @limiter.limit("200/minute")
async def prospect_autocomplete(
    q: str = Query(..., min_length=1, max_length=50, description="Search prefix"),
    limit: int = Query(5, ge=1, le=10, description="Maximum suggestions"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[ProspectSearchSuggestion]:
    """
    Get autocomplete suggestions for prospect search.

    Returns up to 5 suggestions based on name prefix matching.
    """
    suggestions = await ProspectSearchService.search_prospects_autocomplete(
        db=db,
        prefix=q,
        limit=limit
    )

    return [
        ProspectSearchSuggestion(**suggestion)
        for suggestion in suggestions
    ]


@router.get("/{prospect_id}", response_model=ProspectRankingResponse)
# @limiter.limit("100/minute")
async def get_prospect(
    prospect_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ProspectRankingResponse:
    """
    Get detailed information for a specific prospect.
    """
    # Get prospect with related data
    query = select(Prospect).options(
        selectinload(Prospect.stats),
        selectinload(Prospect.scouting_grades)
    ).where(Prospect.id == prospect_id)

    result = await db.execute(query)
    prospect = result.scalar_one_or_none()

    if not prospect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prospect not found"
        )

    # Get ML prediction
    ml_query = select(MLPrediction).where(
        and_(
            MLPrediction.prospect_id == prospect_id,
            MLPrediction.prediction_type == 'success_rating'
        )
    )
    ml_result = await db.execute(ml_query)
    ml_prediction = ml_result.scalar_one_or_none()

    # Get latest stats
    latest_stats = None
    if prospect.stats:
        latest_stats = max(prospect.stats, key=lambda s: s.date_recorded)

    # Get best scouting grade
    best_grade = None
    if prospect.scouting_grades:
        for source_priority in ['Fangraphs', 'MLB Pipeline', 'Baseball America']:
            grades = [g for g in prospect.scouting_grades if g.source == source_priority]
            if grades:
                best_grade = grades[0]
                break

    # Calculate dynasty score
    score_components = DynastyRankingService.calculate_dynasty_score(
        prospect=prospect,
        ml_prediction=ml_prediction,
        latest_stats=latest_stats,
        scouting_grade=best_grade
    )

    # Calculate actual rank by comparing with all prospects
    # For single prospect endpoint, we need to calculate relative ranking
    all_prospects_query = select(func.count(Prospect.id))
    total_result = await db.execute(all_prospects_query)
    total_prospects = total_result.scalar()

    # Estimate rank based on score percentile (simplified approach)
    score_components['dynasty_rank'] = max(1, int(total_prospects * (1 - score_components['total_score'] / 100)))

    response = ProspectRankingResponse(
        id=prospect.id,
        mlb_id=prospect.mlb_id,
        name=prospect.name,
        position=prospect.position,
        organization=prospect.organization,
        level=prospect.level,
        age=prospect.age,
        eta_year=prospect.eta_year,
        dynasty_rank=score_components['dynasty_rank'],
        dynasty_score=round(score_components['total_score'], 2),
        ml_score=round(score_components['ml_score'], 2),
        scouting_score=round(score_components['scouting_score'], 2),
        confidence_level=score_components['confidence_level']
    )

    # Add stats if available
    if latest_stats:
        if prospect.position not in ['SP', 'RP']:
            response.batting_avg = latest_stats.batting_avg
            response.on_base_pct = latest_stats.on_base_pct
            response.slugging_pct = latest_stats.slugging_pct
        else:
            response.era = latest_stats.era
            response.whip = latest_stats.whip

    # Add scouting grades if available
    if best_grade:
        response.overall_grade = best_grade.overall
        response.future_value = best_grade.future_value

    return response


@router.get("/{prospect_id}/profile")
# @limiter.limit("100/minute")
async def get_prospect_profile(
    prospect_id: int,
    include_stats: bool = True,
    include_predictions: bool = True,
    include_comparisons: bool = True,
    include_scouting: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive prospect profile with all historical data.

    Features:
    - Complete statistical history across all minor league levels
    - ML predictions with SHAP explanations
    - Historical and current prospect comparisons
    - Multi-source scouting grades
    - Injury history and organizational context
    - 1-hour Redis caching for performance
    """
    # Generate cache key
    cache_key = f"profile:{prospect_id}:{include_stats}:{include_predictions}:{include_comparisons}:{include_scouting}"
    cached = await cache_manager.get_cached_features(cache_key)
    if cached:
        return cached

    # Get prospect with all related data
    query = select(Prospect).options(
        selectinload(Prospect.stats),
        selectinload(Prospect.scouting_grades)
    ).where(Prospect.id == prospect_id)

    result = await db.execute(query)
    prospect = result.scalar_one_or_none()

    if not prospect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prospect not found"
        )

    # Build comprehensive profile
    profile = {
        "prospect": {
            "id": prospect.id,
            "mlb_id": prospect.mlb_id,
            "name": prospect.name,
            "position": prospect.position,
            "organization": prospect.organization,
            "level": prospect.level,
            "age": prospect.age,
            "eta_year": prospect.eta_year,
            "draft_year": prospect.draft_year,
            "draft_round": prospect.draft_round,
            "draft_pick": prospect.draft_pick
        }
    }

    # Add statistical history
    if include_stats:
        stats_history = await ProspectStatsService.get_stats_history(db, prospect_id)
        multi_level_agg = await ProspectStatsService.get_multi_level_aggregation(db, prospect_id)
        profile["stats"] = {
            "history": stats_history,
            "multi_level_aggregation": multi_level_agg
        }

    # Add ML predictions with SHAP
    if include_predictions:
        ml_query = select(MLPrediction).where(
            and_(
                MLPrediction.prospect_id == prospect_id,
                MLPrediction.prediction_type == 'success_rating'
            )
        ).order_by(MLPrediction.generated_at.desc()).limit(1)

        ml_result = await db.execute(ml_query)
        ml_prediction = ml_result.scalar_one_or_none()

        if ml_prediction:
            profile["ml_prediction"] = {
                "success_probability": ml_prediction.success_probability,
                "confidence_level": ml_prediction.confidence_level,
                "prediction_date": ml_prediction.generated_at.isoformat(),
                "shap_explanation": ml_prediction.feature_importance,  # JSONB with SHAP values
                "narrative": ml_prediction.narrative,
                "model_version": ml_prediction.model_version
            }

    # Add comparisons
    if include_comparisons:
        comparisons = await ProspectComparisonsService.find_similar_prospects(
            db, prospect_id, limit=5, include_historical=True
        )
        org_context = await ProspectComparisonsService.get_organizational_context(
            db, prospect_id
        )
        profile["comparisons"] = comparisons
        profile["organizational_context"] = org_context

    # Add scouting grades
    if include_scouting:
        scouting_data = []
        for grade in prospect.scouting_grades:
            scouting_data.append({
                "source": grade.source,
                "overall": grade.overall,
                "future_value": grade.future_value,
                "hit": grade.hit,
                "power": grade.power,
                "speed": grade.speed,
                "field": grade.field,
                "arm": grade.arm,
                "updated_at": grade.updated_at.isoformat()
            })
        profile["scouting_grades"] = scouting_data

    # Calculate dynasty score
    latest_stats = max(prospect.stats, key=lambda s: s.date_recorded) if prospect.stats else None
    best_grade = None
    if prospect.scouting_grades:
        for source in ['Fangraphs', 'MLB Pipeline', 'Baseball America']:
            grades = [g for g in prospect.scouting_grades if g.source == source]
            if grades:
                best_grade = grades[0]
                break

    ml_prediction = None
    if include_predictions and "ml_prediction" in profile:
        # Create a temporary MLPrediction object for score calculation
        ml_prediction = type('obj', (object,), {
            'success_probability': profile["ml_prediction"]["success_probability"],
            'confidence_level': profile["ml_prediction"]["confidence_level"]
        })()

    dynasty_score = DynastyRankingService.calculate_dynasty_score(
        prospect=prospect,
        ml_prediction=ml_prediction,
        latest_stats=latest_stats,
        scouting_grade=best_grade
    )

    profile["dynasty_metrics"] = {
        "dynasty_score": round(dynasty_score['total_score'], 2),
        "ml_score": round(dynasty_score['ml_score'], 2),
        "scouting_score": round(dynasty_score['scouting_score'], 2),
        "confidence_level": dynasty_score['confidence_level']
    }

    # Cache for 1 hour
    await cache_manager.cache_prospect_features(
        cache_key, profile, ttl=3600
    )

    return profile


@router.get("/{prospect_id}/stats")
# @limiter.limit("100/minute")
async def get_prospect_stats_history(
    prospect_id: int,
    level: Optional[str] = None,
    season: Optional[int] = None,
    limit: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get statistical history for a prospect.

    Args:
        prospect_id: Prospect ID
        level: Optional filter by minor league level
        season: Optional filter by season year
        limit: Optional limit on number of records

    Returns:
        Statistical history organized by level and season
    """
    return await ProspectStatsService.get_stats_history(
        db, prospect_id, level, season, limit
    )


@router.get("/{prospect_id}/comparisons")
# @limiter.limit("100/minute")
async def get_prospect_comparisons(
    prospect_id: int,
    limit: int = Query(5, ge=1, le=10),
    include_historical: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get similar prospects using ML feature similarity.

    Args:
        prospect_id: Prospect ID
        limit: Maximum number of comparisons
        include_historical: Include historical MLB player comparisons

    Returns:
        Current and historical prospect comparisons
    """
    return await ProspectComparisonsService.find_similar_prospects(
        db, prospect_id, limit, include_historical
    )


@router.get("/{prospect_id}/organizational-context")
# @limiter.limit("100/minute")
async def get_prospect_organizational_context(
    prospect_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get organizational depth chart context for a prospect.

    Returns:
        - Prospects at same position in organization
        - Depth chart ranking
        - Blocked status
        - System ranking estimate
    """
    return await ProspectComparisonsService.get_organizational_context(
        db, prospect_id
    )


@router.get("/{prospect_id}/injury-history")
# @limiter.limit("100/minute")
async def get_prospect_injury_history(
    prospect_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get injury history and current status for a prospect.

    Note: This endpoint returns placeholder data as injury tracking
    would require external data sources in production.
    """
    # In production, this would query injury database or external API
    # For now, return structure with placeholder

    return {
        "prospect_id": prospect_id,
        "current_status": "Healthy",
        "injury_history": [],
        "days_missed_current_season": 0,
        "data_source": "placeholder",
        "last_updated": datetime.utcnow().isoformat()
    }


@router.get("/compare")
# @limiter.limit("50/minute")
async def compare_prospects(
    prospect_ids: str = Query(..., description="Comma-separated prospect IDs (2-4 prospects)"),
    include_stats: bool = Query(True, description="Include statistical comparison"),
    include_predictions: bool = Query(True, description="Include ML prediction comparison"),
    include_analogs: bool = Query(True, description="Include historical analog comparison"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Compare multiple prospects side-by-side with comprehensive analytics.

    Features:
    - Multi-prospect comparison supporting 2-4 prospects simultaneously
    - ML prediction differential analysis with SHAP explanations
    - Historical analog comparison using feature similarity
    - Statistical aggregation and comparative metrics
    - 15-minute Redis caching for comparison data
    """
    # Parse and validate prospect IDs
    try:
        prospect_id_list = [int(pid.strip()) for pid in prospect_ids.split(',')]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prospect ID format. Use comma-separated integers."
        )

    if len(prospect_id_list) < 2 or len(prospect_id_list) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must compare between 2-4 prospects"
        )

    # Generate cache key
    cache_key = f"multi_compare:{':'.join(map(str, sorted(prospect_id_list)))}:{include_stats}:{include_predictions}:{include_analogs}"
    cached_result = await cache_manager.get_cached_features(cache_key)
    if cached_result:
        logger.info(f"Cache hit for comparison: {cache_key}")
        return cached_result

    # Get all prospects with comprehensive data
    prospects_data = []
    for prospect_id in prospect_id_list:
        prospect_data = await ProspectComparisonsService._get_prospect_with_features(db, prospect_id)
        if not prospect_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prospect with ID {prospect_id} not found"
            )
        prospects_data.append(prospect_data)

    # Build comparison result
    comparison_result = {
        "prospect_ids": prospect_id_list,
        "prospects": [],
        "comparison_metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "prospects_count": len(prospect_id_list)
        }
    }

    # Add individual prospect data
    for i, data in enumerate(prospects_data):
        prospect = data["prospect"]
        prospect_info = {
            "id": prospect.id,
            "name": prospect.name,
            "position": prospect.position,
            "organization": prospect.organization,
            "level": prospect.level,
            "age": prospect.age,
            "eta_year": prospect.eta_year,
            "draft_year": prospect.draft_year,
            "draft_round": prospect.draft_round
        }

        # Add dynasty score calculation
        ml_prediction = data.get("ml_prediction")
        latest_stats = data.get("latest_stats")
        scouting_grade = data.get("scouting_grade")

        score_components = DynastyRankingService.calculate_dynasty_score(
            prospect=prospect,
            ml_prediction=ml_prediction,
            latest_stats=latest_stats,
            scouting_grade=scouting_grade
        )

        prospect_info["dynasty_metrics"] = {
            "dynasty_score": round(score_components['total_score'], 2),
            "ml_score": round(score_components['ml_score'], 2),
            "scouting_score": round(score_components['scouting_score'], 2),
            "confidence_level": score_components['confidence_level']
        }

        if include_stats and latest_stats:
            if prospect.position not in ['SP', 'RP']:
                prospect_info["stats"] = {
                    "batting_avg": latest_stats.batting_avg,
                    "on_base_pct": latest_stats.on_base_pct,
                    "slugging_pct": latest_stats.slugging_pct,
                    "ops": round((latest_stats.on_base_pct or 0) + (latest_stats.slugging_pct or 0), 3),
                    "wrc_plus": latest_stats.wrc_plus,
                    "strikeout_rate": latest_stats.strikeout_rate,
                    "walk_rate": latest_stats.walk_rate
                }
            else:
                prospect_info["stats"] = {
                    "era": latest_stats.era,
                    "whip": latest_stats.whip,
                    "k_per_9": latest_stats.k_per_9,
                    "bb_per_9": latest_stats.bb_per_9,
                    "fip": latest_stats.fip
                }

        if include_predictions and ml_prediction:
            prospect_info["ml_prediction"] = {
                "success_probability": ml_prediction.success_probability,
                "confidence_level": ml_prediction.confidence_level,
                "shap_values": ml_prediction.feature_importance
            }

        if scouting_grade:
            prospect_info["scouting_grades"] = {
                "overall": scouting_grade.overall,
                "future_value": scouting_grade.future_value,
                "hit": scouting_grade.hit,
                "power": scouting_grade.power,
                "speed": scouting_grade.speed,
                "field": scouting_grade.field,
                "arm": scouting_grade.arm,
                "source": scouting_grade.source
            }

        comparison_result["prospects"].append(prospect_info)

    # Add comparative analysis
    if include_predictions and len([p for p in prospects_data if p.get("ml_prediction")]) >= 2:
        comparison_result["ml_comparison"] = await _generate_ml_comparison_analysis(prospects_data)

    if include_analogs:
        comparison_result["historical_analogs"] = await _generate_comparative_analogs(db, prospects_data)

    # Add statistical comparison metrics
    if include_stats:
        comparison_result["statistical_comparison"] = _generate_statistical_comparison(prospects_data)

    # Cache for 15 minutes
    await cache_manager.cache_prospect_features(
        cache_key, comparison_result, ttl=900
    )

    return comparison_result


@router.get("/compare/analogs")
# @limiter.limit("50/minute")
async def get_comparison_analogs(
    prospect_ids: str = Query(..., description="Comma-separated prospect IDs"),
    limit: int = Query(3, ge=1, le=5, description="Number of analogs per prospect"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get historical analog prospects for a comparison group.

    Returns historical prospects with similar profiles for each prospect
    in the comparison, showing MLB career outcomes.
    """
    try:
        prospect_id_list = [int(pid.strip()) for pid in prospect_ids.split(',')]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prospect ID format"
        )

    analogs_result = {
        "prospect_analogs": [],
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "analogs_per_prospect": limit
        }
    }

    for prospect_id in prospect_id_list:
        prospect_data = await ProspectComparisonsService._get_prospect_with_features(db, prospect_id)
        if prospect_data:
            historical_comps = await ProspectComparisonsService._find_historical_similar(
                db, prospect_data, limit
            )
            analogs_result["prospect_analogs"].append({
                "prospect_id": prospect_id,
                "prospect_name": prospect_data["prospect"].name,
                "historical_analogs": historical_comps
            })

    return analogs_result


@router.post("/compare/export")
# @limiter.limit("20/hour")
async def export_comparison(
    prospect_ids: str,
    format: str = Query(..., regex="^(pdf|csv)$", description="Export format: 'pdf' or 'csv'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate and return comparison export in PDF or CSV format.

    Premium users only. Limited to 20 exports per hour.
    """
    from app.services.export_service import ExportService

    # Validate export access
    ExportService.validate_export_access(current_user)

    try:
        prospect_id_list = [int(pid.strip()) for pid in prospect_ids.split(',')]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid prospect ID format"
        )

    if len(prospect_id_list) < 2 or len(prospect_id_list) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must export comparison for 2-4 prospects"
        )

    # Get comparison data
    comparison_data = await compare_prospects(
        prospect_ids=prospect_ids,
        include_stats=True,
        include_predictions=True,
        include_analogs=True,
        current_user=current_user,
        db=db
    )

    # Generate export based on format
    if format == "pdf":
        export_content = await ExportService.generate_comparison_pdf(comparison_data)
        media_type = "application/pdf"
        filename = f"prospect_comparison_{'-'.join(map(str, prospect_id_list))}_{datetime.now().strftime('%Y%m%d')}.pdf"
    else:  # csv
        export_content = ExportService.generate_comparison_csv(comparison_data)
        media_type = "text/csv"
        filename = f"prospect_comparison_{'-'.join(map(str, prospect_id_list))}_{datetime.now().strftime('%Y%m%d')}.csv"

    return {
        "download_url": f"/api/exports/{filename}",
        "filename": filename,
        "format": format,
        "generated_at": datetime.utcnow().isoformat()
    }


async def _generate_ml_comparison_analysis(prospects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate ML prediction comparison analysis with SHAP differential."""
    ml_prospects = [p for p in prospects_data if p.get("ml_prediction")]

    if len(ml_prospects) < 2:
        return {"error": "Insufficient ML predictions for comparison"}

    analysis = {
        "prediction_comparison": [],
        "shap_differential": {},
        "confidence_analysis": {}
    }

    # Compare predictions pairwise
    for i, prospect_a in enumerate(ml_prospects):
        for j, prospect_b in enumerate(ml_prospects[i+1:], i+1):
            pred_a = prospect_a["ml_prediction"]
            pred_b = prospect_b["ml_prediction"]

            prob_diff = pred_a.success_probability - pred_b.success_probability

            comparison = {
                "prospect_a": {
                    "id": prospect_a["prospect"].id,
                    "name": prospect_a["prospect"].name,
                    "probability": pred_a.success_probability
                },
                "prospect_b": {
                    "id": prospect_b["prospect"].id,
                    "name": prospect_b["prospect"].name,
                    "probability": pred_b.success_probability
                },
                "probability_difference": round(prob_diff, 3),
                "advantage": prospect_a["prospect"].name if prob_diff > 0 else prospect_b["prospect"].name,
                "significance": "High" if abs(prob_diff) > 0.2 else "Medium" if abs(prob_diff) > 0.1 else "Low"
            }

            # SHAP value comparison if available
            if (hasattr(pred_a, 'feature_importance') and hasattr(pred_b, 'feature_importance') and
                pred_a.feature_importance and pred_b.feature_importance):

                shap_a = pred_a.feature_importance
                shap_b = pred_b.feature_importance

                # Find features with largest differences
                feature_diffs = {}
                for feature in shap_a.keys():
                    if feature in shap_b:
                        diff = shap_a[feature] - shap_b[feature]
                        feature_diffs[feature] = diff

                # Get top 3 differential features
                top_diffs = sorted(feature_diffs.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                comparison["key_differentiators"] = [
                    {
                        "feature": feature,
                        "difference": round(diff, 3),
                        "favors": prospect_a["prospect"].name if diff > 0 else prospect_b["prospect"].name
                    }
                    for feature, diff in top_diffs
                ]

            analysis["prediction_comparison"].append(comparison)

    return analysis


async def _generate_comparative_analogs(db: AsyncSession, prospects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate historical analog comparison for multiple prospects."""
    analogs_by_prospect = {}

    for prospect_data in prospects_data:
        historical_comps = await ProspectComparisonsService._find_historical_similar(
            db, prospect_data, limit=3
        )

        analogs_by_prospect[prospect_data["prospect"].id] = {
            "prospect_name": prospect_data["prospect"].name,
            "analogs": historical_comps
        }

    # Find common analog patterns
    all_analog_names = []
    for prospect_analogs in analogs_by_prospect.values():
        for analog in prospect_analogs["analogs"]:
            all_analog_names.append(analog.get("player_name"))

    # Count frequency of analog appearances
    from collections import Counter
    analog_counts = Counter(all_analog_names)
    common_analogs = [name for name, count in analog_counts.items() if count > 1]

    return {
        "prospect_analogs": analogs_by_prospect,
        "common_analog_patterns": common_analogs,
        "comparative_insights": "Multiple prospects share similar historical profiles" if common_analogs else "Distinct prospect profiles with unique analogs"
    }


def _generate_statistical_comparison(prospects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate statistical comparison metrics between prospects."""
    stats_prospects = [p for p in prospects_data if p.get("latest_stats")]

    if len(stats_prospects) < 2:
        return {"error": "Insufficient statistical data for comparison"}

    comparison = {
        "metric_leaders": {},
        "performance_gaps": [],
        "category_analysis": {}
    }

    # Define key metrics by position type
    position_metrics = {
        "hitting": ["batting_avg", "on_base_pct", "slugging_pct", "wrc_plus", "walk_rate"],
        "pitching": ["era", "whip", "k_per_9", "bb_per_9", "fip"]
    }

    # Determine if we're comparing hitters or pitchers
    first_prospect = stats_prospects[0]["prospect"]
    is_pitcher = first_prospect.position in ['SP', 'RP']
    metrics = position_metrics["pitching"] if is_pitcher else position_metrics["hitting"]

    # Find leaders in each metric
    for metric in metrics:
        values = []
        for prospect_data in stats_prospects:
            stats = prospect_data.get("latest_stats")
            if stats and hasattr(stats, metric):
                value = getattr(stats, metric)
                if value is not None:
                    values.append({
                        "prospect_id": prospect_data["prospect"].id,
                        "prospect_name": prospect_data["prospect"].name,
                        "value": value
                    })

        if values:
            # Sort appropriately (lower is better for ERA, WHIP, higher for others)
            reverse_sort = metric not in ["era", "whip", "bb_per_9", "strikeout_rate"]
            sorted_values = sorted(values, key=lambda x: x["value"], reverse=reverse_sort)

            comparison["metric_leaders"][metric] = {
                "leader": sorted_values[0],
                "all_values": sorted_values,
                "range": round(sorted_values[0]["value"] - sorted_values[-1]["value"], 3) if len(sorted_values) > 1 else 0
            }

    # Calculate performance gaps
    for metric, leader_data in comparison["metric_leaders"].items():
        if len(leader_data["all_values"]) > 1:
            leader_value = leader_data["leader"]["value"]
            for prospect_data in leader_data["all_values"][1:]:
                gap = abs(leader_value - prospect_data["value"])
                gap_percentage = (gap / leader_value * 100) if leader_value != 0 else 0

                comparison["performance_gaps"].append({
                    "metric": metric,
                    "leader": leader_data["leader"]["prospect_name"],
                    "trailing_prospect": prospect_data["prospect_name"],
                    "absolute_gap": round(gap, 3),
                    "percentage_gap": round(gap_percentage, 1)
                })

    return comparison


@router.get("/export/csv")
# @limiter.limit("10/hour")
async def export_prospects_csv(
    # Same filters as main endpoint
    position: Optional[List[str]] = Query(None, description="Filter by positions"),
    organization: Optional[List[str]] = Query(None, description="Filter by organizations"),
    level: Optional[List[str]] = Query(None, description="Filter by minor league levels"),
    eta_min: Optional[int] = Query(None, ge=2024, le=2035, description="Minimum ETA year"),
    eta_max: Optional[int] = Query(None, ge=2024, le=2035, description="Maximum ETA year"),
    age_min: Optional[int] = Query(None, ge=16, le=50, description="Minimum age"),
    age_max: Optional[int] = Query(None, ge=16, le=50, description="Maximum age"),
    search: Optional[str] = Query(None, min_length=2, description="Search query"),

    # Dependencies
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export filtered prospect rankings to CSV format.

    Premium users only. Limited to 10 exports per hour.
    """
    from app.services.export_service import ExportService
    from fastapi.responses import StreamingResponse

    # Validate premium access
    ExportService.validate_export_access(current_user)

    # Get prospects using same logic as main endpoint but without pagination
    query = select(Prospect).options(
        selectinload(Prospect.stats),
        selectinload(Prospect.scouting_grades)
    )

    # Apply search filter
    if search:
        search_prospects = await ProspectSearchService.search_prospects(db, search, limit=500)
        if search_prospects:
            prospect_ids = [p.id for p in search_prospects]
            query = query.where(Prospect.id.in_(prospect_ids))
        else:
            # No matches - return empty CSV
            csv_content = ExportService.generate_csv([])
            return StreamingResponse(
                io.StringIO(csv_content),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={ExportService.generate_filename()}"
                }
            )

    # Apply filters
    filters = []
    filter_dict = {}

    if position:
        filters.append(Prospect.position.in_(position))
        filter_dict['position'] = position

    if organization:
        filters.append(Prospect.organization.in_(organization))
        filter_dict['organization'] = organization

    if level:
        filters.append(Prospect.level.in_(level))
        filter_dict['level'] = level

    if eta_min is not None:
        filters.append(Prospect.eta_year >= eta_min)

    if eta_max is not None:
        filters.append(Prospect.eta_year <= eta_max)

    if age_min is not None:
        filters.append(Prospect.age >= age_min)

    if age_max is not None:
        filters.append(Prospect.age <= age_max)

    if filters:
        query = query.where(and_(*filters))

    # Execute query
    result = await db.execute(query)
    prospects = result.scalars().all()

    # Limit to top 500 for exports
    if len(prospects) > 500:
        prospects = prospects[:500]

    # Get ML predictions
    prospect_ids = [p.id for p in prospects]
    ml_predictions_query = select(MLPrediction).where(
        and_(
            MLPrediction.prospect_id.in_(prospect_ids),
            MLPrediction.prediction_type == 'success_rating'
        )
    )
    ml_result = await db.execute(ml_predictions_query)
    ml_predictions = {pred.prospect_id: pred for pred in ml_result.scalars().all()}

    # Calculate scores and rank
    prospects_with_scores = []

    for prospect in prospects:
        latest_stats = None
        if prospect.stats:
            latest_stats = max(prospect.stats, key=lambda s: s.date_recorded)

        best_grade = None
        if prospect.scouting_grades:
            for source_priority in ['Fangraphs', 'MLB Pipeline', 'Baseball America']:
                grades = [g for g in prospect.scouting_grades if g.source == source_priority]
                if grades:
                    best_grade = grades[0]
                    break

        ml_prediction = ml_predictions.get(prospect.id)

        score_components = DynastyRankingService.calculate_dynasty_score(
            prospect=prospect,
            ml_prediction=ml_prediction,
            latest_stats=latest_stats,
            scouting_grade=best_grade
        )

        prospects_with_scores.append((prospect, score_components, latest_stats, best_grade))

    # Rank prospects
    ranked_prospects = DynastyRankingService.rank_prospects(
        [(p, s) for p, s, _, _ in prospects_with_scores]
    )

    # Build export data
    export_data = []
    for prospect, scores in ranked_prospects:
        # Find stats and grade
        orig_data = next((item for item in prospects_with_scores if item[0].id == prospect.id), None)
        if orig_data:
            _, _, latest_stats, best_grade = orig_data

            prospect_dict = {
                'dynasty_rank': scores['dynasty_rank'],
                'name': prospect.name,
                'position': prospect.position,
                'organization': prospect.organization,
                'level': prospect.level,
                'age': prospect.age,
                'eta_year': prospect.eta_year,
                'dynasty_score': scores['total_score'],
                'ml_score': scores['ml_score'],
                'scouting_score': scores['scouting_score'],
                'confidence_level': scores['confidence_level']
            }

            if latest_stats:
                if prospect.position not in ['SP', 'RP']:
                    prospect_dict['batting_avg'] = latest_stats.batting_avg
                    prospect_dict['on_base_pct'] = latest_stats.on_base_pct
                    prospect_dict['slugging_pct'] = latest_stats.slugging_pct
                else:
                    prospect_dict['era'] = latest_stats.era
                    prospect_dict['whip'] = latest_stats.whip

            if best_grade:
                prospect_dict['overall_grade'] = best_grade.overall
                prospect_dict['future_value'] = best_grade.future_value

            export_data.append(prospect_dict)

    # Generate CSV
    csv_content = ExportService.generate_csv(export_data)

    # Return as streaming response
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={ExportService.generate_filename(filter_dict)}"
        }
    )


# ============================================================================
# COMPOSITE RANKINGS ENDPOINT (FanGraphs + MiLB Performance)
# ============================================================================

class CompositeRankingResponse(BaseModel):
    """Response model for composite prospect rankings."""
    rank: int = Field(description="Overall composite rank")
    prospect_id: int
    name: str
    position: str
    organization: Optional[str]
    age: Optional[int]
    level: Optional[str]

    # Score breakdown
    composite_score: float = Field(description="Final composite score")
    base_fv: float = Field(description="FanGraphs Future Value (40-70)")
    performance_modifier: float = Field(description="Recent MiLB performance adjustment")
    trend_adjustment: float = Field(description="30-day vs 60-day trend")
    age_adjustment: float = Field(description="Age-relative-to-level adjustment")
    total_adjustment: float = Field(description="Total adjustment from base FV")

    # Tool grades (for display)
    tool_grades: Dict[str, Optional[int]] = Field(description="Position-specific tool grades")

    # Additional context
    tier: Optional[int] = Field(None, description="Tier classification (1-5)")
    tier_label: Optional[str] = Field(None, description="Tier label (Elite, Top Prospects, etc.)")


class CompositeRankingsPage(BaseModel):
    """Paginated response for composite prospect rankings."""
    prospects: List[CompositeRankingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)


@router.get("/composite-rankings", response_model=CompositeRankingsPage)
async def get_composite_rankings(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),

    # Filtering
    position: Optional[str] = Query(None, description="Filter by position (e.g., SS, SP)"),
    organization: Optional[str] = Query(None, description="Filter by organization"),

    # Limit
    limit: Optional[int] = Query(None, ge=1, le=500, description="Total limit (for export)"),

    # Dependencies
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
) -> CompositeRankingsPage:
    """
    Get composite prospect rankings combining FanGraphs grades with MiLB performance.

    **Algorithm:**
    - Base Score: FanGraphs Future Value (40-70 scale)
    - Performance Modifier: Recent MiLB stats vs level peers (±10)
    - Trend Adjustment: 30-day vs 60-day comparison (±5)
    - Age Adjustment: Age-relative-to-level bonus/penalty (-5 to +5)

    **Formula:**
    ```
    Composite = Base FV + (Performance × 0.5) + (Trend × 0.3) + (Age × 0.2)
    ```

    **Features:**
    - Dynamic adjustments based on recent performance
    - Age-relative-to-level analysis
    - Transparent score breakdowns
    - Position/organization filtering
    - Tier classifications

    **Free Tier:** Top 100 prospects
    **Premium Tier:** Top 500 prospects
    """
    from app.services.prospect_ranking_service import ProspectRankingService

    # Check user tier
    if current_user:
        from sqlalchemy import select
        stmt = select(User).where(User.email == current_user.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        user_tier = user.subscription_tier if user else "free"
    else:
        user_tier = "free"

    # Determine max prospects based on tier
    if user_tier == "premium":
        max_prospects = 500
    else:
        max_prospects = 100

    # Apply user-specified limit
    if limit:
        max_prospects = min(limit, max_prospects)

    # Generate cache key
    cache_key = f"composite_rankings:{user_tier}:{position}:{organization}:{limit}"

    # Try cache (30-minute TTL)
    cached_result = await cache_manager.get_cached_features(cache_key)
    if cached_result:
        logger.info(f"Cache hit for composite rankings: {cache_key}")

        # Apply pagination to cached result
        total = cached_result['total']
        all_prospects = cached_result['prospects']

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_prospects = all_prospects[start_idx:end_idx]

        return CompositeRankingsPage(
            prospects=paginated_prospects,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
            generated_at=datetime.fromisoformat(cached_result['generated_at'])
        )

    # Generate rankings using service
    service = ProspectRankingService(db)

    try:
        rankings = await service.generate_prospect_rankings(
            position_filter=position,
            organization_filter=organization,
            limit=max_prospects
        )

        # Build response objects
        response_prospects = []

        for ranked_prospect in rankings:
            # Get tier classification
            tier_info = await service.get_tier_classification(ranked_prospect['rank'])

            response_prospects.append(CompositeRankingResponse(
                rank=ranked_prospect['rank'],
                prospect_id=ranked_prospect['prospect_id'],
                name=ranked_prospect['name'],
                position=ranked_prospect['position'],
                organization=ranked_prospect['organization'],
                age=ranked_prospect['age'],
                level=ranked_prospect['level'],
                composite_score=ranked_prospect['scores']['composite_score'],
                base_fv=ranked_prospect['scores']['base_fv'],
                performance_modifier=ranked_prospect['scores']['performance_modifier'],
                trend_adjustment=ranked_prospect['scores']['trend_adjustment'],
                age_adjustment=ranked_prospect['scores']['age_adjustment'],
                total_adjustment=ranked_prospect['scores']['total_adjustment'],
                tool_grades=ranked_prospect['tool_grades'],
                tier=tier_info['tier'],
                tier_label=tier_info['label']
            ))

        total = len(response_prospects)

        # Cache the full result (30-minute TTL)
        cache_data = {
            'total': total,
            'prospects': [p.dict() for p in response_prospects],
            'generated_at': datetime.utcnow().isoformat()
        }
        await cache_manager.cache_features(cache_key, cache_data, ttl=1800)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_prospects = response_prospects[start_idx:end_idx]

        return CompositeRankingsPage(
            prospects=paginated_prospects,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )

    except Exception as e:
        logger.error(f"Error generating composite rankings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate rankings: {str(e)}"
        )