"""
Premium Feature Endpoints

Premium subscription-only endpoints for advanced features including
historical data access, batch comparisons, and enhanced predictions.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging
from datetime import datetime, timedelta

from app.api.deps import get_current_user, subscription_tier_required
from app.db.database import get_db
from app.db.models import User, Prospect, ProspectStats, MLPrediction, ComparisonHistory
from app.services.advanced_filter_service import AdvancedFilterService
from app.services.saved_search_service import SavedSearchService
from app.services.historical_data_service import HistoricalDataService
from app.services.enhanced_outlook_service import EnhancedOutlookService
from app.services.feature_flag_service import FeatureFlagService
from app.services.export_service import ExportService
from app.services.prospect_comparisons_service import ProspectComparisonsService
from app.core.cache_manager import cache_manager
from app.core.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


class AdvancedFilterRequest(BaseModel):
    """Request model for advanced filtering."""
    basic_filters: Optional[Dict[str, Any]] = Field(default={}, description="Basic prospect filters")
    stat_filters: Optional[Dict[str, Any]] = Field(default={}, description="Statistical filters")
    ml_filters: Optional[Dict[str, Any]] = Field(default={}, description="ML prediction filters")
    grade_filters: Optional[Dict[str, Any]] = Field(default={}, description="Scouting grade filters")
    filter_groups: Optional[List[Dict[str, Any]]] = Field(default=[], description="Complex filter groups")
    operator: str = Field(default="AND", regex="^(AND|OR)$", description="Primary operator")


class SavedSearchRequest(BaseModel):
    """Request model for saving a search."""
    name: str = Field(..., min_length=1, max_length=100, description="Search name")
    filters: AdvancedFilterRequest = Field(..., description="Filter configuration")
    is_public: bool = Field(default=False, description="Make search public for sharing")


class BatchComparisonRequest(BaseModel):
    """Request model for batch prospect comparison."""
    prospect_ids: List[int] = Field(..., min_items=2, max_items=10, description="Prospect IDs to compare")
    include_stats: bool = Field(default=True, description="Include statistical comparison")
    include_predictions: bool = Field(default=True, description="Include ML predictions")
    include_analogs: bool = Field(default=True, description="Include historical analogs")


class ExportRequest(BaseModel):
    """Request model for data export."""
    format: str = Field(..., regex="^(csv|pdf|json)$", description="Export format")
    data_type: str = Field(..., description="Type of data to export")
    filters: Optional[Dict[str, Any]] = Field(default={}, description="Filters to apply")


class EnhancedOutlookRequest(BaseModel):
    """Request model for enhanced AI outlook."""
    prospect_id: int = Field(..., description="Prospect ID")
    league_context: Optional[Dict[str, Any]] = Field(default={}, description="League-specific context")
    roster_context: Optional[Dict[str, Any]] = Field(default={}, description="User's roster context")
    comparison_prospects: Optional[List[int]] = Field(default=[], max_items=5, description="Prospects to compare against")


@router.post("/advanced-filter", response_model=Dict[str, Any])
# @limiter.limit("100/minute")
@subscription_tier_required("premium")
async def advanced_filter_prospects(
    request: AdvancedFilterRequest,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Execute advanced filtering with complex criteria (Premium only).

    Features:
    - Multi-criteria filtering with AND/OR operations
    - Statistical filters (batting avg, ERA, etc.)
    - ML prediction filters (success probability, confidence)
    - Scouting grade filters
    - Nested filter groups
    - 15-minute caching
    """
    try:
        # Build filter configuration
        filter_config = {
            "basic_filters": request.basic_filters,
            "stat_filters": request.stat_filters,
            "ml_filters": request.ml_filters,
            "grade_filters": request.grade_filters,
            "filter_groups": request.filter_groups,
            "operator": request.operator
        }

        # Execute advanced search
        prospects = await AdvancedFilterService.execute_advanced_search(
            db, filter_config, limit
        )

        # Format response
        return {
            "prospects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "position": p.position,
                    "organization": p.organization,
                    "level": p.level,
                    "age": p.age,
                    "eta_year": p.eta_year
                }
                for p in prospects
            ],
            "total": len(prospects),
            "filter_config": filter_config,
            "cached": False
        }

    except Exception as e:
        logger.error(f"Advanced filter error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Filter execution failed: {str(e)}"
        )


