"""
Enhanced Pitch Data Aggregator Service

Includes additional metrics beyond contact/whiff rate that can be calculated
from available pitch-by-pitch data, even when launch speed and velocity data are missing.

Additional metrics:
- Two-strike approach (swing rate, contact rate)
- Count leverage (first pitch, ahead/behind situations)
- Discipline score (composite of multiple factors)
- In-play rate (balls put in play)
- Productive swing rate (non-foul contact)
"""

from typing import Dict, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class EnhancedPitchDataAggregator:
    """Enhanced aggregator with additional pitch-level metrics."""

    # Minimum sample sizes
    MIN_PITCHES_BATTER = 50
    MIN_PITCHES_PITCHER = 100

    # Enhanced metric weights for hitters (must sum to 1.0)
    ENHANCED_HITTER_WEIGHTS = {
        'contact_rate': 0.20,           # Basic contact ability
        'whiff_rate': 0.15,              # Inverted - lower is better
        'two_strike_contact': 0.15,      # Ability to protect with 2 strikes
        'discipline_score': 0.15,        # Overall plate discipline
        'productive_swing_rate': 0.10,   # Non-foul contact on swings
        'in_play_rate': 0.10,            # Putting balls in play
        'first_pitch_approach': 0.05,    # Smart first pitch decisions
        'ahead_selectivity': 0.05,       # Selectivity when ahead in count
        'behind_contact': 0.05           # Contact ability when behind
    }

    # Enhanced metric weights for pitchers (must sum to 1.0)
    ENHANCED_PITCHER_WEIGHTS = {
        'whiff_rate': 0.25,              # Swing and miss ability
        'zone_rate': 0.15,               # Command - throwing strikes
        'two_strike_putaway': 0.15,      # Finishing hitters with 2 strikes
        'first_pitch_strike': 0.10,      # Getting ahead in counts
        'ahead_control': 0.10,           # Control when ahead
        'chase_generation': 0.10,        # Getting swings outside zone
        'contact_management': 0.10,      # Managing contact quality
        'foul_rate': 0.05                # Inducing non-productive contact
    }

    def __init__(self, db: AsyncSession):
        """Initialize the enhanced aggregator with database session."""
        self.db = db

    async def _check_season_status(self) -> Dict:
        """Check if we're in the offseason and should use full season data."""
        from datetime import datetime, timedelta

        season_end = datetime(2025, 10, 7)
        today = datetime.now()
        days_since_end = (today - season_end).days
        use_full_season = days_since_end > 7

        return {
            'use_full_season': use_full_season,
            'current_year': 2025,
            'days_since_end': days_since_end
        }

    async def get_enhanced_hitter_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate enhanced hitter metrics including count leverage and discipline.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level for percentile comparison
            days: Number of days to look back (ignored if in offseason)

        Returns:
            Dict with enhanced metrics, percentiles, and quality indicators
        """
        season_info = await self._check_season_status()
        use_full_season = season_info['use_full_season']

        # Get player's levels
        if use_full_season:
            levels_query = text("""
                SELECT level, COUNT(*) as pitch_count
                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_player_id
                    AND season = :season
                GROUP BY level
                ORDER BY pitch_count DESC
            """)
            levels_result = await self.db.execute(
                levels_query,
                {'mlb_player_id': int(mlb_player_id), 'season': season_info['current_year']}
            )
        else:
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
            return None

        levels_played = [row[0] for row in levels_data]
        total_pitches = sum(row[1] for row in levels_data)

        logger.info(f"Enhanced metrics for hitter {mlb_player_id}: {total_pitches} pitches at {levels_played}")

        # Build enhanced query
        if use_full_season:
            query = text("""
                WITH pitch_data AS (
                    SELECT * FROM milb_batter_pitches
                    WHERE mlb_batter_id = :mlb_player_id
                        AND level = ANY(:levels)
                        AND season = :season
                ),
                basic_metrics AS (
                    SELECT
                        -- Basic rates
                        COUNT(*) as total_pitches,
                        COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                        COUNT(*) FILTER (WHERE contact = TRUE) as contacts,
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) as whiffs,
                        COUNT(*) FILTER (WHERE foul = TRUE) as fouls,

                        -- Basic percentages
                        COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                        -- In-play and productive swings
                        COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) * 100.0 /
                            NULLIF(COUNT(*), 0) as in_play_rate,
                        COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as productive_swing_rate,

                        -- Zone awareness (if available)
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,
                        COUNT(*) FILTER (WHERE pitch_call = 'B') * 100.0 /
                            NULLIF(COUNT(*), 0) as ball_rate
                    FROM pitch_data
                ),
                count_situations AS (
                    SELECT
                        -- Two strike approach
                        COUNT(*) FILTER (WHERE strikes = 2) as two_strike_pitches,
                        COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2) as two_strike_swings,
                        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) as two_strike_contacts,
                        COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE strikes = 2), 0) as two_strike_swing_rate,
                        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2), 0) as two_strike_contact_rate,

                        -- First pitch
                        COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0) as first_pitches,
                        COUNT(*) FILTER (WHERE swing = TRUE AND balls = 0 AND strikes = 0) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0), 0) as first_pitch_swing_rate,

                        -- Ahead in count (hitter's advantage)
                        COUNT(*) FILTER (WHERE swing = TRUE AND (
                            (balls = 1 AND strikes = 0) OR (balls = 2 AND strikes = 0) OR
                            (balls = 2 AND strikes = 1) OR (balls = 3 AND strikes = 0) OR
                            (balls = 3 AND strikes = 1)
                        )) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE
                            (balls = 1 AND strikes = 0) OR (balls = 2 AND strikes = 0) OR
                            (balls = 2 AND strikes = 1) OR (balls = 3 AND strikes = 0) OR
                            (balls = 3 AND strikes = 1)
                        ), 0) as ahead_swing_rate,

                        -- Behind in count (pitcher's advantage)
                        COUNT(*) FILTER (WHERE contact = TRUE AND (
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        )) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND (
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        )), 0) as behind_contact_rate
                    FROM pitch_data
                )
                SELECT
                    b.*,
                    c.*,
                    -- Calculate discipline score (weighted composite)
                    (
                        COALESCE(b.contact_rate, 75) * 0.30 +
                        (100 - COALESCE(b.whiff_rate, 25)) * 0.30 +
                        CASE
                            WHEN b.contact_rate * 100.0 / NULLIF(b.total_pitches, 1) BETWEEN 40 AND 50 THEN 100
                            WHEN b.contact_rate * 100.0 / NULLIF(b.total_pitches, 1) BETWEEN 35 AND 55 THEN 75
                            ELSE 50
                        END * 0.20 +
                        COALESCE(b.ball_rate, 35) * 0.20
                    ) as discipline_score
                FROM basic_metrics b, count_situations c
            """)

            query_params = {
                'mlb_player_id': int(mlb_player_id),
                'levels': levels_played,
                'season': season_info['current_year']
            }
        else:
            # Similar query but with date filtering instead of season
            query = text("""
                WITH pitch_data AS (
                    SELECT * FROM milb_batter_pitches
                    WHERE mlb_batter_id = :mlb_player_id
                        AND level = ANY(:levels)
                        AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
                ),
                basic_metrics AS (
                    SELECT
                        -- Basic rates
                        COUNT(*) as total_pitches,
                        COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                        COUNT(*) FILTER (WHERE contact = TRUE) as contacts,
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) as whiffs,
                        COUNT(*) FILTER (WHERE foul = TRUE) as fouls,

                        -- Basic percentages
                        COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                        -- In-play and productive swings
                        COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) * 100.0 /
                            NULLIF(COUNT(*), 0) as in_play_rate,
                        COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as productive_swing_rate,

                        -- Zone awareness (if available)
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,
                        COUNT(*) FILTER (WHERE pitch_call = 'B') * 100.0 /
                            NULLIF(COUNT(*), 0) as ball_rate
                    FROM pitch_data
                ),
                count_situations AS (
                    SELECT
                        -- Two strike approach
                        COUNT(*) FILTER (WHERE strikes = 2) as two_strike_pitches,
                        COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2) as two_strike_swings,
                        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) as two_strike_contacts,
                        COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE strikes = 2), 0) as two_strike_swing_rate,
                        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2), 0) as two_strike_contact_rate,

                        -- First pitch
                        COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0) as first_pitches,
                        COUNT(*) FILTER (WHERE swing = TRUE AND balls = 0 AND strikes = 0) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0), 0) as first_pitch_swing_rate,

                        -- Ahead in count
                        COUNT(*) FILTER (WHERE swing = TRUE AND (
                            (balls = 1 AND strikes = 0) OR (balls = 2 AND strikes = 0) OR
                            (balls = 2 AND strikes = 1) OR (balls = 3 AND strikes = 0) OR
                            (balls = 3 AND strikes = 1)
                        )) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE
                            (balls = 1 AND strikes = 0) OR (balls = 2 AND strikes = 0) OR
                            (balls = 2 AND strikes = 1) OR (balls = 3 AND strikes = 0) OR
                            (balls = 3 AND strikes = 1)
                        ), 0) as ahead_swing_rate,

                        -- Behind in count
                        COUNT(*) FILTER (WHERE contact = TRUE AND (
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        )) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND (
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        )), 0) as behind_contact_rate
                    FROM pitch_data
                )
                SELECT
                    b.*,
                    c.*,
                    -- Calculate discipline score
                    (
                        COALESCE(b.contact_rate, 75) * 0.30 +
                        (100 - COALESCE(b.whiff_rate, 25)) * 0.30 +
                        CASE
                            WHEN b.contact_rate * 100.0 / NULLIF(b.total_pitches, 1) BETWEEN 40 AND 50 THEN 100
                            WHEN b.contact_rate * 100.0 / NULLIF(b.total_pitches, 1) BETWEEN 35 AND 55 THEN 75
                            ELSE 50
                        END * 0.20 +
                        COALESCE(b.ball_rate, 35) * 0.20
                    ) as discipline_score
                FROM basic_metrics b, count_situations c
            """)

            query_params = {
                'mlb_player_id': int(mlb_player_id),
                'levels': levels_played,
                'days': str(days)
            }

        try:
            result = await self.db.execute(query, query_params)
            row = result.fetchone()

            if not row or row[0] < self.MIN_PITCHES_BATTER:
                logger.info(f"Insufficient data for enhanced metrics: {row[0] if row else 0} pitches")
                return None

            # Extract metrics from row (column order matches SELECT)
            metrics = {
                'contact_rate': float(row[5]) if row[5] is not None else None,
                'whiff_rate': float(row[6]) if row[6] is not None else None,
                'in_play_rate': float(row[7]) if row[7] is not None else None,
                'productive_swing_rate': float(row[8]) if row[8] is not None else None,
                'chase_rate': float(row[9]) if row[9] is not None else None,
                'ball_rate': float(row[10]) if row[10] is not None else None,
                'two_strike_swing_rate': float(row[15]) if row[15] is not None else None,
                'two_strike_contact_rate': float(row[16]) if row[16] is not None else None,
                'first_pitch_swing_rate': float(row[18]) if row[18] is not None else None,
                'ahead_swing_rate': float(row[19]) if row[19] is not None else None,
                'behind_contact_rate': float(row[20]) if row[20] is not None else None,
                'discipline_score': float(row[21]) if row[21] is not None else None
            }

            # Log what metrics are available
            available_metrics = [k for k, v in metrics.items() if v is not None]
            logger.info(f"Available enhanced metrics for {mlb_player_id}: {available_metrics}")

            # Calculate percentiles for the enhanced metrics
            percentiles = await self._calculate_enhanced_hitter_percentiles(metrics, level)

            # Determine comparison level
            comparison_level = level if level in levels_played else levels_played[0]

            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[0],
                'swings': row[1],
                'level': comparison_level,
                'levels_included': levels_played,
                'metrics_available': len(available_metrics),
                'enhanced_metrics': True
            }

        except Exception as e:
            logger.error(f"Error calculating enhanced hitter metrics: {e}")
            return None

    async def get_enhanced_pitcher_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """Calculate enhanced pitcher metrics including count leverage."""
        season_info = await self._check_season_status()
        use_full_season = season_info['use_full_season']

        # Get pitcher's levels (similar to hitter logic)
        if use_full_season:
            levels_query = text("""
                SELECT level, COUNT(*) as pitch_count
                FROM milb_pitcher_pitches
                WHERE mlb_pitcher_id = :mlb_player_id
                    AND season = :season
                GROUP BY level
                ORDER BY pitch_count DESC
            """)
            levels_result = await self.db.execute(
                levels_query,
                {'mlb_player_id': int(mlb_player_id), 'season': season_info['current_year']}
            )
        else:
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
                {'mlb_player_id': int(mlb_player_id), 'days': str(days)}
            )

        levels_data = levels_result.fetchall()
        if not levels_data:
            return None

        levels_played = [row[0] for row in levels_data]

        # Build enhanced pitcher query
        if use_full_season:
            query = text("""
                WITH pitch_data AS (
                    SELECT * FROM milb_pitcher_pitches
                    WHERE mlb_pitcher_id = :mlb_player_id
                        AND level = ANY(:levels)
                        AND season = :season
                ),
                basic_metrics AS (
                    SELECT
                        COUNT(*) as total_pitches,

                        -- Basic rates
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,
                        COUNT(*) FILTER (WHERE zone <= 9) * 100.0 /
                            NULLIF(COUNT(*), 0) as zone_rate,
                        COUNT(*) FILTER (WHERE foul = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as foul_rate,

                        -- Chase generation
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_generation,

                        -- Contact management
                        COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_allowed
                    FROM pitch_data
                ),
                count_situations AS (
                    SELECT
                        -- Two strike putaway
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE strikes = 2), 0) as two_strike_putaway,

                        -- First pitch strike
                        COUNT(*) FILTER (WHERE is_strike = TRUE AND balls = 0 AND strikes = 0) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0), 0) as first_pitch_strike,

                        -- Ahead control
                        COUNT(*) FILTER (WHERE zone <= 9 AND (
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        )) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        ), 0) as ahead_control
                    FROM pitch_data
                )
                SELECT
                    b.*,
                    c.*
                FROM basic_metrics b, count_situations c
            """)

            query_params = {
                'mlb_player_id': int(mlb_player_id),
                'levels': levels_played,
                'season': season_info['current_year']
            }
        else:
            # Date-based query for active season
            query = text("""
                WITH pitch_data AS (
                    SELECT * FROM milb_pitcher_pitches
                    WHERE mlb_pitcher_id = :mlb_player_id
                        AND level = ANY(:levels)
                        AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
                ),
                basic_metrics AS (
                    SELECT
                        COUNT(*) as total_pitches,

                        -- Basic rates
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,
                        COUNT(*) FILTER (WHERE zone <= 9) * 100.0 /
                            NULLIF(COUNT(*), 0) as zone_rate,
                        COUNT(*) FILTER (WHERE foul = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as foul_rate,

                        -- Chase generation
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_generation,

                        -- Contact management
                        COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_allowed
                    FROM pitch_data
                ),
                count_situations AS (
                    SELECT
                        -- Two strike putaway
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE strikes = 2), 0) as two_strike_putaway,

                        -- First pitch strike
                        COUNT(*) FILTER (WHERE is_strike = TRUE AND balls = 0 AND strikes = 0) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE balls = 0 AND strikes = 0), 0) as first_pitch_strike,

                        -- Ahead control
                        COUNT(*) FILTER (WHERE zone <= 9 AND (
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        )) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE
                            (balls = 0 AND strikes = 1) OR (balls = 0 AND strikes = 2) OR
                            (balls = 1 AND strikes = 2)
                        ), 0) as ahead_control
                    FROM pitch_data
                )
                SELECT
                    b.*,
                    c.*
                FROM basic_metrics b, count_situations c
            """)

            query_params = {
                'mlb_player_id': int(mlb_player_id),
                'levels': levels_played,
                'days': str(days)
            }

        try:
            result = await self.db.execute(query, query_params)
            row = result.fetchone()

            if not row or row[0] < self.MIN_PITCHES_PITCHER:
                return None

            metrics = {
                'whiff_rate': float(row[1]) if row[1] is not None else None,
                'zone_rate': float(row[2]) if row[2] is not None else None,
                'foul_rate': float(row[3]) if row[3] is not None else None,
                'chase_generation': float(row[4]) if row[4] is not None else None,
                'contact_management': float(row[5]) if row[5] is not None else None,
                'two_strike_putaway': float(row[6]) if row[6] is not None else None,
                'first_pitch_strike': float(row[7]) if row[7] is not None else None,
                'ahead_control': float(row[8]) if row[8] is not None else None
            }

            # Calculate percentiles
            percentiles = await self._calculate_enhanced_pitcher_percentiles(metrics, level)

            comparison_level = level if level in levels_played else levels_played[0]

            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[0],
                'level': comparison_level,
                'levels_included': levels_played,
                'enhanced_metrics': True
            }

        except Exception as e:
            logger.error(f"Error calculating enhanced pitcher metrics: {e}")
            return None

    async def _calculate_enhanced_hitter_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """Calculate percentiles for enhanced hitter metrics."""
        # For now, use approximations based on typical distributions
        # In production, these would come from materialized views

        percentiles = {}

        # Contact rate (higher is better)
        if metrics.get('contact_rate') is not None:
            percentiles['contact_rate'] = self._estimate_percentile(
                metrics['contact_rate'], [65, 72, 78, 83, 87], higher_is_better=True
            )

        # Whiff rate (lower is better)
        if metrics.get('whiff_rate') is not None:
            percentiles['whiff_rate'] = self._estimate_percentile(
                metrics['whiff_rate'], [35, 28, 22, 17, 13], higher_is_better=False
            )

        # Two-strike contact (higher is better)
        if metrics.get('two_strike_contact_rate') is not None:
            percentiles['two_strike_contact'] = self._estimate_percentile(
                metrics['two_strike_contact_rate'], [60, 68, 75, 80, 85], higher_is_better=True
            )

        # Discipline score (higher is better)
        if metrics.get('discipline_score') is not None:
            percentiles['discipline_score'] = self._estimate_percentile(
                metrics['discipline_score'], [50, 58, 65, 72, 80], higher_is_better=True
            )

        # Productive swing rate (higher is better)
        if metrics.get('productive_swing_rate') is not None:
            percentiles['productive_swing_rate'] = self._estimate_percentile(
                metrics['productive_swing_rate'], [25, 30, 35, 40, 45], higher_is_better=True
            )

        # In-play rate (higher is better)
        if metrics.get('in_play_rate') is not None:
            percentiles['in_play_rate'] = self._estimate_percentile(
                metrics['in_play_rate'], [12, 15, 18, 22, 26], higher_is_better=True
            )

        # First pitch approach (moderate is better)
        if metrics.get('first_pitch_swing_rate') is not None:
            # Optimal range is 25-35%, penalize too low or too high
            fps = metrics['first_pitch_swing_rate']
            if 25 <= fps <= 35:
                percentiles['first_pitch_approach'] = 80
            elif 20 <= fps <= 40:
                percentiles['first_pitch_approach'] = 60
            else:
                percentiles['first_pitch_approach'] = 40

        # Ahead selectivity (lower swing rate when ahead is better)
        if metrics.get('ahead_swing_rate') is not None:
            percentiles['ahead_selectivity'] = self._estimate_percentile(
                metrics['ahead_swing_rate'], [50, 45, 40, 35, 30], higher_is_better=False
            )

        # Behind contact (higher is better)
        if metrics.get('behind_contact_rate') is not None:
            percentiles['behind_contact'] = self._estimate_percentile(
                metrics['behind_contact_rate'], [65, 70, 75, 80, 85], higher_is_better=True
            )

        # Fill missing with defaults
        for metric in self.ENHANCED_HITTER_WEIGHTS:
            if metric not in percentiles:
                percentiles[metric] = 50.0

        return percentiles

    async def _calculate_enhanced_pitcher_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """Calculate percentiles for enhanced pitcher metrics."""
        percentiles = {}

        # Whiff rate (higher is better for pitchers)
        if metrics.get('whiff_rate') is not None:
            percentiles['whiff_rate'] = self._estimate_percentile(
                metrics['whiff_rate'], [15, 20, 25, 30, 35], higher_is_better=True
            )

        # Zone rate (moderate is better - too high can be hittable)
        if metrics.get('zone_rate') is not None:
            percentiles['zone_rate'] = self._estimate_percentile(
                metrics['zone_rate'], [40, 45, 50, 55, 60], higher_is_better=True
            )

        # Two-strike putaway (higher is better)
        if metrics.get('two_strike_putaway') is not None:
            percentiles['two_strike_putaway'] = self._estimate_percentile(
                metrics['two_strike_putaway'], [8, 12, 16, 20, 25], higher_is_better=True
            )

        # First pitch strike (higher is better)
        if metrics.get('first_pitch_strike') is not None:
            percentiles['first_pitch_strike'] = self._estimate_percentile(
                metrics['first_pitch_strike'], [55, 60, 65, 70, 75], higher_is_better=True
            )

        # Ahead control (higher is better)
        if metrics.get('ahead_control') is not None:
            percentiles['ahead_control'] = self._estimate_percentile(
                metrics['ahead_control'], [45, 50, 55, 60, 65], higher_is_better=True
            )

        # Chase generation (higher is better)
        if metrics.get('chase_generation') is not None:
            percentiles['chase_generation'] = self._estimate_percentile(
                metrics['chase_generation'], [20, 25, 30, 35, 40], higher_is_better=True
            )

        # Contact management (lower is better)
        if metrics.get('contact_management') is not None:
            percentiles['contact_management'] = self._estimate_percentile(
                metrics['contact_management'], [85, 80, 75, 70, 65], higher_is_better=False
            )

        # Foul rate (moderate - inducing non-productive contact)
        if metrics.get('foul_rate') is not None:
            percentiles['foul_rate'] = self._estimate_percentile(
                metrics['foul_rate'], [30, 35, 40, 45, 50], higher_is_better=True
            )

        # Fill missing
        for metric in self.ENHANCED_PITCHER_WEIGHTS:
            if metric not in percentiles:
                percentiles[metric] = 50.0

        return percentiles

    def _estimate_percentile(
        self,
        value: float,
        thresholds: List[float],
        higher_is_better: bool = True
    ) -> float:
        """
        Estimate percentile based on threshold values.

        Args:
            value: The metric value
            thresholds: [p10, p25, p50, p75, p90] thresholds
            higher_is_better: Whether higher values are better

        Returns:
            Estimated percentile (0-100)
        """
        if value is None:
            return 50.0

        p10, p25, p50, p75, p90 = thresholds

        if higher_is_better:
            if value <= p10:
                return 5.0
            elif value <= p25:
                return 10 + ((value - p10) / (p25 - p10)) * 15
            elif value <= p50:
                return 25 + ((value - p25) / (p50 - p25)) * 25
            elif value <= p75:
                return 50 + ((value - p50) / (p75 - p50)) * 25
            elif value <= p90:
                return 75 + ((value - p75) / (p90 - p75)) * 15
            else:
                return 95.0
        else:
            # Invert for "lower is better" metrics
            if value >= p90:
                return 5.0
            elif value >= p75:
                return 10 + ((p90 - value) / (p90 - p75)) * 15
            elif value >= p50:
                return 25 + ((p75 - value) / (p75 - p50)) * 25
            elif value >= p25:
                return 50 + ((p50 - value) / (p50 - p25)) * 25
            elif value >= p10:
                return 75 + ((p25 - value) / (p25 - p10)) * 15
            else:
                return 95.0

    async def calculate_enhanced_composite(
        self,
        percentiles: Dict,
        is_hitter: bool
    ) -> Tuple[float, Dict]:
        """
        Calculate weighted composite from enhanced metrics.

        Returns:
            Tuple of (composite_score, contributions)
        """
        weights = self.ENHANCED_HITTER_WEIGHTS if is_hitter else self.ENHANCED_PITCHER_WEIGHTS

        composite = 0.0
        contributions = {}

        for metric, weight in weights.items():
            percentile = percentiles.get(metric, 50.0)
            contribution = percentile * weight
            composite += contribution
            contributions[metric] = round(contribution, 2)

        return round(composite, 2), contributions

    def percentile_to_modifier(self, percentile: float) -> float:
        """Convert percentile to ranking modifier (-10 to +10)."""
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