"""Advanced search endpoints for prospects."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User, UserSearchHistory, UserProspectView
from app.services.advanced_search_service import AdvancedSearchService, AdvancedSearchCriteria
from app.services.saved_search_service import SavedSearchService
from app.core.cache_manager import cache_manager
from app.core.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


class AdvancedSearchRequest(BaseModel):
    """Request model for advanced search."""

    # Statistical criteria
    min_batting_avg: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_batting_avg: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_on_base_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_on_base_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_slugging_pct: Optional[float] = Field(None, ge=0.0, le=3.0)
    max_slugging_pct: Optional[float] = Field(None, ge=0.0, le=3.0)
    min_era: Optional[float] = Field(None, ge=0.0, le=20.0)
    max_era: Optional[float] = Field(None, ge=0.0, le=20.0)
    min_whip: Optional[float] = Field(None, ge=0.0, le=5.0)
    max_whip: Optional[float] = Field(None, ge=0.0, le=5.0)
    min_woba: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_woba: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_wrc_plus: Optional[int] = Field(None, ge=0, le=300)
    max_wrc_plus: Optional[int] = Field(None, ge=0, le=300)

    # Basic prospect criteria
    positions: Optional[List[str]] = Field(None, description="List of positions to include")
    organizations: Optional[List[str]] = Field(None, description="List of organizations to include")
    levels: Optional[List[str]] = Field(None, description="List of levels to include")
    min_age: Optional[int] = Field(None, ge=16, le=35)
    max_age: Optional[int] = Field(None, ge=16, le=35)
    min_eta_year: Optional[int] = Field(None, ge=2024, le=2035)
    max_eta_year: Optional[int] = Field(None, ge=2024, le=2035)

    # Scouting criteria
    min_overall_grade: Optional[int] = Field(None, ge=20, le=80)
    max_overall_grade: Optional[int] = Field(None, ge=20, le=80)
    scouting_sources: Optional[List[str]] = Field(None, description="List of scouting sources")
    min_hit_grade: Optional[int] = Field(None, ge=20, le=80)
    max_hit_grade: Optional[int] = Field(None, ge=20, le=80)
    min_power_grade: Optional[int] = Field(None, ge=20, le=80)
    max_power_grade: Optional[int] = Field(None, ge=20, le=80)
    min_future_value: Optional[int] = Field(None, ge=20, le=80)
    max_future_value: Optional[int] = Field(None, ge=20, le=80)
    risk_levels: Optional[List[str]] = Field(None, description="List of risk levels")

    # ML criteria
    min_success_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_success_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    prediction_types: Optional[List[str]] = Field(None, description="List of ML prediction types")

    # Performance improvement criteria
    improvement_lookback_days: Optional[int] = Field(30, ge=7, le=365)
    min_improvement_rate: Optional[float] = Field(None, ge=-1.0, le=1.0)

    # Search text
    search_query: Optional[str] = Field(None, max_length=100)

    # Pagination and sorting
    page: int = Field(1, ge=1)
    size: int = Field(25, ge=1, le=100)
    sort_by: str = Field("relevance", regex="^(relevance|name|age|eta_year|organization)$")


class AdvancedSearchResponse(BaseModel):
    """Response model for advanced search."""

    prospects: List[Dict[str, Any]]
    total_count: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    search_metadata: Dict[str, Any]


@router.post("/advanced", response_model=AdvancedSearchResponse)
@limiter.limit("30/minute")
async def advanced_search_prospects(
    search_request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Perform advanced prospect search with complex criteria combinations.

    Supports comprehensive filtering by statistics, scouting grades,
    ML predictions, timeline factors, and text search with relevance scoring.

    Performance characteristics:
    - Typical response time: 200-500ms for complex searches
    - Database queries: 3-5 optimized queries with proper indexing
    - Memory usage: ~1-2MB for standard result set

    Args:
        search_request: Advanced search criteria and parameters
        db: Database session
        user: Current authenticated user

    Returns:
        AdvancedSearchResponse with filtered prospects and metadata

    Raises:
        HTTPException: If search criteria validation fails or database error occurs
    """
    try:
        # Convert request to search criteria
        criteria = AdvancedSearchCriteria(
            # Statistical criteria
            min_batting_avg=search_request.min_batting_avg,
            max_batting_avg=search_request.max_batting_avg,
            min_on_base_pct=search_request.min_on_base_pct,
            max_on_base_pct=search_request.max_on_base_pct,
            min_slugging_pct=search_request.min_slugging_pct,
            max_slugging_pct=search_request.max_slugging_pct,
            min_era=search_request.min_era,
            max_era=search_request.max_era,
            min_whip=search_request.min_whip,
            max_whip=search_request.max_whip,
            min_woba=search_request.min_woba,
            max_woba=search_request.max_woba,
            min_wrc_plus=search_request.min_wrc_plus,
            max_wrc_plus=search_request.max_wrc_plus,

            # Basic criteria
            positions=search_request.positions,
            organizations=search_request.organizations,
            levels=search_request.levels,
            min_age=search_request.min_age,
            max_age=search_request.max_age,
            min_eta_year=search_request.min_eta_year,
            max_eta_year=search_request.max_eta_year,

            # Scouting criteria
            min_overall_grade=search_request.min_overall_grade,
            max_overall_grade=search_request.max_overall_grade,
            scouting_sources=search_request.scouting_sources,
            min_hit_grade=search_request.min_hit_grade,
            max_hit_grade=search_request.max_hit_grade,
            min_power_grade=search_request.min_power_grade,
            max_power_grade=search_request.max_power_grade,
            min_future_value=search_request.min_future_value,
            max_future_value=search_request.max_future_value,
            risk_levels=search_request.risk_levels,

            # ML criteria
            min_success_probability=search_request.min_success_probability,
            max_success_probability=search_request.max_success_probability,
            min_confidence_score=search_request.min_confidence_score,
            max_confidence_score=search_request.max_confidence_score,
            prediction_types=search_request.prediction_types,

            # Performance criteria
            improvement_lookback_days=search_request.improvement_lookback_days,
            min_improvement_rate=search_request.min_improvement_rate,

            # Text search
            search_query=search_request.search_query
        )

        # Perform search
        search_results = await AdvancedSearchService.advanced_search_prospects(
            db=db,
            criteria=criteria,
            user_id=user.id,
            page=search_request.page,
            size=search_request.size,
            sort_by=search_request.sort_by
        )

        # Convert prospects to dict format for response
        prospects_data = []
        for prospect in search_results["prospects"]:
            prospect_data = {
                "id": prospect.id,
                "mlb_id": prospect.mlb_id,
                "name": prospect.name,
                "position": prospect.position,
                "organization": prospect.organization,
                "level": prospect.level,
                "age": prospect.age,
                "eta_year": prospect.eta_year,

                # Latest stats if available
                "latest_stats": None,
                "scouting_grades": []
            }

            # Add latest stats
            if prospect.stats:
                latest_stats = max(prospect.stats, key=lambda s: s.date_recorded)
                prospect_data["latest_stats"] = {
                    "batting_avg": latest_stats.batting_avg,
                    "on_base_pct": latest_stats.on_base_pct,
                    "slugging_pct": latest_stats.slugging_pct,
                    "era": latest_stats.era,
                    "whip": latest_stats.whip,
                    "woba": latest_stats.woba,
                    "wrc_plus": latest_stats.wrc_plus,
                    "date_recorded": latest_stats.date_recorded.isoformat()
                }

            # Add scouting grades
            if prospect.scouting_grades:
                for grade in prospect.scouting_grades:
                    prospect_data["scouting_grades"].append({
                        "source": grade.source,
                        "overall": grade.overall,
                        "hit": grade.hit,
                        "power": grade.power,
                        "future_value": grade.future_value,
                        "risk": grade.risk
                    })

            prospects_data.append(prospect_data)

        # Build search metadata
        search_metadata = {
            "applied_filters": {
                "statistical": bool(any([
                    search_request.min_batting_avg, search_request.max_batting_avg,
                    search_request.min_on_base_pct, search_request.max_on_base_pct,
                    search_request.min_slugging_pct, search_request.max_slugging_pct,
                    search_request.min_era, search_request.max_era,
                    search_request.min_whip, search_request.max_whip,
                    search_request.min_woba, search_request.max_woba,
                    search_request.min_wrc_plus, search_request.max_wrc_plus
                ])),
                "scouting": bool(any([
                    search_request.min_overall_grade, search_request.max_overall_grade,
                    search_request.scouting_sources, search_request.min_hit_grade,
                    search_request.max_hit_grade, search_request.min_power_grade,
                    search_request.max_power_grade, search_request.min_future_value,
                    search_request.max_future_value, search_request.risk_levels
                ])),
                "ml_predictions": bool(any([
                    search_request.min_success_probability, search_request.max_success_probability,
                    search_request.min_confidence_score, search_request.max_confidence_score,
                    search_request.prediction_types
                ])),
                "basic_filters": bool(any([
                    search_request.positions, search_request.organizations,
                    search_request.levels, search_request.min_age,
                    search_request.max_age, search_request.min_eta_year,
                    search_request.max_eta_year
                ])),
                "text_search": bool(search_request.search_query)
            },
            "sort_by": search_request.sort_by,
            "search_complexity": len([
                f for f in [
                    search_request.min_batting_avg, search_request.max_batting_avg,
                    search_request.positions, search_request.organizations,
                    search_request.min_overall_grade, search_request.max_overall_grade,
                    search_request.min_success_probability, search_request.max_success_probability
                ] if f is not None
            ])
        }

        return AdvancedSearchResponse(
            prospects=prospects_data,
            total_count=search_results["total_count"],
            page=search_results["page"],
            size=search_results["size"],
            total_pages=search_results["total_pages"],
            has_next=search_results["has_next"],
            has_prev=search_results["has_prev"],
            search_metadata=search_metadata
        )

    except Exception as e:
        logger.error(f"Advanced search error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search request failed. Please try again or contact support."
        )