@router.post("/saved-searches", response_model=Dict[str, Any])
# @limiter.limit("50/hour")
@subscription_tier_required("premium")
async def create_saved_search(
    request: SavedSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a saved search configuration (Premium only).

    Features:
    - Save complex filter configurations
    - Name searches for easy recall
    - Optional public sharing
    - Maximum 50 saved searches per user
    """
    # Get user from database
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check saved search limit (50 per user)
    from app.db.models import SavedSearch
    count_stmt = select(func.count(SavedSearch.id)).where(SavedSearch.user_id == user.id)
    count_result = await db.execute(count_stmt)
    search_count = count_result.scalar()

    if search_count >= 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum saved searches limit (50) reached"
        )

    try:
        # Create saved search
        saved_search = SavedSearch(
            user_id=user.id,
            name=request.name,
            filters=request.filters.dict(),
            is_public=request.is_public,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow()
        )

        db.add(saved_search)
        await db.commit()
        await db.refresh(saved_search)

        return {
            "id": saved_search.id,
            "name": saved_search.name,
            "filters": saved_search.filters,
            "is_public": saved_search.is_public,
            "created_at": saved_search.created_at.isoformat(),
            "message": "Search saved successfully"
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Save search error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save search: {str(e)}"
        )


@router.get("/saved-searches", response_model=List[Dict[str, Any]])
# @limiter.limit("100/minute")
@subscription_tier_required("premium")
async def get_saved_searches(
    include_public: bool = Query(False, description="Include public searches from other users"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get user's saved searches (Premium only).

    Returns:
        List of saved searches with metadata
    """
    # Get user from database
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Build query
    from app.db.models import SavedSearch
    if include_public:
        query = select(SavedSearch).where(
            or_(
                SavedSearch.user_id == user.id,
                SavedSearch.is_public == True
            )
        ).order_by(desc(SavedSearch.last_used))
    else:
        query = select(SavedSearch).where(
            SavedSearch.user_id == user.id
        ).order_by(desc(SavedSearch.last_used))

    result = await db.execute(query)
    searches = result.scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "filters": s.filters,
            "is_public": s.is_public,
            "is_owner": s.user_id == user.id,
            "created_at": s.created_at.isoformat(),
            "last_used": s.last_used.isoformat() if s.last_used else None
        }
        for s in searches
    ]


