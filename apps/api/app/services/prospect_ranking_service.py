"""
Prospect Ranking Service - Composite Rankings Algorithm

Combines FanGraphs expert scouting grades with recent MiLB performance data
to generate dynamic prospect rankings.

Algorithm Components:
1. Base Score: FanGraphs FV (40-70 scale)
2. Performance Modifier: Recent MiLB stats vs level peers (±10)
3. Trend Adjustment: 30-day vs 60-day comparison (±5)
4. Age Bonus: Young for level premium (0 to +5)

See RANKING_ALGORITHM_DESIGN.md for full specification.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import text, select, func, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.pitch_data_aggregator import PitchDataAggregator
try:
    from app.services.pitch_data_aggregator_enhanced import EnhancedPitchDataAggregator
    ENHANCED_METRICS_AVAILABLE = True
except ImportError:
    ENHANCED_METRICS_AVAILABLE = False
import logging
import os

logger = logging.getLogger(__name__)


class ProspectRankingService:
    """Service for calculating composite prospect rankings."""

    # Age benchmarks by level (typical age for each level)
    AGE_BENCHMARKS = {
        'AAA': 24,
        'AA': 23,
        'A+': 22,
        'A': 21,
        'Rookie': 20,
        'Complex': 19,
        'DSL': 18
    }

    # Minimum sample sizes for stats to be considered
    MIN_PLATE_APPEARANCES = 50
    MIN_INNINGS_PITCHED = 20

    def __init__(self, db: AsyncSession):
        """Initialize the ranking service with database session."""
        self.db = db

    async def get_base_score(self, prospect_data: Dict) -> Optional[float]:
        """
        Get base FanGraphs FV score for a prospect.

        Args:
            prospect_data: Dictionary containing prospect information

        Returns:
            FV score (40-70 scale) or None if no FanGraphs grade exists
        """
        fv = prospect_data.get('fangraphs_fv')

        if fv is None:
            return None

        # Ensure FV is in valid range
        if not (40 <= fv <= 70):
            logger.warning(f"FV {fv} outside expected range 40-70 for prospect {prospect_data.get('name')}")

        return float(fv)

    async def calculate_performance_modifier(
        self,
        prospect_data: Dict,
        recent_stats: Optional[Dict],
        is_hitter: bool
    ) -> Tuple[float, Optional[Dict]]:
        """
        Calculate performance modifier using pitch-level data when available.

        Priority:
        1. Pitch-level metrics (preferred) - weighted composite percentiles
        2. Game log aggregates (fallback) - OPS/ERA percentiles
        3. No recent data - return 0.0

        Args:
            prospect_data: Dictionary containing prospect information
            recent_stats: Recent performance statistics (last 60 days)
            is_hitter: True for hitters, False for pitchers

        Returns:
            Tuple of (modifier_score, detailed_breakdown)
        """
        if not recent_stats:
            return 0.0, None

        # Get level and player ID
        level = recent_stats.get('recent_level') or prospect_data.get('current_level')
        mlb_player_id = prospect_data.get('mlb_player_id')

        if not level or not mlb_player_id:
            logger.warning(f"Missing level or player ID for {prospect_data.get('name')}")
            return 0.0, None

        # Try pitch-level data first (preferred method)
        # Use enhanced aggregator if available for more comprehensive metrics
        use_enhanced = ENHANCED_METRICS_AVAILABLE and os.getenv('USE_ENHANCED_METRICS', 'true').lower() == 'true'

        if use_enhanced:
            logger.info(f"Using enhanced pitch metrics for {prospect_data.get('name')}")
            pitch_aggregator = EnhancedPitchDataAggregator(self.db)
        else:
            pitch_aggregator = PitchDataAggregator(self.db)

        try:
            # Skip pitch data aggregation if we're processing many prospects (performance optimization)
            # TODO: Implement batch processing for pitch metrics
            if os.getenv('SKIP_PITCH_METRICS', 'false').lower() == 'true':
                logger.info(f"Skipping pitch metrics for {prospect_data.get('name')} (performance mode)")
                pitch_metrics = None
            else:
                logger.info(f"Attempting to fetch pitch data for {prospect_data.get('name')} (ID: {mlb_player_id}, Level: {level})")

                # Add timeout to prevent slow queries from blocking the entire request
                import asyncio
                try:
                    if use_enhanced:
                        # Use enhanced metrics with more comprehensive data
                        if is_hitter:
                            pitch_metrics = await asyncio.wait_for(
                                pitch_aggregator.get_enhanced_hitter_metrics(mlb_player_id, level, days=60),
                                timeout=3.0  # Slightly longer timeout for enhanced metrics
                            )
                        else:
                            pitch_metrics = await asyncio.wait_for(
                                pitch_aggregator.get_enhanced_pitcher_metrics(mlb_player_id, level, days=60),
                                timeout=3.0  # Slightly longer timeout for enhanced metrics
                            )
                    else:
                        # Use standard metrics
                        if is_hitter:
                            pitch_metrics = await asyncio.wait_for(
                                pitch_aggregator.get_hitter_pitch_metrics(mlb_player_id, level, days=60),
                                timeout=2.0  # 2 second timeout per player
                            )
                        else:
                            pitch_metrics = await asyncio.wait_for(
                                pitch_aggregator.get_pitcher_pitch_metrics(mlb_player_id, level, days=60),
                                timeout=2.0  # 2 second timeout per player
                            )
                except asyncio.TimeoutError:
                    logger.warning(f"Pitch metrics timeout for {prospect_data.get('name')} - using fallback")
                    pitch_metrics = None

            # Use pitch data if available
            if pitch_metrics:
                logger.info(f"Successfully retrieved pitch data for {prospect_data.get('name')}: {pitch_metrics.get('sample_size', 0)} pitches")
                # Get OPS/K-BB% percentile for weighted composite
                ops_percentile = await self._estimate_percentile(
                    recent_stats.get('recent_ops'), level, is_hitter
                ) if is_hitter else 50.0

                k_bb_percentile = 50.0  # TODO: Calculate from game logs
                if not is_hitter and recent_stats.get('recent_k_rate') and recent_stats.get('recent_bb_rate'):
                    k_minus_bb = recent_stats['recent_k_rate'] - recent_stats['recent_bb_rate']
                    k_bb_percentile = await self._estimate_k_bb_percentile(k_minus_bb, level)

                # Calculate weighted composite
                if use_enhanced and hasattr(pitch_aggregator, 'calculate_enhanced_composite'):
                    # Use enhanced composite calculation for more nuanced evaluation
                    composite_percentile, contributions = await pitch_aggregator.calculate_enhanced_composite(
                        pitch_metrics['percentiles'],
                        is_hitter
                    )
                else:
                    # Use standard composite calculation
                    composite_percentile, contributions = await pitch_aggregator.calculate_weighted_composite(
                        pitch_metrics['percentiles'],
                        is_hitter,
                        ops_percentile=ops_percentile,
                        k_minus_bb_percentile=k_bb_percentile
                    )

                # Convert percentile to modifier
                modifier = pitch_aggregator.percentile_to_modifier(composite_percentile)

                breakdown = {
                    'source': 'pitch_data',
                    'composite_percentile': composite_percentile,
                    'metrics': pitch_metrics['metrics'],
                    'percentiles': pitch_metrics['percentiles'],
                    'weighted_contributions': contributions,
                    'sample_size': pitch_metrics['sample_size'],
                    'days_covered': pitch_metrics['days_covered'],
                    'level': pitch_metrics['level']
                }

                logger.info(
                    f"Using pitch data for {prospect_data.get('name')}: "
                    f"{composite_percentile:.1f}%ile → {modifier:+.1f} modifier"
                )

                return modifier, breakdown
            else:
                logger.info(f"No pitch data available for {prospect_data.get('name')} (ID: {mlb_player_id})")

        except Exception as e:
            logger.error(f"Error calculating pitch-based modifier for {prospect_data.get('name')}: {e}", exc_info=True)
            # Fall through to game log fallback

        # Fallback to game log metrics (OPS/ERA)
        logger.info(f"Using game log fallback for {prospect_data.get('name')} - either no pitch data or error occurred")

        # Check for insufficient sample size in game logs
        if is_hitter:
            if not recent_stats.get('recent_games') or recent_stats['recent_games'] < 10:
                return 0.0, {'source': 'insufficient_data', 'note': 'Less than 10 games'}
            metric = recent_stats.get('recent_ops')
        else:
            if not recent_stats.get('recent_games') or recent_stats['recent_games'] < 5:
                return 0.0, {'source': 'insufficient_data', 'note': 'Less than 5 games'}
            metric = recent_stats.get('recent_era')

        if metric is None:
            return 0.0, {'source': 'no_data', 'note': 'No metric value'}

        # Calculate percentile using game log thresholds
        percentile = await self._estimate_percentile(metric, level, is_hitter)

        # Convert percentile to modifier
        if percentile >= 90:
            modifier = 10.0
        elif percentile >= 75:
            modifier = 5.0
        elif percentile >= 60:
            modifier = 2.0
        elif percentile >= 40:
            modifier = 0.0
        elif percentile >= 25:
            modifier = -5.0
        else:
            modifier = -10.0

        breakdown = {
            'source': 'game_logs',
            'metric': 'OPS' if is_hitter else 'ERA',
            'value': metric,
            'percentile': percentile,
            'games': recent_stats.get('recent_games'),
            'level': level
        }

        return modifier, breakdown

    async def _estimate_percentile(
        self,
        stat_value: float,
        level: str,
        is_hitter: bool
    ) -> float:
        """
        Estimate percentile for a stat value at a given level.

        This is a simplified version using statistical thresholds.
        Production version should query actual league percentiles.

        Args:
            stat_value: The statistic value (OPS for hitters, ERA for pitchers)
            level: MiLB level
            is_hitter: True for hitters, False for pitchers

        Returns:
            Estimated percentile (0-100)
        """
        if is_hitter:
            # OPS thresholds by level (approximate)
            thresholds = {
                'AAA': {'p90': 0.900, 'p75': 0.820, 'p50': 0.750, 'p25': 0.680},
                'AA': {'p90': 0.920, 'p75': 0.840, 'p50': 0.770, 'p25': 0.700},
                'A+': {'p90': 0.940, 'p75': 0.860, 'p50': 0.790, 'p25': 0.720},
                'A': {'p90': 0.960, 'p75': 0.880, 'p50': 0.810, 'p25': 0.740},
            }
        else:
            # ERA thresholds by level (lower is better)
            thresholds = {
                'AAA': {'p90': 2.80, 'p75': 3.40, 'p50': 4.00, 'p25': 4.60},
                'AA': {'p90': 2.60, 'p75': 3.20, 'p50': 3.80, 'p25': 4.40},
                'A+': {'p90': 2.40, 'p75': 3.00, 'p50': 3.60, 'p25': 4.20},
                'A': {'p90': 2.20, 'p75': 2.80, 'p50': 3.40, 'p25': 4.00},
            }

        # Get thresholds for level (default to AA if not found)
        level_thresholds = thresholds.get(level, thresholds.get('AA', {}))

        if not level_thresholds:
            return 50.0  # Default to median

        # Estimate percentile based on thresholds
        if is_hitter:
            # Higher is better for hitters
            if stat_value >= level_thresholds['p90']:
                return 95.0
            elif stat_value >= level_thresholds['p75']:
                return 82.5
            elif stat_value >= level_thresholds['p50']:
                return 62.5
            elif stat_value >= level_thresholds['p25']:
                return 37.5
            else:
                return 15.0
        else:
            # Lower is better for pitchers
            if stat_value <= level_thresholds['p90']:
                return 95.0
            elif stat_value <= level_thresholds['p75']:
                return 82.5
            elif stat_value <= level_thresholds['p50']:
                return 62.5
            elif stat_value <= level_thresholds['p25']:
                return 37.5
            else:
                return 15.0

    async def calculate_trend_adjustment(
        self,
        recent_stats: Optional[Dict],
        previous_stats: Optional[Dict],
        is_hitter: bool
    ) -> float:
        """
        Calculate trend adjustment based on performance change.

        Args:
            recent_stats: Last 30 days statistics
            previous_stats: Previous 30 days statistics (30-60 days ago)
            is_hitter: True for hitters, False for pitchers

        Returns:
            Trend adjustment (-5 to +5)
        """
        if not recent_stats or not previous_stats:
            return 0.0

        if is_hitter:
            recent_metric = recent_stats.get('recent_ops')
            previous_metric = previous_stats.get('previous_ops')
        else:
            recent_metric = recent_stats.get('recent_era')
            previous_metric = previous_stats.get('previous_era')

        if recent_metric is None or previous_metric is None or previous_metric == 0:
            return 0.0

        # Calculate improvement rate
        if is_hitter:
            # Higher is better for hitters
            improvement = (recent_metric - previous_metric) / previous_metric
        else:
            # Lower is better for pitchers (inverted)
            improvement = (previous_metric - recent_metric) / previous_metric

        # Convert to adjustment
        if improvement > 0.15:  # 15%+ improvement
            return 5.0
        elif improvement > 0.05:  # 5-15% improvement
            return 2.0
        elif improvement < -0.15:  # 15%+ decline
            return -5.0
        elif improvement < -0.05:  # 5-15% decline
            return -2.0
        else:
            return 0.0

    async def calculate_age_adjustment(
        self,
        age: Optional[int],
        level: Optional[str]
    ) -> float:
        """
        Calculate age adjustment (bonus/penalty) based on age relative to level.

        Young players at advanced levels get bonuses (positive signal).
        Old players at lower levels get penalties (negative signal).

        Args:
            age: Prospect's age
            level: Current MiLB level

        Returns:
            Age adjustment (-5 to +5)
        """
        if not age or not level:
            return 0.0

        # Get age benchmark for level
        benchmark_age = self.AGE_BENCHMARKS.get(level)

        if not benchmark_age:
            return 0.0

        # Calculate age difference (positive = younger, negative = older)
        age_difference = benchmark_age - age

        # Convert to adjustment (bonuses for young, penalties for old)
        if age_difference >= 3:    # 3+ years younger than typical
            return 5.0
        elif age_difference >= 2:  # 2 years younger
            return 3.0
        elif age_difference >= 1:  # 1 year younger
            return 1.0
        elif age_difference <= -3: # 3+ years OLDER than typical
            return -5.0
        elif age_difference <= -2: # 2 years older
            return -3.0
        elif age_difference <= -1: # 1 year older
            return -1.0
        else:
            return 0.0

    async def calculate_composite_score(
        self,
        prospect_data: Dict
    ) -> Dict[str, float]:
        """
        Calculate final composite score for a prospect.

        Args:
            prospect_data: Dictionary containing all prospect information

        Returns:
            Dictionary with score breakdown
        """
        # Get base FV score
        base_score = await self.get_base_score(prospect_data)

        if base_score is None:
            return {
                'composite_score': 0.0,
                'base_fv': 0.0,
                'performance_modifier': 0.0,
                'trend_adjustment': 0.0,
                'age_bonus': 0.0,
                'total_adjustment': 0.0,
                'note': 'No FanGraphs grade available'
            }

        # Determine if hitter or pitcher
        position = prospect_data.get('position', '')
        is_hitter = position not in ['SP', 'RP', 'P', 'RHP', 'LHP']

        # Get recent stats (full 2025 season)
        recent_stats = {
            'recent_ops': prospect_data.get('recent_ops'),
            'recent_era': prospect_data.get('recent_era'),
            'recent_games': prospect_data.get('recent_games'),
            'recent_level': prospect_data.get('recent_level'),
            'recent_k_rate': prospect_data.get('recent_k_rate'),
            'recent_bb_rate': prospect_data.get('recent_bb_rate')
        }

        previous_stats = {
            'previous_ops': prospect_data.get('previous_ops'),
            'previous_era': prospect_data.get('previous_era')
        }

        # Calculate individual modifiers (now returns tuple with breakdown)
        performance_mod, performance_breakdown = await self.calculate_performance_modifier(
            prospect_data, recent_stats, is_hitter
        )

        trend_mod = await self.calculate_trend_adjustment(
            recent_stats, previous_stats, is_hitter
        )

        # Use recent_level from game logs if current_level not available
        level = prospect_data.get('current_level') or prospect_data.get('recent_level')

        age_adjustment = await self.calculate_age_adjustment(
            prospect_data.get('age'),
            level
        )

        # Calculate weighted composite
        composite = (
            base_score +
            (performance_mod * 0.5) +
            (trend_mod * 0.3) +
            (age_adjustment * 0.2)
        )

        # Apply adjustment cap (±10 points max)
        total_adjustment = composite - base_score

        if total_adjustment > 10:
            composite = base_score + 10
            total_adjustment = 10.0
        elif total_adjustment < -10:
            composite = base_score - 10
            total_adjustment = -10.0

        result = {
            'composite_score': round(composite, 1),
            'base_fv': round(base_score, 1),
            'performance_modifier': round(performance_mod, 1),
            'trend_adjustment': round(trend_mod, 1),
            'age_adjustment': round(age_adjustment, 1),
            'total_adjustment': round(total_adjustment, 1)
        }

        # Add detailed performance breakdown if available
        if performance_breakdown:
            result['performance_breakdown'] = performance_breakdown

        return result

    async def generate_prospect_rankings(
        self,
        position_filter: Optional[str] = None,
        organization_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Generate ranked list of prospects.

        Args:
            position_filter: Optional position filter (e.g., 'SS', 'SP')
            organization_filter: Optional team filter (e.g., 'Yankees')
            limit: Optional limit on number of results

        Returns:
            List of ranked prospects with scores
        """
        # Build query to get prospects with FanGraphs grades and recent MiLB data
        query = text("""
            SELECT
                p.id,
                p.name,
                p.position,
                p.organization,
                p.age,
                p.current_level,
                p.fg_player_id,
                p.mlb_player_id,

                -- FanGraphs base scores
                COALESCE(h.fv, pit.fv) as fangraphs_fv,

                -- Hitter tool grades
                h.hit_future,
                h.game_power_future,
                h.speed_future,
                h.fielding_future,

                -- Pitcher tool grades
                pit.fb_future,
                pit.sl_future,
                pit.cb_future,
                pit.ch_future,
                pit.cmd_future,

                -- Recent MiLB stats (last 60 days)
                recent.ops as recent_ops,
                recent.era as recent_era,
                recent.games_played as recent_games,
                recent.level as recent_level,

                -- Previous period stats (30-60 days ago)
                previous.ops as previous_ops,
                previous.era as previous_era

            FROM prospects p

            -- Join FanGraphs hitter grades
            LEFT JOIN fangraphs_hitter_grades h
                ON p.fg_player_id = h.fangraphs_player_id
                AND h.data_year = 2025

            -- Join FanGraphs pitcher grades
            LEFT JOIN fangraphs_pitcher_grades pit
                ON p.fg_player_id = pit.fangraphs_player_id
                AND pit.data_year = 2025

            -- Full 2025 season performance (season ended Oct 7, 2025)
            LEFT JOIN LATERAL (
                SELECT
                    AVG(CASE WHEN at_bats > 0 THEN ops END) as ops,
                    AVG(CASE WHEN innings_pitched > 0 THEN era END) as era,
                    COUNT(*) as games_played,
                    MAX(level) as level,
                    -- K rate and BB rate for pitchers
                    AVG(CASE WHEN innings_pitched > 0 THEN (strikeouts / innings_pitched * 9.0) END) as recent_k_rate,
                    AVG(CASE WHEN innings_pitched > 0 THEN (walks / innings_pitched * 9.0) END) as recent_bb_rate
                FROM milb_game_logs
                WHERE CAST(mlb_player_id AS VARCHAR) = p.mlb_player_id
                    AND season = 2025
            ) recent ON true

            -- Last 30 days of season for trend (Sept 8 - Oct 7, 2025)
            LEFT JOIN LATERAL (
                SELECT
                    AVG(CASE WHEN at_bats > 0 THEN ops END) as ops,
                    AVG(CASE WHEN innings_pitched > 0 THEN era END) as era
                FROM milb_game_logs
                WHERE CAST(mlb_player_id AS VARCHAR) = p.mlb_player_id
                    AND season = 2025
                    AND game_date >= '2025-09-08'::date
            ) previous ON true

            WHERE (h.fv IS NOT NULL OR pit.fv IS NOT NULL)
            {position_clause}
            {org_clause}
            ORDER BY COALESCE(h.fv, pit.fv) DESC
            {limit_clause}
        """.format(
            position_clause=f"AND p.position = '{position_filter}'" if position_filter else "",
            org_clause=f"AND p.organization = '{organization_filter}'" if organization_filter else "",
            limit_clause=f"LIMIT {limit}" if limit else ""
        ))

        result = await self.db.execute(query)
        prospects_data = result.fetchall()

        # Calculate composite scores for each prospect
        ranked_prospects = []

        for row in prospects_data:
            # Convert row to dictionary
            prospect_dict = {
                'id': row[0],
                'name': row[1],
                'position': row[2],
                'organization': row[3],
                'age': row[4],
                'current_level': row[5],
                'fg_player_id': row[6],
                'mlb_player_id': row[7],
                'fangraphs_fv': row[8],
                'hit_future': row[9],
                'game_power_future': row[10],
                'speed_future': row[11],
                'fielding_future': row[12],
                'fb_future': row[13],
                'sl_future': row[14],
                'cb_future': row[15],
                'ch_future': row[16],
                'cmd_future': row[17],
                'recent_ops': row[18],
                'recent_era': row[19],
                'recent_games': row[20],
                'recent_level': row[21],
                'recent_k_rate': row[22],
                'recent_bb_rate': row[23],
                'previous_ops': row[24],
                'previous_era': row[25]
            }

            # Calculate composite score
            scores = await self.calculate_composite_score(prospect_dict)

            # Build result object
            # Use recent_level if current_level is not available
            level_display = prospect_dict.get('current_level') or prospect_dict.get('recent_level')

            ranked_prospects.append({
                'prospect_id': prospect_dict['id'],
                'name': prospect_dict['name'],
                'position': prospect_dict['position'],
                'organization': prospect_dict['organization'],
                'age': prospect_dict['age'],
                'level': level_display,
                'scores': scores,
                'tool_grades': {
                    'hit': prospect_dict.get('hit_future'),
                    'power': prospect_dict.get('game_power_future'),
                    'speed': prospect_dict.get('speed_future'),
                    'field': prospect_dict.get('fielding_future'),
                    'fastball': prospect_dict.get('fb_future'),
                    'slider': prospect_dict.get('sl_future'),
                    'curve': prospect_dict.get('cb_future'),
                    'change': prospect_dict.get('ch_future'),
                    'command': prospect_dict.get('cmd_future')
                }
            })

        # Sort by composite score (descending)
        ranked_prospects.sort(
            key=lambda x: (
                x['scores']['composite_score'],
                x['scores']['base_fv'],
                -x['age'] if x['age'] else 0
            ),
            reverse=True
        )

        # Assign ranks
        for i, prospect in enumerate(ranked_prospects):
            prospect['rank'] = i + 1

        return ranked_prospects

    async def get_trend_indicator(self, trend_adjustment: float) -> str:
        """
        Get trend indicator emoji/label for UI display.

        Args:
            trend_adjustment: Trend adjustment value

        Returns:
            Trend indicator string
        """
        if trend_adjustment >= 5:
            return "🔥 Hot"
        elif trend_adjustment >= 2:
            return "↗️ Surging"
        elif trend_adjustment <= -5:
            return "❄️ Cold"
        elif trend_adjustment <= -2:
            return "↘️ Cooling"
        else:
            return "→ Stable"

    async def get_tier_classification(self, rank: int) -> Dict[str, any]:
        """
        Get tier classification for a ranking.

        Args:
            rank: Prospect's rank

        Returns:
            Dictionary with tier info
        """
        if rank <= 10:
            return {'tier': 1, 'label': 'Elite', 'stars': '★★★★★'}
        elif rank <= 25:
            return {'tier': 2, 'label': 'Top Prospects', 'stars': '★★★★'}
        elif rank <= 50:
            return {'tier': 3, 'label': 'Strong Prospects', 'stars': '★★★'}
        elif rank <= 100:
            return {'tier': 4, 'label': 'Solid Prospects', 'stars': '★★'}
        else:
            return {'tier': 5, 'label': 'Deep Prospects', 'stars': '★'}