@router.get("/criteria/options")
@limiter.limit("60/minute")
async def get_search_criteria_options(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get available options for search criteria filters.

    Returns lists of available positions, organizations, levels,
    scouting sources, and other filter options for the advanced search form.

    Returns:
        Dict containing all available filter options
    """
    try:
        # This would typically query the database for distinct values
        # For now, returning static options based on the schema constraints
        return {
            "positions": ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH", "SP", "RP"],
            "scouting_sources": ["Fangraphs", "MLB Pipeline", "Baseball America", "Baseball Prospectus"],
            "risk_levels": ["Safe", "Moderate", "High", "Extreme"],
            "prediction_types": ["career_war", "debut_probability", "success_rating"],
            "levels": ["MLB", "AAA", "AA", "A+", "A", "A-", "Rookie"],
            "sort_options": ["relevance", "name", "age", "eta_year", "organization"],
            "grade_range": {"min": 20, "max": 80},
            "age_range": {"min": 16, "max": 35},
            "eta_range": {"min": 2024, "max": 2035}
        }

    except Exception as e:
        logger.error(f"Failed to get search criteria options: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load search options"
        )


class SavedSearchCreate(BaseModel):
    """Request model for creating a saved search."""
    search_name: str = Field(..., min_length=1, max_length=100)
    search_criteria: Dict[str, Any] = Field(..., description="Advanced search criteria")


class SavedSearchUpdate(BaseModel):
    """Request model for updating a saved search."""
    search_name: Optional[str] = Field(None, min_length=1, max_length=100)
    search_criteria: Optional[Dict[str, Any]] = Field(None, description="Advanced search criteria")


class SavedSearchResponse(BaseModel):
    """Response model for saved search."""
    id: int
    search_name: str
    search_criteria: Dict[str, Any]
    created_at: str
    last_used: str


@router.post("/saved", response_model=SavedSearchResponse)
@limiter.limit("20/minute")
async def create_saved_search(
    request: SavedSearchCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create a new saved search for the current user.

    Stores complex search criteria for quick re-use. Search names must be
    unique per user to avoid conflicts.

    Args:
        request: Saved search creation data
        db: Database session
        user: Current authenticated user

    Returns:
        SavedSearchResponse with created search details

    Raises:
        HTTPException: If search name already exists or creation fails
    """
    try:
        saved_search = await SavedSearchService.create_saved_search(
            db=db,
            user_id=user.id,
            search_name=request.search_name,
            search_criteria=request.search_criteria
        )

        return SavedSearchResponse(
            id=saved_search.id,
            search_name=saved_search.search_name,
            search_criteria=saved_search.search_criteria,
            created_at=saved_search.created_at.isoformat(),
            last_used=saved_search.last_used.isoformat()
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create saved search: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create saved search"
        )


@router.get("/saved", response_model=List[SavedSearchResponse])
@limiter.limit("60/minute")
async def get_saved_searches(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get all saved searches for the current user.

    Returns saved searches ordered by last used date, then creation date.
    Includes search criteria for immediate re-execution.

    Args:
        db: Database session
        user: Current authenticated user
        limit: Maximum number of searches to return

    Returns:
        List of SavedSearchResponse objects
    """
    try:
        saved_searches = await SavedSearchService.get_user_saved_searches(
            db=db,
            user_id=user.id,
            limit=limit
        )

        return [
            SavedSearchResponse(
                id=search.id,
                search_name=search.search_name,
                search_criteria=search.search_criteria,
                created_at=search.created_at.isoformat(),
                last_used=search.last_used.isoformat()
            )
            for search in saved_searches
        ]

    except Exception as e:
        logger.error(f"Failed to get saved searches: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load saved searches"
        )


@router.get("/saved/{search_id}", response_model=SavedSearchResponse)
@limiter.limit("60/minute")
async def get_saved_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get a specific saved search by ID.

    Updates the last_used timestamp when accessed for usage tracking.

    Args:
        search_id: Saved search ID
        db: Database session
        user: Current authenticated user

    Returns:
        SavedSearchResponse with search details

    Raises:
        HTTPException: If search not found or access denied
    """
    try:
        saved_search = await SavedSearchService.get_saved_search_by_id(
            db=db,
            user_id=user.id,
            search_id=search_id
        )

        if not saved_search:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )

        # Update last used timestamp
        await SavedSearchService.update_last_used(
            db=db,
            user_id=user.id,
            search_id=search_id
        )

        return SavedSearchResponse(
            id=saved_search.id,
            search_name=saved_search.search_name,
            search_criteria=saved_search.search_criteria,
            created_at=saved_search.created_at.isoformat(),
            last_used=saved_search.last_used.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get saved search {search_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load saved search"
        )


@router.put("/saved/{search_id}", response_model=SavedSearchResponse)
@limiter.limit("20/minute")
async def update_saved_search(
    search_id: int,
    request: SavedSearchUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Update a saved search.

    Allows updating search name and/or criteria. Search names must remain
    unique per user.

    Args:
        search_id: Saved search ID
        request: Update data
        db: Database session
        user: Current authenticated user

    Returns:
        SavedSearchResponse with updated search details

    Raises:
        HTTPException: If search not found, name conflict, or update fails
    """
    try:
        saved_search = await SavedSearchService.update_saved_search(
            db=db,
            user_id=user.id,
            search_id=search_id,
            search_name=request.search_name,
            search_criteria=request.search_criteria
        )

        if not saved_search:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )

        return SavedSearchResponse(
            id=saved_search.id,
            search_name=saved_search.search_name,
            search_criteria=saved_search.search_criteria,
            created_at=saved_search.created_at.isoformat(),
            last_used=saved_search.last_used.isoformat()
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update saved search {search_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update saved search"
        )


@router.delete("/saved/{search_id}")
@limiter.limit("20/minute")
async def delete_saved_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Delete a saved search.

    Permanently removes the saved search from the user's collection.

    Args:
        search_id: Saved search ID
        db: Database session
        user: Current authenticated user

    Returns:
        Success message

    Raises:
        HTTPException: If search not found or deletion fails
    """
    try:
        deleted = await SavedSearchService.delete_saved_search(
            db=db,
            user_id=user.id,
            search_id=search_id
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved search not found"
            )

        return {"message": "Saved search deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete saved search {search_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete saved search"
        )


class SearchHistoryResponse(BaseModel):
    """Response model for search history entry."""
    id: int
    search_query: Optional[str]
    search_criteria: Optional[Dict[str, Any]]
    results_count: Optional[int]
    searched_at: str


class ProspectViewResponse(BaseModel):
    """Response model for prospect view entry."""
    id: int
    prospect_id: int
    prospect_name: str
    viewed_at: str
    view_duration: Optional[int]


@router.get("/history", response_model=List[SearchHistoryResponse])
@limiter.limit("60/minute")
async def get_search_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get user's search history.

    Returns recent searches ordered by timestamp, including search criteria
    and result counts for pattern analysis and quick re-execution.

    Args:
        db: Database session
        user: Current authenticated user
        limit: Maximum number of history entries to return

    Returns:
        List of SearchHistoryResponse objects
    """
    try:
        from sqlalchemy import select, desc

        query = select(UserSearchHistory).where(
            UserSearchHistory.user_id == user.id
        ).order_by(
            desc(UserSearchHistory.searched_at)
        ).limit(limit)

        result = await db.execute(query)
        history_entries = result.scalars().all()

        return [
            SearchHistoryResponse(
                id=entry.id,
                search_query=entry.search_query,
                search_criteria=entry.search_criteria,
                results_count=entry.results_count,
                searched_at=entry.searched_at.isoformat()
            )
            for entry in history_entries
        ]

    except Exception as e:
        logger.error(f"Failed to get search history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load search history"
        )


@router.get("/recently-viewed", response_model=List[ProspectViewResponse])
@limiter.limit("60/minute")
async def get_recently_viewed_prospects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(25, ge=1, le=100)
):
    """
    Get user's recently viewed prospects.

    Returns prospects the user has recently viewed, ordered by timestamp,
    for quick access and research continuity.

    Args:
        db: Database session
        user: Current authenticated user
        limit: Maximum number of viewed prospects to return

    Returns:
        List of ProspectViewResponse objects
    """
    try:
        from sqlalchemy import select, desc
        from app.db.models import Prospect

        query = select(UserProspectView, Prospect.name).join(
            Prospect, UserProspectView.prospect_id == Prospect.id
        ).where(
            UserProspectView.user_id == user.id
        ).order_by(
            desc(UserProspectView.viewed_at)
        ).limit(limit)

        result = await db.execute(query)
        view_entries = result.all()

        return [
            ProspectViewResponse(
                id=view_entry[0].id,
                prospect_id=view_entry[0].prospect_id,
                prospect_name=view_entry[1],
                viewed_at=view_entry[0].viewed_at.isoformat(),
                view_duration=view_entry[0].view_duration
            )
            for view_entry in view_entries
        ]

    except Exception as e:
        logger.error(f"Failed to get recently viewed prospects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load recently viewed prospects"
        )


@router.post("/track-view")
@limiter.limit("100/minute")
async def track_prospect_view(
    prospect_id: int,
    view_duration: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Track a prospect view for user analytics.

    Records when a user views a prospect for search result optimization
    and personalization features.

    Args:
        prospect_id: ID of the viewed prospect
        view_duration: Optional duration of view in seconds
        db: Database session
        user: Current authenticated user

    Returns:
        Success message
    """
    try:
        # Create prospect view record
        prospect_view = UserProspectView(
            user_id=user.id,
            prospect_id=prospect_id,
            view_duration=view_duration
        )

        db.add(prospect_view)
        await db.commit()

        return {"message": "Prospect view tracked successfully"}

    except Exception as e:
        logger.error(f"Failed to track prospect view: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track prospect view"
        )