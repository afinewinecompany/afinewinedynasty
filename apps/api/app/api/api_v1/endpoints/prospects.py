from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import json
import logging
import io

from app.api.deps import get_current_user
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
@limiter.limit("100/minute")
async def get_prospect_rankings(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (25, 50, 100)"),

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
    current_user: User = Depends(get_current_user),
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
    """

    # Validate page_size
    if page_size not in [25, 50, 100]:
        page_size = 50

    # Generate cache key for this specific query
    cache_key = f"rankings:{page}:{page_size}:{sort_by}:{sort_order}"
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
@limiter.limit("200/minute")
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
@limiter.limit("100/minute")
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
@limiter.limit("100/minute")
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
@limiter.limit("100/minute")
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
@limiter.limit("100/minute")
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
@limiter.limit("100/minute")
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
@limiter.limit("100/minute")
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


@router.get("/export/csv")
@limiter.limit("10/hour")
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