"""Service for handling prospect statistical history and aggregations."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import logging

from app.db.models import Prospect, ProspectStats
from app.core.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class ProspectStatsService:
    """Service for managing prospect statistical data."""

    @staticmethod
    async def get_stats_history(
        db: AsyncSession,
        prospect_id: int,
        level: Optional[str] = None,
        season: Optional[int] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistical history for a prospect.

        Args:
            db: Database session
            prospect_id: Prospect ID
            level: Optional filter by minor league level
            season: Optional filter by season year
            limit: Optional limit on number of records

        Returns:
            Dictionary with stats organized by level and season
        """
        cache_key = f"stats_history:{prospect_id}:{level}:{season}:{limit}"
        cached = await cache_manager.get_cached_features(cache_key)
        if cached:
            return cached

        # Build query
        query = select(ProspectStats).where(
            ProspectStats.prospect_id == prospect_id
        )

        if level:
            query = query.where(ProspectStats.level == level)

        if season:
            # Filter by year from date_recorded
            year_start = datetime(season, 1, 1)
            year_end = datetime(season, 12, 31, 23, 59, 59)
            query = query.where(
                and_(
                    ProspectStats.date_recorded >= year_start,
                    ProspectStats.date_recorded <= year_end
                )
            )

        # Order by date descending
        query = query.order_by(desc(ProspectStats.date_recorded))

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        stats_records = result.scalars().all()

        # Organize stats by level and season
        stats_by_level = {}
        stats_by_season = {}

        for stat in stats_records:
            stat_year = stat.date_recorded.year

            # By level
            if stat.level not in stats_by_level:
                stats_by_level[stat.level] = []
            stats_by_level[stat.level].append(stat)

            # By season
            if stat_year not in stats_by_season:
                stats_by_season[stat_year] = []
            stats_by_season[stat_year].append(stat)

        # Calculate aggregations
        aggregations = await ProspectStatsService._calculate_aggregations(
            stats_records
        )

        result = {
            "prospect_id": prospect_id,
            "total_records": len(stats_records),
            "by_level": ProspectStatsService._format_stats_by_level(stats_by_level),
            "by_season": ProspectStatsService._format_stats_by_season(stats_by_season),
            "aggregations": aggregations,
            "latest_stats": ProspectStatsService._format_single_stat(stats_records[0]) if stats_records else None,
            "progression": ProspectStatsService._calculate_progression(stats_records)
        }

        # Cache for 6 hours
        await cache_manager.cache_prospect_features(
            cache_key, result, ttl=21600
        )

        return result

    @staticmethod
    async def get_multi_level_aggregation(
        db: AsyncSession,
        prospect_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get statistical aggregations across all minor league levels.

        Args:
            db: Database session
            prospect_id: Prospect ID

        Returns:
            List of aggregated stats by level
        """
        cache_key = f"multi_level_agg:{prospect_id}"
        cached = await cache_manager.get_cached_features(cache_key)
        if cached:
            return cached

        # Query for all stats grouped by level
        query = select(
            ProspectStats.level,
            func.count(ProspectStats.id).label('games'),
            func.avg(ProspectStats.batting_avg).label('avg_batting'),
            func.avg(ProspectStats.on_base_pct).label('avg_obp'),
            func.avg(ProspectStats.slugging_pct).label('avg_slg'),
            func.avg(ProspectStats.era).label('avg_era'),
            func.avg(ProspectStats.whip).label('avg_whip'),
            func.avg(ProspectStats.strikeout_rate).label('avg_k_rate'),
            func.avg(ProspectStats.walk_rate).label('avg_bb_rate'),
            func.min(ProspectStats.date_recorded).label('first_game'),
            func.max(ProspectStats.date_recorded).label('last_game')
        ).where(
            ProspectStats.prospect_id == prospect_id
        ).group_by(
            ProspectStats.level
        ).order_by(
            ProspectStats.level
        )

        result = await db.execute(query)
        aggregations = []

        level_order = ['Rookie', 'A', 'A+', 'AA', 'AAA']

        for row in result:
            level_data = {
                "level": row.level,
                "level_rank": level_order.index(row.level) if row.level in level_order else 99,
                "games": row.games,
                "date_range": {
                    "first": row.first_game.isoformat() if row.first_game else None,
                    "last": row.last_game.isoformat() if row.last_game else None
                }
            }

            # Add batting stats if available
            if row.avg_batting is not None:
                level_data["batting"] = {
                    "avg": round(row.avg_batting, 3) if row.avg_batting else None,
                    "obp": round(row.avg_obp, 3) if row.avg_obp else None,
                    "slg": round(row.avg_slg, 3) if row.avg_slg else None,
                    "ops": round((row.avg_obp or 0) + (row.avg_slg or 0), 3)
                }

            # Add pitching stats if available
            if row.avg_era is not None:
                level_data["pitching"] = {
                    "era": round(row.avg_era, 2) if row.avg_era else None,
                    "whip": round(row.avg_whip, 2) if row.avg_whip else None,
                    "k_rate": round(row.avg_k_rate, 1) if row.avg_k_rate else None,
                    "bb_rate": round(row.avg_bb_rate, 1) if row.avg_bb_rate else None
                }

            aggregations.append(level_data)

        # Sort by level rank
        aggregations.sort(key=lambda x: x['level_rank'])

        # Cache for 6 hours
        await cache_manager.cache_prospect_features(
            cache_key, aggregations, ttl=21600
        )

        return aggregations

    @staticmethod
    async def _calculate_aggregations(stats_records: List[ProspectStats]) -> Dict[str, Any]:
        """Calculate aggregate statistics from records."""
        if not stats_records:
            return {}

        # Separate batting and pitching stats
        batting_stats = [s for s in stats_records if s.batting_avg is not None]
        pitching_stats = [s for s in stats_records if s.era is not None]

        aggregations = {}

        if batting_stats:
            aggregations["batting"] = {
                "games": len(batting_stats),
                "avg": round(sum(s.batting_avg for s in batting_stats if s.batting_avg) / len(batting_stats), 3),
                "obp": round(sum(s.on_base_pct for s in batting_stats if s.on_base_pct) / len(batting_stats), 3),
                "slg": round(sum(s.slugging_pct for s in batting_stats if s.slugging_pct) / len(batting_stats), 3),
                "hr": sum(s.home_runs for s in batting_stats if s.home_runs),
                "rbi": sum(s.rbi for s in batting_stats if s.rbi),
                "sb": sum(s.stolen_bases for s in batting_stats if s.stolen_bases)
            }
            aggregations["batting"]["ops"] = round(
                aggregations["batting"]["obp"] + aggregations["batting"]["slg"], 3
            )

        if pitching_stats:
            total_innings = sum(s.innings_pitched for s in pitching_stats if s.innings_pitched)
            aggregations["pitching"] = {
                "games": len(pitching_stats),
                "innings": round(total_innings, 1),
                "era": round(sum(s.era * (s.innings_pitched or 0) for s in pitching_stats) / total_innings, 2) if total_innings else None,
                "whip": round(sum(s.whip * (s.innings_pitched or 0) for s in pitching_stats) / total_innings, 2) if total_innings else None,
                "k_rate": round(sum(s.strikeout_rate for s in pitching_stats if s.strikeout_rate) / len(pitching_stats), 1),
                "bb_rate": round(sum(s.walk_rate for s in pitching_stats if s.walk_rate) / len(pitching_stats), 1),
                "wins": sum(s.wins for s in pitching_stats if s.wins),
                "losses": sum(s.losses for s in pitching_stats if s.losses),
                "saves": sum(s.saves for s in pitching_stats if s.saves)
            }

        return aggregations

    @staticmethod
    def _format_stats_by_level(stats_by_level: Dict[str, List[ProspectStats]]) -> Dict[str, Any]:
        """Format stats grouped by level."""
        formatted = {}

        for level, stats in stats_by_level.items():
            formatted[level] = {
                "count": len(stats),
                "latest": ProspectStatsService._format_single_stat(stats[0]) if stats else None,
                "aggregation": ProspectStatsService._calculate_level_aggregation(stats)
            }

        return formatted

    @staticmethod
    def _format_stats_by_season(stats_by_season: Dict[int, List[ProspectStats]]) -> Dict[str, Any]:
        """Format stats grouped by season."""
        formatted = {}

        for season, stats in stats_by_season.items():
            formatted[str(season)] = {
                "count": len(stats),
                "levels": list(set(s.level for s in stats if s.level)),
                "aggregation": ProspectStatsService._calculate_season_aggregation(stats)
            }

        return formatted

    @staticmethod
    def _format_single_stat(stat: ProspectStats) -> Dict[str, Any]:
        """Format a single stat record."""
        if not stat:
            return None

        formatted = {
            "date": stat.date_recorded.isoformat(),
            "level": stat.level,
            "games": stat.games
        }

        # Add batting stats
        if stat.batting_avg is not None:
            formatted["batting"] = {
                "avg": stat.batting_avg,
                "obp": stat.on_base_pct,
                "slg": stat.slugging_pct,
                "ops": round((stat.on_base_pct or 0) + (stat.slugging_pct or 0), 3),
                "hr": stat.home_runs,
                "rbi": stat.rbi,
                "sb": stat.stolen_bases,
                "k_rate": stat.strikeout_rate,
                "bb_rate": stat.walk_rate,
                "woba": stat.woba,
                "wrc_plus": stat.wrc_plus
            }

        # Add pitching stats
        if stat.era is not None:
            formatted["pitching"] = {
                "era": stat.era,
                "whip": stat.whip,
                "k_rate": stat.strikeout_rate,
                "bb_rate": stat.walk_rate,
                "k_9": stat.k_per_9,
                "bb_9": stat.bb_per_9,
                "fip": stat.fip,
                "xfip": stat.xfip,
                "innings": stat.innings_pitched,
                "wins": stat.wins,
                "losses": stat.losses,
                "saves": stat.saves
            }

        return formatted

    @staticmethod
    def _calculate_level_aggregation(stats: List[ProspectStats]) -> Dict[str, Any]:
        """Calculate aggregations for a specific level."""
        if not stats:
            return {}

        # Use the general aggregation method
        return ProspectStatsService._calculate_aggregations(stats)

    @staticmethod
    def _calculate_season_aggregation(stats: List[ProspectStats]) -> Dict[str, Any]:
        """Calculate aggregations for a specific season."""
        if not stats:
            return {}

        # Use the general aggregation method with season context
        base_agg = ProspectStatsService._calculate_aggregations(stats)

        # Add season-specific info
        if base_agg:
            base_agg["games_played"] = len(stats)
            base_agg["levels_played"] = list(set(s.level for s in stats if s.level))

        return base_agg

    @staticmethod
    def _calculate_progression(stats_records: List[ProspectStats]) -> Dict[str, Any]:
        """Calculate statistical progression over time."""
        if len(stats_records) < 2:
            return {}

        # Get oldest and newest stats (list is already ordered desc)
        newest = stats_records[0]
        oldest = stats_records[-1]

        progression = {
            "time_span_days": (newest.date_recorded - oldest.date_recorded).days,
            "total_games": len(stats_records)
        }

        # Calculate batting progression
        if newest.batting_avg is not None and oldest.batting_avg is not None:
            progression["batting"] = {
                "avg_change": round(newest.batting_avg - oldest.batting_avg, 3),
                "obp_change": round((newest.on_base_pct or 0) - (oldest.on_base_pct or 0), 3),
                "slg_change": round((newest.slugging_pct or 0) - (oldest.slugging_pct or 0), 3),
                "wrc_plus_change": round((newest.wrc_plus or 0) - (oldest.wrc_plus or 0), 1) if newest.wrc_plus and oldest.wrc_plus else None
            }

        # Calculate pitching progression
        if newest.era is not None and oldest.era is not None:
            progression["pitching"] = {
                "era_change": round(newest.era - oldest.era, 2),
                "whip_change": round((newest.whip or 0) - (oldest.whip or 0), 2),
                "k_rate_change": round((newest.strikeout_rate or 0) - (oldest.strikeout_rate or 0), 1),
                "bb_rate_change": round((newest.walk_rate or 0) - (oldest.walk_rate or 0), 1)
            }

        return progression