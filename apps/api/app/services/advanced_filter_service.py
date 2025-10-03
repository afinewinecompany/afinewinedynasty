"""
Advanced Filtering Service for Premium Users

Provides complex query building and multi-criteria filtering capabilities
for premium subscription users.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, and_, or_, func, desc, asc, not_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
import logging

from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction
from app.core.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class AdvancedFilterService:
    """
    Service for building complex prospect queries with advanced filtering.

    Features:
    - Multi-criteria filtering with AND/OR operations
    - Range filters for numerical values
    - Statistical filters (batting avg, ERA, etc.)
    - ML prediction filters
    - Scouting grade filters
    - Custom filter combinations
    """

    @staticmethod
    def build_filter_query(
        base_query: Select,
        filters: Dict[str, Any],
        operator: str = "AND"
    ) -> Select:
        """
        Build a complex filter query from filter criteria.

        Args:
            base_query: Base SQLAlchemy query
            filters: Dictionary of filter criteria
            operator: Logical operator for combining filters ("AND" or "OR")

        Returns:
            Modified query with filters applied
        """
        filter_conditions = []

        # Basic filters
        if filters.get("position"):
            positions = filters["position"]
            if isinstance(positions, list):
                filter_conditions.append(Prospect.position.in_(positions))
            else:
                filter_conditions.append(Prospect.position == positions)

        if filters.get("organization"):
            organizations = filters["organization"]
            if isinstance(organizations, list):
                filter_conditions.append(Prospect.organization.in_(organizations))
            else:
                filter_conditions.append(Prospect.organization == organizations)

        if filters.get("level"):
            levels = filters["level"]
            if isinstance(levels, list):
                filter_conditions.append(Prospect.level.in_(levels))
            else:
                filter_conditions.append(Prospect.level == levels)

        # Range filters
        if filters.get("age_min") is not None:
            filter_conditions.append(Prospect.age >= filters["age_min"])

        if filters.get("age_max") is not None:
            filter_conditions.append(Prospect.age <= filters["age_max"])

        if filters.get("eta_min") is not None:
            filter_conditions.append(Prospect.eta_year >= filters["eta_min"])

        if filters.get("eta_max") is not None:
            filter_conditions.append(Prospect.eta_year <= filters["eta_max"])

        # Draft filters
        if filters.get("draft_year_min") is not None:
            filter_conditions.append(Prospect.draft_year >= filters["draft_year_min"])

        if filters.get("draft_year_max") is not None:
            filter_conditions.append(Prospect.draft_year <= filters["draft_year_max"])

        if filters.get("draft_round_max") is not None:
            filter_conditions.append(
                and_(
                    Prospect.draft_round.isnot(None),
                    Prospect.draft_round <= filters["draft_round_max"]
                )
            )

        # Apply filters based on operator
        if filter_conditions:
            if operator.upper() == "OR":
                base_query = base_query.where(or_(*filter_conditions))
            else:
                base_query = base_query.where(and_(*filter_conditions))

        return base_query

    @staticmethod
    async def apply_statistical_filters(
        db: AsyncSession,
        prospect_ids: List[int],
        stat_filters: Dict[str, Any]
    ) -> List[int]:
        """
        Filter prospects based on statistical criteria.

        Args:
            db: Database session
            prospect_ids: List of prospect IDs to filter
            stat_filters: Statistical filter criteria

        Returns:
            Filtered list of prospect IDs
        """
        if not stat_filters or not prospect_ids:
            return prospect_ids

        # Build stats query
        query = select(ProspectStats.prospect_id).where(
            ProspectStats.prospect_id.in_(prospect_ids)
        )

        # Apply stat filters
        stat_conditions = []

        # Hitting stats
        if stat_filters.get("batting_avg_min") is not None:
            stat_conditions.append(
                ProspectStats.batting_avg >= stat_filters["batting_avg_min"]
            )

        if stat_filters.get("batting_avg_max") is not None:
            stat_conditions.append(
                ProspectStats.batting_avg <= stat_filters["batting_avg_max"]
            )

        if stat_filters.get("ops_min") is not None:
            # OPS = OBP + SLG
            stat_conditions.append(
                (ProspectStats.on_base_pct + ProspectStats.slugging_pct) >= stat_filters["ops_min"]
            )

        if stat_filters.get("home_runs_min") is not None:
            stat_conditions.append(
                ProspectStats.home_runs >= stat_filters["home_runs_min"]
            )

        # Pitching stats
        if stat_filters.get("era_max") is not None:
            stat_conditions.append(
                ProspectStats.era <= stat_filters["era_max"]
            )

        if stat_filters.get("whip_max") is not None:
            stat_conditions.append(
                ProspectStats.whip <= stat_filters["whip_max"]
            )

        if stat_filters.get("k_per_9_min") is not None:
            stat_conditions.append(
                ProspectStats.k_per_9 >= stat_filters["k_per_9_min"]
            )

        # Apply conditions
        if stat_conditions:
            query = query.where(and_(*stat_conditions))

        # Get latest stats per prospect
        subquery = select(
            ProspectStats.prospect_id,
            func.max(ProspectStats.date_recorded).label("latest_date")
        ).where(
            ProspectStats.prospect_id.in_(prospect_ids)
        ).group_by(ProspectStats.prospect_id).subquery()

        query = query.join(
            subquery,
            and_(
                ProspectStats.prospect_id == subquery.c.prospect_id,
                ProspectStats.date_recorded == subquery.c.latest_date
            )
        )

        result = await db.execute(query)
        filtered_ids = [row.prospect_id for row in result]

        return filtered_ids

    @staticmethod
    async def apply_ml_prediction_filters(
        db: AsyncSession,
        prospect_ids: List[int],
        ml_filters: Dict[str, Any]
    ) -> List[int]:
        """
        Filter prospects based on ML prediction criteria.

        Args:
            db: Database session
            prospect_ids: List of prospect IDs to filter
            ml_filters: ML prediction filter criteria

        Returns:
            Filtered list of prospect IDs
        """
        if not ml_filters or not prospect_ids:
            return prospect_ids

        query = select(MLPrediction.prospect_id).where(
            and_(
                MLPrediction.prospect_id.in_(prospect_ids),
                MLPrediction.prediction_type == 'success_rating'
            )
        )

        # Apply ML filters
        ml_conditions = []

        if ml_filters.get("success_probability_min") is not None:
            ml_conditions.append(
                MLPrediction.success_probability >= ml_filters["success_probability_min"]
            )

        if ml_filters.get("success_probability_max") is not None:
            ml_conditions.append(
                MLPrediction.success_probability <= ml_filters["success_probability_max"]
            )

        if ml_filters.get("confidence_levels"):
            confidence_levels = ml_filters["confidence_levels"]
            if isinstance(confidence_levels, list):
                ml_conditions.append(
                    MLPrediction.confidence_level.in_(confidence_levels)
                )
            else:
                ml_conditions.append(
                    MLPrediction.confidence_level == confidence_levels
                )

        if ml_conditions:
            query = query.where(and_(*ml_conditions))

        result = await db.execute(query)
        filtered_ids = [row.prospect_id for row in result]

        return filtered_ids

    @staticmethod
    async def apply_scouting_grade_filters(
        db: AsyncSession,
        prospect_ids: List[int],
        grade_filters: Dict[str, Any]
    ) -> List[int]:
        """
        Filter prospects based on scouting grade criteria.

        Args:
            db: Database session
            prospect_ids: List of prospect IDs to filter
            grade_filters: Scouting grade filter criteria

        Returns:
            Filtered list of prospect IDs
        """
        if not grade_filters or not prospect_ids:
            return prospect_ids

        query = select(ScoutingGrades.prospect_id).where(
            ScoutingGrades.prospect_id.in_(prospect_ids)
        )

        # Apply grade filters
        grade_conditions = []

        if grade_filters.get("overall_grade_min") is not None:
            grade_conditions.append(
                ScoutingGrades.overall >= grade_filters["overall_grade_min"]
            )

        if grade_filters.get("future_value_min") is not None:
            grade_conditions.append(
                ScoutingGrades.future_value >= grade_filters["future_value_min"]
            )

        if grade_filters.get("sources"):
            sources = grade_filters["sources"]
            if isinstance(sources, list):
                grade_conditions.append(ScoutingGrades.source.in_(sources))
            else:
                grade_conditions.append(ScoutingGrades.source == sources)

        # Tool grades (hit, power, speed, field, arm)
        for tool in ["hit", "power", "speed", "field", "arm"]:
            min_key = f"{tool}_grade_min"
            if grade_filters.get(min_key) is not None:
                grade_conditions.append(
                    getattr(ScoutingGrades, tool) >= grade_filters[min_key]
                )

        if grade_conditions:
            query = query.where(and_(*grade_conditions))

        result = await db.execute(query)
        filtered_ids = list(set([row.prospect_id for row in result]))

        return filtered_ids

    @staticmethod
    def build_complex_filter_expression(
        filter_groups: List[Dict[str, Any]]
    ) -> Tuple[List, str]:
        """
        Build complex filter expressions with nested AND/OR operations.

        Args:
            filter_groups: List of filter groups with operators

        Returns:
            Tuple of (filter conditions, primary operator)

        Example:
            filter_groups = [
                {
                    "operator": "AND",
                    "filters": {
                        "position": ["SS", "2B"],
                        "age_max": 21
                    }
                },
                {
                    "operator": "OR",
                    "filters": {
                        "organization": "NYY",
                        "level": "AAA"
                    }
                }
            ]
        """
        if not filter_groups:
            return [], "AND"

        group_conditions = []

        for group in filter_groups:
            operator = group.get("operator", "AND").upper()
            filters = group.get("filters", {})

            conditions = []

            # Build conditions for this group
            for key, value in filters.items():
                if key == "position" and value:
                    if isinstance(value, list):
                        conditions.append(Prospect.position.in_(value))
                    else:
                        conditions.append(Prospect.position == value)

                elif key == "organization" and value:
                    if isinstance(value, list):
                        conditions.append(Prospect.organization.in_(value))
                    else:
                        conditions.append(Prospect.organization == value)

                elif key == "level" and value:
                    if isinstance(value, list):
                        conditions.append(Prospect.level.in_(value))
                    else:
                        conditions.append(Prospect.level == value)

                elif key == "age_min" and value is not None:
                    conditions.append(Prospect.age >= value)

                elif key == "age_max" and value is not None:
                    conditions.append(Prospect.age <= value)

                elif key == "eta_min" and value is not None:
                    conditions.append(Prospect.eta_year >= value)

                elif key == "eta_max" and value is not None:
                    conditions.append(Prospect.eta_year <= value)

            # Combine conditions for this group
            if conditions:
                if operator == "OR":
                    group_conditions.append(or_(*conditions))
                else:
                    group_conditions.append(and_(*conditions))

        # Primary operator for combining groups is AND by default
        return group_conditions, "AND"

    @staticmethod
    async def execute_advanced_search(
        db: AsyncSession,
        filter_config: Dict[str, Any],
        limit: int = 500
    ) -> List[Prospect]:
        """
        Execute an advanced search with complex filtering.

        Args:
            db: Database session
            filter_config: Complete filter configuration
            limit: Maximum number of results

        Returns:
            List of filtered prospects
        """
        # Generate cache key
        import json
        cache_key = f"advanced_filter:{json.dumps(filter_config, sort_keys=True)}"

        # Check cache
        cached_result = await cache_manager.get_cached_features(cache_key)
        if cached_result:
            logger.info(f"Cache hit for advanced filter: {cache_key}")
            return cached_result

        # Build base query
        query = select(Prospect)

        # Apply basic filters
        if filter_config.get("basic_filters"):
            query = AdvancedFilterService.build_filter_query(
                query,
                filter_config["basic_filters"],
                filter_config.get("operator", "AND")
            )

        # Apply complex filter groups
        if filter_config.get("filter_groups"):
            conditions, operator = AdvancedFilterService.build_complex_filter_expression(
                filter_config["filter_groups"]
            )
            if conditions:
                if operator == "OR":
                    query = query.where(or_(*conditions))
                else:
                    query = query.where(and_(*conditions))

        # Execute initial query
        result = await db.execute(query.limit(limit * 2))  # Get extra for filtering
        prospects = result.scalars().all()
        prospect_ids = [p.id for p in prospects]

        # Apply statistical filters
        if filter_config.get("stat_filters"):
            prospect_ids = await AdvancedFilterService.apply_statistical_filters(
                db, prospect_ids, filter_config["stat_filters"]
            )

        # Apply ML prediction filters
        if filter_config.get("ml_filters"):
            prospect_ids = await AdvancedFilterService.apply_ml_prediction_filters(
                db, prospect_ids, filter_config["ml_filters"]
            )

        # Apply scouting grade filters
        if filter_config.get("grade_filters"):
            prospect_ids = await AdvancedFilterService.apply_scouting_grade_filters(
                db, prospect_ids, filter_config["grade_filters"]
            )

        # Filter final prospect list
        filtered_prospects = [p for p in prospects if p.id in prospect_ids][:limit]

        # Cache results for 15 minutes
        await cache_manager.cache_prospect_features(
            cache_key, filtered_prospects, ttl=900
        )

        return filtered_prospects