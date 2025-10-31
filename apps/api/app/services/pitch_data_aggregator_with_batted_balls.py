"""
Enhanced Pitch Data Aggregator with Batted Ball Profiles

Extends the enhanced aggregator to include:
- Batted ball types (Ground Ball%, Line Drive%, Fly Ball%)
- Spray angles (Pull%, Center%, Oppo%)
- Contact quality (Hard Hit%, Soft Hit%)
- Power indicators (Pull Fly Ball%)

These metrics are crucial for evaluating hitting approach and power potential.
"""

from typing import Dict, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class BattedBallPitchDataAggregator:
    """Enhanced aggregator with batted ball profile metrics."""

    # Minimum sample sizes
    MIN_PITCHES_BATTER = 50
    MIN_BALLS_IN_PLAY = 20  # Need sufficient balls in play for batted ball metrics

    # Enhanced metric weights including batted ball profiles (must sum to 1.0)
    BATTED_BALL_HITTER_WEIGHTS = {
        # Original enhanced metrics (60%)
        'contact_rate': 0.12,
        'whiff_rate': 0.10,
        'two_strike_contact': 0.10,
        'discipline_score': 0.10,
        'productive_swing_rate': 0.08,
        'in_play_rate': 0.06,
        'first_pitch_approach': 0.02,
        'ahead_selectivity': 0.02,

        # Batted ball profile metrics (40%)
        'line_drive_rate': 0.10,      # Line drives are best outcome
        'ground_ball_rate': 0.05,      # Ground balls (context dependent)
        'fly_ball_rate': 0.05,         # Fly balls (power potential)
        'hard_hit_rate': 0.08,         # Hard contact is key
        'spray_ability': 0.06,         # Ability to use all fields
        'pull_fly_ball_rate': 0.06     # Power indicator
    }

    def __init__(self, db: AsyncSession):
        """Initialize the aggregator with database session."""
        self.db = db

    async def _check_season_status(self) -> Dict:
        """Check if we're in the offseason and should use full season data."""
        from datetime import datetime

        season_end = datetime(2025, 10, 7)
        today = datetime.now()
        days_since_end = (today - season_end).days
        use_full_season = days_since_end > 7

        return {
            'use_full_season': use_full_season,
            'current_year': 2025,
            'days_since_end': days_since_end
        }

    async def get_comprehensive_hitter_metrics(
        self,
        mlb_player_id: str,
        level: str,
        days: int = 60
    ) -> Optional[Dict]:
        """
        Calculate comprehensive hitter metrics including batted ball profiles.

        Args:
            mlb_player_id: MLB Stats API player ID
            level: MiLB level for percentile comparison
            days: Number of days to look back (ignored if in offseason)

        Returns:
            Dict with comprehensive metrics including batted ball data
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

        logger.info(f"Comprehensive metrics for hitter {mlb_player_id}: {total_pitches} pitches at {levels_played}")

        # Build comprehensive query including batted ball data
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
                        COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) as balls_in_play,

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

                        -- Zone awareness
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate
                    FROM pitch_data
                ),
                count_situations AS (
                    SELECT
                        -- Two strike approach
                        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2), 0) as two_strike_contact_rate,

                        -- First pitch
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
                ),
                batted_ball_metrics AS (
                    SELECT
                        -- Batted ball types
                        COUNT(*) FILTER (WHERE trajectory = 'ground_ball') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as ground_ball_rate,
                        COUNT(*) FILTER (WHERE trajectory = 'line_drive') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as line_drive_rate,
                        COUNT(*) FILTER (WHERE trajectory = 'fly_ball') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as fly_ball_rate,
                        COUNT(*) FILTER (WHERE trajectory = 'popup') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as popup_rate,

                        -- Contact quality
                        COUNT(*) FILTER (WHERE hardness = 'hard') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hardness IS NOT NULL), 0) as hard_hit_rate,
                        COUNT(*) FILTER (WHERE hardness = 'soft') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hardness IS NOT NULL), 0) as soft_hit_rate,

                        -- Spray chart (using hit_location field zones)
                        COUNT(*) FILTER (WHERE hit_location IN (7, 78, 4, 1)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hit_location IS NOT NULL), 0) as pull_rate,
                        COUNT(*) FILTER (WHERE hit_location IN (8, 5, 2)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hit_location IS NOT NULL), 0) as center_rate,
                        COUNT(*) FILTER (WHERE hit_location IN (9, 89, 6, 3)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hit_location IS NOT NULL), 0) as oppo_rate,

                        -- Pull fly balls (power indicator)
                        COUNT(*) FILTER (WHERE trajectory = 'fly_ball' AND hit_location IN (7, 78)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory = 'fly_ball'), 0) as pull_fly_ball_rate,

                        -- Data availability
                        COUNT(*) FILTER (WHERE trajectory IS NOT NULL) as with_trajectory,
                        COUNT(*) FILTER (WHERE hardness IS NOT NULL) as with_hardness,
                        COUNT(*) FILTER (WHERE hit_location IS NOT NULL) as with_hit_location
                    FROM pitch_data
                    WHERE contact = TRUE AND foul = FALSE  -- Only balls in play
                )
                SELECT
                    b.*,
                    c.*,
                    bb.*,
                    -- Calculate discipline score
                    (
                        COALESCE(b.contact_rate, 75) * 0.30 +
                        (100 - COALESCE(b.whiff_rate, 25)) * 0.30 +
                        (100 - COALESCE(b.chase_rate, 35)) * 0.20 +
                        CASE
                            WHEN b.productive_swing_rate BETWEEN 35 AND 45 THEN 100
                            WHEN b.productive_swing_rate BETWEEN 30 AND 50 THEN 75
                            ELSE 50
                        END * 0.20
                    ) as discipline_score
                FROM basic_metrics b, count_situations c, batted_ball_metrics bb
            """)

            query_params = {
                'mlb_player_id': int(mlb_player_id),
                'levels': levels_played,
                'season': season_info['current_year']
            }
        else:
            # Similar query but with date filtering
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
                        COUNT(*) FILTER (WHERE contact = TRUE AND foul = FALSE) as balls_in_play,

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

                        -- Zone awareness
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate
                    FROM pitch_data
                ),
                count_situations AS (
                    SELECT
                        -- Two strike approach
                        COUNT(*) FILTER (WHERE contact = TRUE AND strikes = 2) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE AND strikes = 2), 0) as two_strike_contact_rate,

                        -- First pitch
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
                ),
                batted_ball_metrics AS (
                    SELECT
                        -- Batted ball types
                        COUNT(*) FILTER (WHERE trajectory = 'ground_ball') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as ground_ball_rate,
                        COUNT(*) FILTER (WHERE trajectory = 'line_drive') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as line_drive_rate,
                        COUNT(*) FILTER (WHERE trajectory = 'fly_ball') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as fly_ball_rate,
                        COUNT(*) FILTER (WHERE trajectory = 'popup') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory IS NOT NULL), 0) as popup_rate,

                        -- Contact quality
                        COUNT(*) FILTER (WHERE hardness = 'hard') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hardness IS NOT NULL), 0) as hard_hit_rate,
                        COUNT(*) FILTER (WHERE hardness = 'soft') * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hardness IS NOT NULL), 0) as soft_hit_rate,

                        -- Spray chart
                        COUNT(*) FILTER (WHERE hit_location IN (7, 78, 4, 1)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hit_location IS NOT NULL), 0) as pull_rate,
                        COUNT(*) FILTER (WHERE hit_location IN (8, 5, 2)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hit_location IS NOT NULL), 0) as center_rate,
                        COUNT(*) FILTER (WHERE hit_location IN (9, 89, 6, 3)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE hit_location IS NOT NULL), 0) as oppo_rate,

                        -- Pull fly balls (power indicator)
                        COUNT(*) FILTER (WHERE trajectory = 'fly_ball' AND hit_location IN (7, 78)) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE trajectory = 'fly_ball'), 0) as pull_fly_ball_rate,

                        -- Data availability
                        COUNT(*) FILTER (WHERE trajectory IS NOT NULL) as with_trajectory,
                        COUNT(*) FILTER (WHERE hardness IS NOT NULL) as with_hardness,
                        COUNT(*) FILTER (WHERE hit_location IS NOT NULL) as with_hit_location
                    FROM pitch_data
                    WHERE contact = TRUE AND foul = FALSE  -- Only balls in play
                )
                SELECT
                    b.*,
                    c.*,
                    bb.*,
                    -- Calculate discipline score
                    (
                        COALESCE(b.contact_rate, 75) * 0.30 +
                        (100 - COALESCE(b.whiff_rate, 25)) * 0.30 +
                        (100 - COALESCE(b.chase_rate, 35)) * 0.20 +
                        CASE
                            WHEN b.productive_swing_rate BETWEEN 35 AND 45 THEN 100
                            WHEN b.productive_swing_rate BETWEEN 30 AND 50 THEN 75
                            ELSE 50
                        END * 0.20
                    ) as discipline_score
                FROM basic_metrics b, count_situations c, batted_ball_metrics bb
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
                logger.info(f"Insufficient data: {row[0] if row else 0} pitches")
                return None

            # Extract all metrics from row
            metrics = {
                # Basic metrics
                'contact_rate': float(row[6]) if row[6] is not None else None,
                'whiff_rate': float(row[7]) if row[7] is not None else None,
                'in_play_rate': float(row[8]) if row[8] is not None else None,
                'productive_swing_rate': float(row[9]) if row[9] is not None else None,
                'chase_rate': float(row[10]) if row[10] is not None else None,

                # Count situations
                'two_strike_contact_rate': float(row[11]) if row[11] is not None else None,
                'first_pitch_swing_rate': float(row[12]) if row[12] is not None else None,
                'ahead_swing_rate': float(row[13]) if row[13] is not None else None,
                'behind_contact_rate': float(row[14]) if row[14] is not None else None,

                # Batted ball types
                'ground_ball_rate': float(row[15]) if row[15] is not None else None,
                'line_drive_rate': float(row[16]) if row[16] is not None else None,
                'fly_ball_rate': float(row[17]) if row[17] is not None else None,
                'popup_rate': float(row[18]) if row[18] is not None else None,

                # Contact quality
                'hard_hit_rate': float(row[19]) if row[19] is not None else None,
                'soft_hit_rate': float(row[20]) if row[20] is not None else None,

                # Spray chart
                'pull_rate': float(row[21]) if row[21] is not None else None,
                'center_rate': float(row[22]) if row[22] is not None else None,
                'oppo_rate': float(row[23]) if row[23] is not None else None,

                # Power indicator
                'pull_fly_ball_rate': float(row[24]) if row[24] is not None else None,

                # Calculated
                'discipline_score': float(row[28]) if row[28] is not None else None
            }

            # Calculate spray ability score (balanced approach is better)
            if all(metrics.get(k) is not None for k in ['pull_rate', 'center_rate', 'oppo_rate']):
                # Ideal is roughly 33/33/33, penalize extremes
                pull = metrics['pull_rate']
                center = metrics['center_rate']
                oppo = metrics['oppo_rate']

                # Calculate balance score (100 = perfect balance, lower = more extreme)
                min_pct = min(pull, center, oppo)
                max_pct = max(pull, center, oppo)
                balance = 100 - (max_pct - min_pct)
                metrics['spray_ability'] = balance

            # Calculate power score (composite of power indicators)
            # Combines hard hit rate, fly ball rate, and pull fly ball rate
            power_components = []
            weights_sum = 0

            if metrics.get('hard_hit_rate') is not None:
                # Hard hit rate is most important (50% weight)
                power_components.append(metrics['hard_hit_rate'] * 0.50)
                weights_sum += 0.50

            if metrics.get('fly_ball_rate') is not None:
                # Fly ball rate indicates loft ability (25% weight)
                power_components.append(metrics['fly_ball_rate'] * 0.25)
                weights_sum += 0.25

            if metrics.get('pull_fly_ball_rate') is not None:
                # Pull fly balls are most likely to be home runs (25% weight)
                power_components.append(metrics['pull_fly_ball_rate'] * 0.25)
                weights_sum += 0.25

            if power_components and weights_sum > 0:
                # Normalize by actual weights used
                metrics['power_score'] = sum(power_components) / weights_sum

            # Log available metrics
            available_metrics = [k for k, v in metrics.items() if v is not None]
            logger.info(f"Available comprehensive metrics for {mlb_player_id}: {len(available_metrics)} metrics")

            # Log batted ball data availability
            balls_in_play = row[5]
            with_trajectory = row[25]
            with_hardness = row[26]
            with_hit_location = row[27]

            logger.info(f"Batted ball data: {balls_in_play} balls in play, "
                       f"{with_trajectory} with trajectory, {with_hardness} with hardness, "
                       f"{with_hit_location} with hit location")

            # Calculate percentiles
            percentiles = await self._calculate_comprehensive_percentiles(metrics, level)

            # Determine comparison level
            comparison_level = level if level in levels_played else levels_played[0]

            return {
                'metrics': metrics,
                'percentiles': percentiles,
                'sample_size': row[0],
                'balls_in_play': balls_in_play,
                'swings': row[1],
                'level': comparison_level,
                'levels_included': levels_played,
                'metrics_available': len(available_metrics),
                'batted_ball_data': {
                    'with_trajectory': with_trajectory,
                    'with_hardness': with_hardness,
                    'with_hit_location': with_hit_location
                },
                'comprehensive_metrics': True
            }

        except Exception as e:
            logger.error(f"Error calculating comprehensive hitter metrics: {e}")
            return None

    async def _calculate_comprehensive_percentiles(
        self,
        metrics: Dict,
        level: str
    ) -> Dict:
        """Calculate percentiles for comprehensive metrics including batted balls."""
        percentiles = {}

        # Contact metrics
        if metrics.get('contact_rate') is not None:
            percentiles['contact_rate'] = self._estimate_percentile(
                metrics['contact_rate'], [65, 72, 78, 83, 87], higher_is_better=True
            )

        if metrics.get('whiff_rate') is not None:
            percentiles['whiff_rate'] = self._estimate_percentile(
                metrics['whiff_rate'], [35, 28, 22, 17, 13], higher_is_better=False
            )

        # Two-strike and approach metrics
        if metrics.get('two_strike_contact_rate') is not None:
            percentiles['two_strike_contact'] = self._estimate_percentile(
                metrics['two_strike_contact_rate'], [60, 68, 75, 80, 85], higher_is_better=True
            )

        if metrics.get('discipline_score') is not None:
            percentiles['discipline_score'] = self._estimate_percentile(
                metrics['discipline_score'], [50, 58, 65, 72, 80], higher_is_better=True
            )

        if metrics.get('productive_swing_rate') is not None:
            percentiles['productive_swing_rate'] = self._estimate_percentile(
                metrics['productive_swing_rate'], [25, 30, 35, 40, 45], higher_is_better=True
            )

        if metrics.get('in_play_rate') is not None:
            percentiles['in_play_rate'] = self._estimate_percentile(
                metrics['in_play_rate'], [12, 15, 18, 22, 26], higher_is_better=True
            )

        # Batted ball types
        if metrics.get('line_drive_rate') is not None:
            # Line drives are best outcome
            percentiles['line_drive_rate'] = self._estimate_percentile(
                metrics['line_drive_rate'], [18, 21, 23, 26, 30], higher_is_better=True
            )

        if metrics.get('ground_ball_rate') is not None:
            # Ground balls - moderate is better (too high or low is bad)
            gb = metrics['ground_ball_rate']
            if 40 <= gb <= 50:
                percentiles['ground_ball_rate'] = 70
            elif 35 <= gb <= 55:
                percentiles['ground_ball_rate'] = 50
            else:
                percentiles['ground_ball_rate'] = 30

        if metrics.get('fly_ball_rate') is not None:
            # Fly balls - moderate to high can be good for power
            percentiles['fly_ball_rate'] = self._estimate_percentile(
                metrics['fly_ball_rate'], [20, 24, 28, 32, 38], higher_is_better=True
            )

        # Contact quality
        if metrics.get('hard_hit_rate') is not None:
            percentiles['hard_hit_rate'] = self._estimate_percentile(
                metrics['hard_hit_rate'], [5, 7, 9, 12, 15], higher_is_better=True
            )

        # Spray and power
        if metrics.get('spray_ability') is not None:
            # Higher score means more balanced spray
            percentiles['spray_ability'] = self._estimate_percentile(
                metrics['spray_ability'], [40, 50, 60, 70, 80], higher_is_better=True
            )

        if metrics.get('pull_fly_ball_rate') is not None:
            # Pull fly balls indicate power potential
            percentiles['pull_fly_ball_rate'] = self._estimate_percentile(
                metrics['pull_fly_ball_rate'], [15, 25, 35, 45, 55], higher_is_better=True
            )

        if metrics.get('power_score') is not None:
            # Power score composite - higher is better
            percentiles['power_score'] = self._estimate_percentile(
                metrics['power_score'], [8, 12, 16, 22, 30], higher_is_better=True
            )

        # First pitch and count leverage
        if metrics.get('first_pitch_swing_rate') is not None:
            fps = metrics['first_pitch_swing_rate']
            if 25 <= fps <= 35:
                percentiles['first_pitch_approach'] = 80
            elif 20 <= fps <= 40:
                percentiles['first_pitch_approach'] = 60
            else:
                percentiles['first_pitch_approach'] = 40

        if metrics.get('ahead_swing_rate') is not None:
            percentiles['ahead_selectivity'] = self._estimate_percentile(
                metrics['ahead_swing_rate'], [50, 45, 40, 35, 30], higher_is_better=False
            )

        # Fill missing with defaults
        for metric in self.BATTED_BALL_HITTER_WEIGHTS:
            if metric not in percentiles:
                percentiles[metric] = 50.0

        return percentiles

    def _estimate_percentile(
        self,
        value: float,
        thresholds: List[float],
        higher_is_better: bool = True
    ) -> float:
        """Estimate percentile based on threshold values."""
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

    async def calculate_comprehensive_composite(
        self,
        percentiles: Dict,
        is_hitter: bool = True
    ) -> Tuple[float, Dict]:
        """
        Calculate weighted composite from comprehensive metrics.

        Returns:
            Tuple of (composite_score, contributions)
        """
        weights = self.BATTED_BALL_HITTER_WEIGHTS

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