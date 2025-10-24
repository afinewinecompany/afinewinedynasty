"""
Pitch Data Aggregator Service

Aggregates pitch-level MiLB data into weighted performance metrics
with percentile rankings by level cohort.

Used by ProspectRankingService to calculate enhanced performance modifiers.
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
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate hitter pitch-level metrics for recent performance.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level (AAA, AA, A+, A, etc.)
            days: Number of days to look back (default 60)

        Returns:
            Dict with raw metrics, percentiles, and sample size
            None if insufficient data
        """
        # FIXED: Check what levels the player has played at recently
        levels_query = text("""
            SELECT level, COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = :mlb_player_id
                AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            GROUP BY level
            ORDER BY pitch_count DESC
        """)

        levels_result = await self.db.execute(
            levels_query,
            {'mlb_player_id': int(mlb_player_id), 'days': str(days)}
        )
        levels_data = levels_result.fetchall()

        if not levels_data:
            logger.info(f"No pitch data for hitter {mlb_player_id} in last {days} days")
            return None

        levels_played = [row[0] for row in levels_data]
        total_pitches = sum(row[1] for row in levels_data)

        logger.info(f"Player {mlb_player_id}: {total_pitches} pitches at {levels_played} in {days}d")

        # FIXED: Aggregate across ALL levels
        query = text("""
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

                    -- Track levels included
                    array_agg(DISTINCT level ORDER BY level) as levels_included

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    AND level = ANY(:levels)  -- FIXED: Include ALL levels
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_seen >= :min_pitches
        """)

        try:
            result = await self.db.execute(
                query,
                {
                    'mlb_player_id': int(mlb_player_id),
                    'levels': levels_played,  # FIXED: Pass ALL levels
                    'days': str(days),
                    'min_pitches': self.MIN_PITCHES_BATTER
                }
            )

            row = result.fetchone()

            if not row:
                logger.info(
                    f"Insufficient pitch data for hitter {mlb_player_id} at {level} "
                    f"(need {self.MIN_PITCHES_BATTER} pitches in last {days} days)"
                )
                return None

            metrics = {
                'exit_velo_90th': row[0],
                'hard_hit_rate': row[1],
                'contact_rate': row[2],
                'whiff_rate': row[3],
                'chase_rate': row[4],
            }

            # Calculate percentiles against level cohort
            percentiles = await self._calculate_hitter_percentiles(metrics, level)

            # Use specified level for percentile comparison, or highest level played
            comparison_level = level if level in levels_played else levels_played[0]

            result_dict = {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],  # FIXED: Now includes ALL levels
                'days_covered': days,
                'level': comparison_level,
            }

            # Add multi-level info if applicable
            if row[8] and len(row[8]) > 1:
                result_dict['levels_included'] = row[8]
                result_dict['aggregation_note'] = f"Data from: {', '.join(row[8])}"
                logger.info(f"Aggregated {row[5]} pitches from levels: {row[8]}")

            return result_dict

        except Exception as e:
            logger.error(f"Error fetching hitter pitch metrics: {e}")
            return None

    async def get_pitcher_pitch_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate pitcher pitch-level metrics for recent performance.

        FIXED: Now aggregates across ALL levels the player has played at.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level for percentile comparison (AAA, AA, A+, A, etc.)
            days: Number of days to look back (default 60)

        Returns:
            Dict with raw metrics, percentiles, and sample size
            None if insufficient data
        """
        # FIXED: Check what levels the player has played at recently
        levels_query = text("""
            SELECT level, COUNT(*) as pitch_count
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id = :mlb_player_id
                AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            GROUP BY level
            ORDER BY pitch_count DESC
        """)

        levels_result = await self.db.execute(
            levels_query,
            {'mlb_pitcher_id': int(mlb_player_id), 'days': str(days)}
        )
        levels_data = levels_result.fetchall()

        if not levels_data:
            logger.info(f"No pitch data for pitcher {mlb_player_id} in last {days} days")
            return None

        levels_played = [row[0] for row in levels_data]
        total_pitches = sum(row[1] for row in levels_data)

        logger.info(f"Pitcher {mlb_player_id}: {total_pitches} pitches at {levels_played} in {days}d")

        # FIXED: Aggregate across ALL levels
        query = text("""
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

                    -- Track levels included
                    array_agg(DISTINCT level ORDER BY level) as levels_included

                FROM milb_pitcher_pitches
                WHERE mlb_pitcher_id = :mlb_player_id
                    AND level = ANY(:levels)  -- FIXED: Include ALL levels
                    AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
            )
            SELECT * FROM player_stats
            WHERE pitches_thrown >= :min_pitches
        """)

        try:
            result = await self.db.execute(
                query,
                {
                    'mlb_player_id': int(mlb_player_id),
                    'levels': levels_played,  # FIXED: Pass ALL levels
                    'days': str(days),
                    'min_pitches': self.MIN_PITCHES_PITCHER
                }
            )

            row = result.fetchone()

            if not row:
                logger.info(
                    f"Insufficient pitch data for pitcher {mlb_player_id} at {level} "
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

            # Use specified level for percentile comparison, or highest level played
            comparison_level = level if level in levels_played else levels_played[0]

            # Calculate percentiles against level cohort
            percentiles = await self._calculate_pitcher_percentiles(metrics, comparison_level)

            result_dict = {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[5],  # FIXED: Now includes ALL levels
                'days_covered': days,
                'level': comparison_level,
            }

            # Add multi-level info if applicable (pitchers have one less field than hitters)
            if row[7] and len(row[7]) > 1:
                result_dict['levels_included'] = row[7]
                result_dict['aggregation_note'] = f"Data from: {', '.join(row[7])}"
                logger.info(f"Aggregated {row[5]} pitches from levels: {row[7]}")

            return result_dict

        except Exception as e:
            logger.error(f"Error fetching pitcher pitch metrics: {e}")
            return None

    async def _calculate_hitter_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """
        Calculate percentile rank for each hitter metric vs level cohort.

        Args:
            metrics: Dict of metric_name -> raw_value
            level: MiLB level for cohort comparison

        Returns:
            Dict of metric_name -> percentile_rank (0-100)
        """
        # Query materialized view for level percentiles
        query = text("""
            SELECT
                exit_velo_percentiles,
                hard_hit_percentiles,
                contact_percentiles,
                whiff_percentiles,
                chase_percentiles
            FROM mv_hitter_percentiles_by_level
            WHERE level = :level
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        try:
            result = await self.db.execute(query, {'level': level})
            row = result.fetchone()

            if not row:
                logger.warning(
                    f"No percentile data for level {level}, using median defaults"
                )
                return {key: 50.0 for key in self.HITTER_WEIGHTS.keys()}

            # Calculate percentile rank for each metric
            percentiles = {}
            percentiles['exit_velo_90th'] = self._find_percentile(
                metrics.get('exit_velo_90th'), row[0]
            )
            percentiles['hard_hit_rate'] = self._find_percentile(
                metrics.get('hard_hit_rate'), row[1]
            )
            percentiles['contact_rate'] = self._find_percentile(
                metrics.get('contact_rate'), row[2]
            )
            percentiles['whiff_rate'] = self._find_percentile(
                metrics.get('whiff_rate'), row[3]
            )
            percentiles['chase_rate'] = self._find_percentile(
                metrics.get('chase_rate'), row[4]
            )

            return percentiles

        except Exception as e:
            logger.error(f"Error calculating hitter percentiles: {e}")
            return {key: 50.0 for key in self.HITTER_WEIGHTS.keys()}

    async def _calculate_pitcher_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """
        Calculate percentile rank for each pitcher metric vs level cohort.

        Args:
            metrics: Dict of metric_name -> raw_value
            level: MiLB level for cohort comparison

        Returns:
            Dict of metric_name -> percentile_rank (0-100)
        """
        query = text("""
            SELECT
                whiff_percentiles,
                zone_percentiles,
                velo_percentiles,
                hard_contact_percentiles,
                chase_percentiles
            FROM mv_pitcher_percentiles_by_level
            WHERE level = :level
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        try:
            result = await self.db.execute(query, {'level': level})
            row = result.fetchone()

            if not row:
                logger.warning(
                    f"No percentile data for level {level}, using median defaults"
                )
                return {key: 50.0 for key in self.PITCHER_WEIGHTS.keys()}

            percentiles = {}
            percentiles['whiff_rate'] = self._find_percentile(
                metrics.get('whiff_rate'), row[0]
            )
            percentiles['zone_rate'] = self._find_percentile(
                metrics.get('zone_rate'), row[1]
            )
            percentiles['avg_fb_velo'] = self._find_percentile(
                metrics.get('avg_fb_velo'), row[2]
            )
            percentiles['hard_contact_rate'] = self._find_percentile(
                metrics.get('hard_contact_rate'), row[3]
            )
            percentiles['chase_rate'] = self._find_percentile(
                metrics.get('chase_rate'), row[4]
            )

            return percentiles

        except Exception as e:
            logger.error(f"Error calculating pitcher percentiles: {e}")
            return {key: 50.0 for key in self.PITCHER_WEIGHTS.keys()}

    def _find_percentile(
        self,
        value: Optional[float],
        percentile_array: List[float]
    ) -> float:
        """
        Find percentile rank of value within distribution.

        Uses linear interpolation between known percentiles.

        Args:
            value: The value to rank
            percentile_array: [p10, p25, p50, p75, p90] from materialized view

        Returns:
            Estimated percentile (0-100)
        """
        if value is None or percentile_array is None:
            return 50.0  # Default to median

        try:
            p10, p25, p50, p75, p90 = percentile_array

            # Convert to float to handle Decimal types from database
            value = float(value)
            p10, p25, p50, p75, p90 = float(p10), float(p25), float(p50), float(p75), float(p90)

            if value <= p10:
                return 5.0
            elif value <= p25:
                # Interpolate between 10th and 25th percentile
                return 10 + ((value - p10) / (p25 - p10)) * 15
            elif value <= p50:
                # Interpolate between 25th and 50th percentile
                return 25 + ((value - p25) / (p50 - p25)) * 25
            elif value <= p75:
                # Interpolate between 50th and 75th percentile
                return 50 + ((value - p50) / (p75 - p50)) * 25
            elif value <= p90:
                # Interpolate between 75th and 90th percentile
                return 75 + ((value - p75) / (p90 - p75)) * 15
            else:
                return 95.0

        except (TypeError, ZeroDivisionError, ValueError) as e:
            logger.warning(f"Error interpolating percentile: {e}")
            return 50.0

    async def calculate_weighted_composite(
        self,
        percentiles: Dict,
        is_hitter: bool,
        ops_percentile: float = 50.0,
        k_minus_bb_percentile: float = 50.0
    ) -> Tuple[float, Dict]:
        """
        Calculate weighted composite score from percentiles.

        Args:
            percentiles: Dict of metric_name -> percentile_rank
            is_hitter: True for hitters, False for pitchers
            ops_percentile: OPS percentile (for hitters, fallback metric)
            k_minus_bb_percentile: K%-BB% percentile (for pitchers, fallback metric)

        Returns:
            Tuple of (composite_score, weighted_contributions)
            composite_score: Weighted composite (0-100 scale)
            weighted_contributions: Dict showing each metric's contribution
        """
        weights = self.HITTER_WEIGHTS if is_hitter else self.PITCHER_WEIGHTS

        composite = 0.0
        contributions = {}

        for metric, weight in weights.items():
            percentile = percentiles.get(metric, 50.0)

            # Add fallback metrics
            if metric == 'ops' and is_hitter:
                percentile = ops_percentile
            elif metric == 'k_minus_bb' and not is_hitter:
                percentile = k_minus_bb_percentile

            # Invert negative metrics (lower is better)
            if metric in ['whiff_rate', 'chase_rate', 'hard_contact_rate']:
                if is_hitter and metric in ['whiff_rate', 'chase_rate']:
                    # For hitters: lower whiff/chase is better → invert
                    percentile = 100 - percentile
                elif not is_hitter and metric == 'hard_contact_rate':
                    # For pitchers: lower hard contact allowed is better → invert
                    percentile = 100 - percentile

            contribution = percentile * weight
            composite += contribution
            contributions[metric] = round(contribution, 2)

        return round(composite, 2), contributions

    def percentile_to_modifier(self, percentile: float) -> float:
        """
        Convert percentile rank (0-100) to performance modifier (-10 to +10).

        Mapping:
        - 95th+ percentile: +10
        - 90th percentile: +8
        - 75th percentile: +5
        - 60th percentile: +2
        - 40-60th: 0 (average)
        - 25th percentile: -2
        - 10th percentile: -5
        - 5th percentile: -8
        - <5th percentile: -10

        Args:
            percentile: Percentile rank (0-100)

        Returns:
            Performance modifier (-10 to +10)
        """
        if percentile >= 95:
            return 10.0
        elif percentile >= 90:
            return 8.0
        elif percentile >= 75:
            return 5.0
        elif percentile >= 60:
            return 2.0
        elif percentile >= 40:
            return 0.0
        elif percentile >= 25:
            return -2.0
        elif percentile >= 10:
            return -5.0
        elif percentile >= 5:
            return -8.0
        else:
            return -10.0
