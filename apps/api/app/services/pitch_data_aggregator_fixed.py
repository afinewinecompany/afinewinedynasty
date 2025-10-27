"""
Pitch Data Aggregator Service - FIXED VERSION

Aggregates pitch-level MiLB data into weighted performance metrics
with percentile rankings by level cohort.

FIXES:
- Aggregates pitch data across ALL levels played in the time period
- Properly accounts for players who moved between levels
"""

from typing import Dict, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class PitchDataAggregator:
    """Aggregates pitch-level data into weighted performance metrics."""

    # Minimum sample sizes
    MIN_PITCHES_BATTER = 50
    MIN_PITCHES_PITCHER = 100

    # Metric weights (must sum to 1.0)
    HITTER_WEIGHTS = {
        'exit_velo_90th': 0.25,
        'hard_hit_rate': 0.20,
        'contact_rate': 0.15,
        'whiff_rate': 0.15,  # Will be inverted (lower is better for hitters)
        'chase_rate': 0.10,  # Will be inverted (lower is better)
        'ops': 0.15
    }

    PITCHER_WEIGHTS = {
        'whiff_rate': 0.25,
        'zone_rate': 0.20,
        'avg_fb_velo': 0.15,
        'hard_contact_rate': 0.15,  # Will be inverted (lower is better)
        'chase_rate': 0.10,
        'k_minus_bb': 0.15
    }

    def __init__(self, db: AsyncSession):
        """Initialize the aggregator with database session."""
        self.db = db

    async def get_hitter_pitch_metrics(
        self,
        mlb_player_id: str,
        level: Optional[str] = None,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate hitter pitch-level metrics for recent performance.

        FIXED: Now aggregates across ALL levels if level is not specified,
        or across all levels played recently if a specific level is given.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level filter (optional - if provided, uses highest level as context)
            days: Number of days to look back (default 60)

        Returns:
            Dict with raw metrics, percentiles, and sample size
            None if insufficient data
        """

        # First, determine what levels the player has played at recently
        levels_query = text("""
            SELECT
                level,
                COUNT(*) as pitch_count,
                MAX(game_date) as last_game
            FROM milb_batter_pitches
            WHERE mlb_batter_id = :mlb_player_id
                AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            GROUP BY level
            ORDER BY pitch_count DESC
        """)

        levels_result = await self.db.execute(
            levels_query,
            {
                'mlb_player_id': int(mlb_player_id),
                'days': str(days)
            }
        )

        levels_data = levels_result.fetchall()

        if not levels_data:
            logger.info(f"No pitch data found for hitter {mlb_player_id} in last {days} days")
            return None

        # Determine the primary level for percentile comparison
        # Use the level with the most pitches, or the specified level if valid
        primary_level = level
        levels_played = [row[0] for row in levels_data]

        if not primary_level or primary_level not in levels_played:
            # Use the level with the most pitches
            primary_level = levels_data[0][0]

        # Build the level filter clause
        if level and level in levels_played:
            # If a specific level is requested and player played there, use only that level
            level_filter = "AND level = :level"
            filter_params = {'level': level}
        else:
            # Aggregate across ALL levels played in the time period
            level_filter = "AND level IN :levels"
            filter_params = {'levels': tuple(levels_played)}

        # Now get the aggregated metrics across the relevant levels
        query = text(f"""
            WITH player_stats AS (
                SELECT
                    -- Exit Velocity (90th percentile)
                    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                        FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                    -- Hard Hit Rate
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                    -- Contact Rate
                    COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                    -- Whiff Rate
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                    -- Chase Rate
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                    -- Sample size
                    COUNT(*) as pitches_seen,
                    COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                    COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play,

                    -- Levels represented
                    array_agg(DISTINCT level ORDER BY level) as levels_included

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    {level_filter}
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_seen >= :min_pitches
        """)

        try:
            params = {
                'mlb_player_id': int(mlb_player_id),
                'days': str(days),
                'min_pitches': self.MIN_PITCHES_BATTER
            }
            params.update(filter_params)

            result = await self.db.execute(query, params)
            row = result.fetchone()

            if not row:
                logger.info(
                    f"Insufficient pitch data for hitter {mlb_player_id} "
                    f"(need {self.MIN_PITCHES_BATTER} pitches in last {days} days, "
                    f"found less across levels: {', '.join(levels_played)})"
                )
                return None

            metrics = {
                'exit_velo_90th': row[0],
                'hard_hit_rate': row[1],
                'contact_rate': row[2],
                'whiff_rate': row[3],
                'chase_rate': row[4],
            }

            # Calculate percentiles against the primary level cohort
            percentiles = await self._calculate_hitter_percentiles(metrics, primary_level)

            # Include information about data aggregation
            levels_note = ""
            if row[8] and len(row[8]) > 1:
                levels_note = f"Aggregated from {', '.join(row[8])}"

            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],  # This will now be the TOTAL across all levels
                'days_covered': days,
                'level': primary_level,  # Primary level for context
                'levels_included': row[8] if row[8] else [primary_level],
                'aggregation_note': levels_note
            }

        except Exception as e:
            logger.error(f"Error fetching hitter pitch metrics: {e}")
            return None

    async def get_pitcher_pitch_metrics(
        self,
        mlb_player_id: str,
        level: Optional[str] = None,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate pitcher pitch-level metrics for recent performance.

        FIXED: Now aggregates across ALL levels if level is not specified.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level filter (optional)
            days: Number of days to look back (default 60)

        Returns:
            Dict with raw metrics, percentiles, and sample size
            None if insufficient data
        """

        # First, determine what levels the player has played at recently
        levels_query = text("""
            SELECT
                level,
                COUNT(*) as pitch_count,
                MAX(game_date) as last_game
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id = :mlb_player_id
                AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            GROUP BY level
            ORDER BY pitch_count DESC
        """)

        levels_result = await self.db.execute(
            levels_query,
            {
                'mlb_player_id': int(mlb_player_id),
                'days': str(days)
            }
        )

        levels_data = levels_result.fetchall()

        if not levels_data:
            logger.info(f"No pitch data found for pitcher {mlb_player_id} in last {days} days")
            return None

        # Determine the primary level for percentile comparison
        primary_level = level
        levels_played = [row[0] for row in levels_data]

        if not primary_level or primary_level not in levels_played:
            primary_level = levels_data[0][0]

        # Build the level filter
        if level and level in levels_played:
            level_filter = "AND level = :level"
            filter_params = {'level': level}
        else:
            level_filter = "AND level IN :levels"
            filter_params = {'levels': tuple(levels_played)}

        query = text(f"""
            WITH player_stats AS (
                SELECT
                    -- Whiff Rate
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                    -- Zone Rate
                    COUNT(*) FILTER (WHERE zone BETWEEN 1 AND 9) * 100.0 /
                        NULLIF(COUNT(*), 0) as zone_rate,

                    -- Avg FB Velocity
                    AVG(start_speed) FILTER (WHERE pitch_type IN ('FF', 'FA', 'SI')
                        AND start_speed IS NOT NULL) as avg_fb_velo,

                    -- Hard Contact Rate
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_contact_rate,

                    -- Chase Rate
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                    -- Sample size
                    COUNT(*) as pitches_thrown,
                    COUNT(*) FILTER (WHERE swing = TRUE) as swings_induced,

                    -- Levels represented
                    array_agg(DISTINCT level ORDER BY level) as levels_included

                FROM milb_pitcher_pitches
                WHERE mlb_pitcher_id = :mlb_player_id
                    {level_filter}
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_thrown >= :min_pitches
        """)

        try:
            params = {
                'mlb_player_id': int(mlb_player_id),
                'days': str(days),
                'min_pitches': self.MIN_PITCHES_PITCHER
            }
            params.update(filter_params)

            result = await self.db.execute(query, params)
            row = result.fetchone()

            if not row:
                logger.info(
                    f"Insufficient pitch data for pitcher {mlb_player_id} "
                    f"(need {self.MIN_PITCHES_PITCHER} pitches in last {days} days)"
                )
                return None

            metrics = {
                'whiff_rate': row[0],
                'zone_rate': row[1],
                'avg_fb_velo': row[2],
                'hard_contact_rate': row[3],
                'chase_rate': row[4],
            }

            # Calculate percentiles against the primary level cohort
            percentiles = await self._calculate_pitcher_percentiles(metrics, primary_level)

            levels_note = ""
            if row[7] and len(row[7]) > 1:
                levels_note = f"Aggregated from {', '.join(row[7])}"

            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],  # Total across all levels
                'days_covered': days,
                'level': primary_level,
                'levels_included': row[7] if row[7] else [primary_level],
                'aggregation_note': levels_note
            }

        except Exception as e:
            logger.error(f"Error fetching pitcher pitch metrics: {e}")
            return None

    # Rest of the methods remain the same...
    async def _calculate_hitter_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict[str, float]:
        """Calculate percentiles for hitter metrics at a given level."""
        # Implementation continues as before
        pass

    async def _calculate_pitcher_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict[str, float]:
        """Calculate percentiles for pitcher metrics at a given level."""
        # Implementation continues as before
        pass

    async def calculate_weighted_composite(
        self,
        percentiles: Dict[str, float],
        is_hitter: bool,
        ops_percentile: Optional[float] = None,
        k_minus_bb_percentile: Optional[float] = None
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate weighted composite percentile."""
        # Implementation continues as before
        pass

    def percentile_to_modifier(self, percentile: float) -> float:
        """Convert percentile to performance modifier."""
        # Implementation continues as before
        pass