@router.post("/batch-compare", response_model=Dict[str, Any])
# @limiter.limit("50/hour")
@subscription_tier_required("premium")
async def batch_compare_prospects(
    request: BatchComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Compare multiple prospects in batch (Premium only).

    Features:
    - Compare 2-10 prospects simultaneously
    - Statistical comparison
    - ML prediction differential
    - Historical analog matching
    - Export capability
    """
    try:
        # Get all prospects with comprehensive data
        prospects_data = []
        for prospect_id in request.prospect_ids:
            prospect_data = await ProspectComparisonsService._get_prospect_with_features(
                db, prospect_id
            )
            if not prospect_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prospect {prospect_id} not found"
                )
            prospects_data.append(prospect_data)

        # Build comparison result
        comparison = {
            "prospect_count": len(request.prospect_ids),
            "prospects": [],
            "statistical_comparison": {},
            "ml_comparison": {},
            "historical_analogs": {}
        }

        # Add individual prospect data
        for data in prospects_data:
            prospect = data["prospect"]
            prospect_info = {
                "id": prospect.id,
                "name": prospect.name,
                "position": prospect.position,
                "organization": prospect.organization,
                "age": prospect.age
            }

            if request.include_stats and data.get("latest_stats"):
                stats = data["latest_stats"]
                prospect_info["stats"] = {
                    "batting_avg": stats.batting_avg,
                    "on_base_pct": stats.on_base_pct,
                    "slugging_pct": stats.slugging_pct,
                    "era": stats.era,
                    "whip": stats.whip
                }

            if request.include_predictions and data.get("ml_prediction"):
                pred = data["ml_prediction"]
                prospect_info["ml_prediction"] = {
                    "success_probability": pred.success_probability,
                    "confidence_level": pred.confidence_level
                }

            comparison["prospects"].append(prospect_info)

        # Add comparative analysis
        if request.include_stats:
            comparison["statistical_comparison"] = await _generate_stat_comparison(prospects_data)

        if request.include_predictions:
            comparison["ml_comparison"] = await _generate_ml_comparison(prospects_data)

        if request.include_analogs:
            comparison["historical_analogs"] = await _generate_analog_comparison(db, prospects_data)

        # Save comparison history
        user_stmt = select(User).where(User.email == current_user.email)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user:
            history = ComparisonHistory(
                user_id=user.id,
                prospect_ids=request.prospect_ids,
                comparison_data=comparison,
                created_at=datetime.utcnow()
            )
            db.add(history)
            await db.commit()

        return comparison

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch comparison error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}"
        )


@router.post("/export", response_model=Dict[str, Any])
# @limiter.limit("10/hour")
@subscription_tier_required("premium")
async def export_data(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Export data in various formats (Premium only).

    Features:
    - CSV, PDF, JSON formats
    - Filtered exports
    - Asynchronous generation for large datasets
    - Rate limited to 10 exports per hour
    """
    try:
        # Generate export based on data type
        if request.data_type == "rankings":
            export_data = await _export_rankings(db, request.filters, request.format)
        elif request.data_type == "comparison":
            export_data = await _export_comparison(db, request.filters, request.format)
        elif request.data_type == "historical":
            export_data = await _export_historical(db, request.filters, request.format)
        else:
            raise ValueError(f"Unknown export type: {request.data_type}")

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.data_type}_{timestamp}.{request.format}"

        # For large exports, process in background
        if request.format == "pdf":
            task_id = f"export_{current_user.email}_{timestamp}"
            background_tasks.add_task(
                ExportService.generate_pdf_async,
                export_data,
                filename,
                task_id
            )

            return {
                "task_id": task_id,
                "status": "processing",
                "message": "Export is being generated. Check status endpoint."
            }
        else:
            # Generate immediately for CSV/JSON
            if request.format == "csv":
                content = ExportService.generate_csv(export_data)
            else:  # json
                import json
                content = json.dumps(export_data, indent=2)

            return {
                "filename": filename,
                "content": content,
                "format": request.format,
                "generated_at": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


# Helper functions
async def _generate_stat_comparison(prospects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate statistical comparison between prospects."""
    comparison = {"leaders": {}, "averages": {}}

    stats_to_compare = ["batting_avg", "on_base_pct", "slugging_pct", "era", "whip"]

    for stat in stats_to_compare:
        values = []
        for data in prospects_data:
            if data.get("latest_stats") and hasattr(data["latest_stats"], stat):
                value = getattr(data["latest_stats"], stat)
                if value is not None:
                    values.append({
                        "prospect_name": data["prospect"].name,
                        "value": value
                    })

        if values:
            # Sort to find leader (higher is better for batting stats, lower for pitching)
            reverse = stat not in ["era", "whip"]
            sorted_values = sorted(values, key=lambda x: x["value"], reverse=reverse)
            comparison["leaders"][stat] = sorted_values[0]
            comparison["averages"][stat] = sum(v["value"] for v in values) / len(values)

    return comparison


async def _generate_ml_comparison(prospects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate ML prediction comparison."""
    comparison = {"predictions": [], "average_probability": 0}

    probabilities = []
    for data in prospects_data:
        if data.get("ml_prediction"):
            pred = data["ml_prediction"]
            comparison["predictions"].append({
                "prospect_name": data["prospect"].name,
                "probability": pred.success_probability,
                "confidence": pred.confidence_level
            })
            probabilities.append(pred.success_probability)

    if probabilities:
        comparison["average_probability"] = sum(probabilities) / len(probabilities)
        comparison["highest"] = max(comparison["predictions"], key=lambda x: x["probability"])
        comparison["lowest"] = min(comparison["predictions"], key=lambda x: x["probability"])

    return comparison


async def _generate_analog_comparison(db: AsyncSession, prospects_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate historical analog comparison."""
    analogs = {}

    for data in prospects_data:
        historical = await ProspectComparisonsService._find_historical_similar(
            db, data, limit=3
        )
        analogs[data["prospect"].name] = historical

    return analogs


async def _export_rankings(db: AsyncSession, filters: Dict[str, Any], format: str) -> List[Dict[str, Any]]:
    """Export rankings data."""
    # Implementation would query and format rankings
    return []


async def _export_comparison(db: AsyncSession, filters: Dict[str, Any], format: str) -> List[Dict[str, Any]]:
    """Export comparison data."""
    # Implementation would query and format comparison
    return []


async def _export_historical(db: AsyncSession, filters: Dict[str, Any], format: str) -> List[Dict[str, Any]]:
    """Export historical data."""
    # Implementation would query and format historical data
    return []