"""
Historical Data Service for Premium Users

Provides access to time-series data and trend analysis for prospects.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
import logging
import numpy as np
from collections import defaultdict

from app.db.models import Prospect, ProspectStats, MLPrediction, ScoutingGrades
from app.core.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """
    Service for accessing and analyzing historical prospect data.

    Features:
    - Time-series performance data
    - Trend analysis and trajectories
    - Season-over-season comparisons
    - Performance progression tracking
    - Historical prediction accuracy
    """

    @staticmethod
    async def get_prospect_historical_stats(
        db: AsyncSession,
        prospect_id: int,
        seasons: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get historical statistical data for a prospect.

        Args:
            db: Database session
            prospect_id: Prospect ID
            seasons: Number of seasons to retrieve (default: all)
            start_date: Start date for data range
            end_date: End date for data range

        Returns:
            Dictionary with historical stats organized by season/level
        """
        # Generate cache key
        cache_key = f"historical_stats:{prospect_id}:{seasons}:{start_date}:{end_date}"
        cached = await cache_manager.get_cached_features(cache_key)
        if cached:
            return cached

        # Build query
        query = select(ProspectStats).where(
            ProspectStats.prospect_id == prospect_id
        )

        # Apply date filters
        if start_date:
            query = query.where(ProspectStats.date_recorded >= start_date)
        if end_date:
            query = query.where(ProspectStats.date_recorded <= end_date)

        # Order by date
        query = query.order_by(desc(ProspectStats.date_recorded))

        # Execute query
        result = await db.execute(query)
        stats = result.scalars().all()

        # Organize by season and level
        historical_data = {
            "prospect_id": prospect_id,
            "stats_by_season": defaultdict(lambda: defaultdict(list)),
            "levels_played": set(),
            "total_games": 0,
            "date_range": {
                "start": None,
                "end": None
            }
        }

        for stat in stats:
            season = stat.season or datetime.now().year
            level = stat.level or "Unknown"

            historical_data["stats_by_season"][season][level].append({
                "date": stat.date_recorded.isoformat(),
                "games_played": stat.games_played,
                "batting_avg": stat.batting_avg,
                "on_base_pct": stat.on_base_pct,
                "slugging_pct": stat.slugging_pct,
                "ops": (stat.on_base_pct or 0) + (stat.slugging_pct or 0),
                "home_runs": stat.home_runs,
                "rbi": stat.rbi,
                "stolen_bases": stat.stolen_bases,
                "era": stat.era,
                "whip": stat.whip,
                "k_per_9": stat.k_per_9,
                "bb_per_9": stat.bb_per_9,
                "fip": stat.fip,
                "war": stat.war
            })

            historical_data["levels_played"].add(level)
            historical_data["total_games"] += stat.games_played or 0

            # Update date range
            if not historical_data["date_range"]["start"] or stat.date_recorded < datetime.fromisoformat(historical_data["date_range"]["start"]):
                historical_data["date_range"]["start"] = stat.date_recorded.isoformat()
            if not historical_data["date_range"]["end"] or stat.date_recorded > datetime.fromisoformat(historical_data["date_range"]["end"]):
                historical_data["date_range"]["end"] = stat.date_recorded.isoformat()

        # Convert defaultdict to regular dict for JSON serialization
        historical_data["stats_by_season"] = dict(historical_data["stats_by_season"])
        for season in historical_data["stats_by_season"]:
            historical_data["stats_by_season"][season] = dict(historical_data["stats_by_season"][season])
        historical_data["levels_played"] = list(historical_data["levels_played"])

        # Apply season limit if specified
        if seasons and len(historical_data["stats_by_season"]) > seasons:
            sorted_seasons = sorted(historical_data["stats_by_season"].keys(), reverse=True)[:seasons]
            historical_data["stats_by_season"] = {
                s: historical_data["stats_by_season"][s]
                for s in sorted_seasons
            }

        # Cache for 24 hours
        await cache_manager.cache_prospect_features(cache_key, historical_data, ttl=86400)

        return historical_data

    @staticmethod
    async def calculate_performance_trajectory(
        db: AsyncSession,
        prospect_id: int,
        metric: str = "batting_avg"
    ) -> Dict[str, Any]:
        """
        Calculate performance trajectory and trend for a specific metric.

        Args:
            db: Database session
            prospect_id: Prospect ID
            metric: Metric to analyze (e.g., 'batting_avg', 'era', 'ops')

        Returns:
            Dictionary with trend analysis and trajectory data
        """
        # Get historical stats
        query = select(ProspectStats).where(
            ProspectStats.prospect_id == prospect_id
        ).order_by(asc(ProspectStats.date_recorded))

        result = await db.execute(query)
        stats = result.scalars().all()

        if not stats:
            return {
                "prospect_id": prospect_id,
                "metric": metric,
                "trajectory": "insufficient_data"
            }

        # Extract metric values and dates
        data_points = []
        for stat in stats:
            if hasattr(stat, metric):
                value = getattr(stat, metric)
                if value is not None:
                    data_points.append({
                        "date": stat.date_recorded,
                        "value": value,
                        "level": stat.level,
                        "season": stat.season or stat.date_recorded.year
                    })

        if len(data_points) < 3:
            return {
                "prospect_id": prospect_id,
                "metric": metric,
                "trajectory": "insufficient_data",
                "data_points": data_points
            }

        # Calculate trend using linear regression
        x = np.arange(len(data_points))
        y = np.array([dp["value"] for dp in data_points])

        # Fit linear trend
        coefficients = np.polyfit(x, y, 1)
        slope = coefficients[0]
        intercept = coefficients[1]

        # Calculate R-squared
        y_pred = np.polyval(coefficients, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Determine trajectory direction
        if abs(slope) < 0.001:
            trajectory = "stable"
        elif slope > 0:
            trajectory = "improving" if metric not in ["era", "whip", "bb_per_9"] else "declining"
        else:
            trajectory = "declining" if metric not in ["era", "whip", "bb_per_9"] else "improving"

        # Calculate recent trend (last 20% of data points)
        recent_size = max(3, len(data_points) // 5)
        recent_points = data_points[-recent_size:]
        recent_x = np.arange(len(recent_points))
        recent_y = np.array([dp["value"] for dp in recent_points])
        recent_slope = np.polyfit(recent_x, recent_y, 1)[0]

        # Determine recent trajectory
        if abs(recent_slope) < 0.001:
            recent_trajectory = "stable"
        elif recent_slope > 0:
            recent_trajectory = "improving" if metric not in ["era", "whip", "bb_per_9"] else "declining"
        else:
            recent_trajectory = "declining" if metric not in ["era", "whip", "bb_per_9"] else "improving"

        return {
            "prospect_id": prospect_id,
            "metric": metric,
            "trajectory": trajectory,
            "recent_trajectory": recent_trajectory,
            "trend_analysis": {
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_squared),
                "recent_slope": float(recent_slope)
            },
            "data_points": data_points,
            "summary": {
                "first_value": data_points[0]["value"],
                "last_value": data_points[-1]["value"],
                "change": data_points[-1]["value"] - data_points[0]["value"],
                "change_percent": ((data_points[-1]["value"] - data_points[0]["value"]) / data_points[0]["value"] * 100) if data_points[0]["value"] != 0 else 0,
                "peak_value": max(dp["value"] for dp in data_points),
                "low_value": min(dp["value"] for dp in data_points),
                "average": np.mean(y)
            }
        }

    @staticmethod
    async def get_season_over_season_comparison(
        db: AsyncSession,
        prospect_id: int,
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare prospect performance across seasons.

        Args:
            db: Database session
            prospect_id: Prospect ID
            metrics: List of metrics to compare (default: key metrics)

        Returns:
            Season-over-season comparison data
        """
        if not metrics:
            metrics = [
                "batting_avg", "on_base_pct", "slugging_pct", "ops",
                "home_runs", "rbi", "stolen_bases",
                "era", "whip", "k_per_9", "bb_per_9"
            ]

        # Get all stats organized by season
        historical = await HistoricalDataService.get_prospect_historical_stats(
            db, prospect_id
        )

        season_comparison = {
            "prospect_id": prospect_id,
            "seasons": {},
            "metrics_progression": {},
            "level_progression": []
        }

        # Calculate season aggregates
        for season, levels in historical["stats_by_season"].items():
            season_data = {
                "levels": list(levels.keys()),
                "metrics": {}
            }

            # Aggregate metrics across all levels for the season
            for metric in metrics:
                values = []
                for level, stats_list in levels.items():
                    for stat in stats_list:
                        if stat.get(metric) is not None:
                            values.append(stat[metric])

                if values:
                    season_data["metrics"][metric] = {
                        "average": np.mean(values),
                        "min": min(values),
                        "max": max(values),
                        "games": sum(s.get("games_played", 0) for l in levels.values() for s in l)
                    }

            season_comparison["seasons"][season] = season_data

        # Calculate progression for each metric
        for metric in metrics:
            progression = []
            for season in sorted(season_comparison["seasons"].keys()):
                if metric in season_comparison["seasons"][season]["metrics"]:
                    progression.append({
                        "season": season,
                        "value": season_comparison["seasons"][season]["metrics"][metric]["average"]
                    })

            if len(progression) > 1:
                # Calculate year-over-year changes
                for i in range(1, len(progression)):
                    prev_value = progression[i-1]["value"]
                    curr_value = progression[i]["value"]
                    change = curr_value - prev_value
                    change_pct = (change / prev_value * 100) if prev_value != 0 else 0
                    progression[i]["change"] = change
                    progression[i]["change_percent"] = change_pct

            season_comparison["metrics_progression"][metric] = progression

        # Track level progression
        for season in sorted(season_comparison["seasons"].keys()):
            season_comparison["level_progression"].append({
                "season": season,
                "levels": season_comparison["seasons"][season]["levels"]
            })

        return season_comparison

    @staticmethod
    async def get_historical_ml_predictions(
        db: AsyncSession,
        prospect_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get historical ML predictions and their accuracy.

        Args:
            db: Database session
            prospect_id: Prospect ID
            limit: Maximum number of predictions to retrieve

        Returns:
            Historical predictions with accuracy analysis
        """
        # Get predictions
        query = select(MLPrediction).where(
            and_(
                MLPrediction.prospect_id == prospect_id,
                MLPrediction.prediction_type == 'success_rating'
            )
        ).order_by(desc(MLPrediction.generated_at)).limit(limit)

        result = await db.execute(query)
        predictions = result.scalars().all()

        if not predictions:
            return {
                "prospect_id": prospect_id,
                "predictions": [],
                "summary": "No historical predictions available"
            }

        # Format predictions
        historical_predictions = {
            "prospect_id": prospect_id,
            "predictions": [],
            "trend": {},
            "accuracy_metrics": {}
        }

        for pred in predictions:
            historical_predictions["predictions"].append({
                "date": pred.generated_at.isoformat(),
                "success_probability": pred.success_probability,
                "confidence_level": pred.confidence_level,
                "model_version": pred.model_version,
                "narrative": pred.narrative
            })

        # Calculate prediction trends
        if len(predictions) > 1:
            probabilities = [p.success_probability for p in predictions]
            historical_predictions["trend"] = {
                "latest": probabilities[0],
                "oldest": probabilities[-1],
                "change": probabilities[0] - probabilities[-1],
                "average": np.mean(probabilities),
                "std_dev": np.std(probabilities),
                "volatility": "high" if np.std(probabilities) > 0.15 else "medium" if np.std(probabilities) > 0.08 else "low"
            }

        return historical_predictions

    @staticmethod
    async def get_peer_performance_comparison(
        db: AsyncSession,
        prospect_id: int,
        season: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Compare prospect's historical performance to peers at same level/age.

        Args:
            db: Database session
            prospect_id: Prospect ID
            season: Season to compare (default: current)

        Returns:
            Peer comparison data with percentiles
        """
        # Get prospect details
        prospect_query = select(Prospect).where(Prospect.id == prospect_id)
        prospect_result = await db.execute(prospect_query)
        prospect = prospect_result.scalar_one_or_none()

        if not prospect:
            return {"error": "Prospect not found"}

        # Get prospect's stats for the season
        stats_query = select(ProspectStats).where(
            ProspectStats.prospect_id == prospect_id
        )
        if season:
            stats_query = stats_query.where(ProspectStats.season == season)
        stats_query = stats_query.order_by(desc(ProspectStats.date_recorded)).limit(1)

        stats_result = await db.execute(stats_query)
        prospect_stats = stats_result.scalar_one_or_none()

        if not prospect_stats:
            return {
                "prospect_id": prospect_id,
                "message": "No stats available for comparison"
            }

        # Get peer stats (same position, similar age, same level)
        peer_query = select(ProspectStats).join(Prospect).where(
            and_(
                Prospect.position == prospect.position,
                Prospect.age.between(prospect.age - 1, prospect.age + 1),
                ProspectStats.level == prospect_stats.level,
                ProspectStats.prospect_id != prospect_id
            )
        )
        if season:
            peer_query = peer_query.where(ProspectStats.season == season)

        peer_result = await db.execute(peer_query)
        peer_stats = peer_result.scalars().all()

        if not peer_stats:
            return {
                "prospect_id": prospect_id,
                "message": "No peer data available for comparison"
            }

        # Calculate percentiles for key metrics
        comparison = {
            "prospect_id": prospect_id,
            "prospect_name": prospect.name,
            "comparison_group": {
                "position": prospect.position,
                "age_range": f"{prospect.age-1}-{prospect.age+1}",
                "level": prospect_stats.level,
                "peer_count": len(peer_stats)
            },
            "percentiles": {}
        }

        # Metrics to compare
        metrics_to_compare = {
            "batting_avg": "higher_better",
            "on_base_pct": "higher_better",
            "slugging_pct": "higher_better",
            "ops": "higher_better",
            "era": "lower_better",
            "whip": "lower_better",
            "k_per_9": "higher_better",
            "bb_per_9": "lower_better"
        }

        for metric, direction in metrics_to_compare.items():
            if hasattr(prospect_stats, metric):
                prospect_value = getattr(prospect_stats, metric)
                if prospect_value is not None:
                    peer_values = [getattr(ps, metric) for ps in peer_stats
                                 if getattr(ps, metric) is not None]

                    if peer_values:
                        # Calculate percentile
                        if direction == "higher_better":
                            percentile = (sum(1 for v in peer_values if v < prospect_value) / len(peer_values)) * 100
                        else:
                            percentile = (sum(1 for v in peer_values if v > prospect_value) / len(peer_values)) * 100

                        comparison["percentiles"][metric] = {
                            "value": prospect_value,
                            "percentile": round(percentile, 1),
                            "peer_average": np.mean(peer_values),
                            "peer_median": np.median(peer_values),
                            "rating": "elite" if percentile >= 90 else "above_average" if percentile >= 70 else "average" if percentile >= 30 else "below_average"
                        }

        return comparison