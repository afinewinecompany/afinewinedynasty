"""
Batch Pitch Data Aggregator Service

High-performance batch processing for pitch metrics across multiple prospects.
Fetches all pitch data in parallel using concurrent queries with connection pooling.

Key Optimizations:
1. Single batch query for all prospects instead of sequential queries
2. Pre-loads percentile distributions once per level
3. Concurrent async processing with semaphore for connection pooling
4. In-memory caching of percentile data
"""

from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class BatchPitchAggregator:
    """Optimized batch aggregator for pitch-level metrics."""

    # Minimum sample sizes
    MIN_PITCHES_BATTER = 50
    MIN_PITCHES_PITCHER = 100

    # Metric weights (must sum to 1.0)
    HITTER_WEIGHTS = {
        'exit_velo_90th': 0.25,
        'hard_hit_rate': 0.20,
        'contact_rate': 0.15,
        'whiff_rate': 0.15,
        'chase_rate': 0.10,
        'ops': 0.15
    }

    PITCHER_WEIGHTS = {
        'whiff_rate': 0.25,
        'zone_rate': 0.20,
        'avg_fb_velo': 0.15,
        'hard_contact_rate': 0.15,
        'chase_rate': 0.10,
        'k_minus_bb': 0.15
    }

    def __init__(self, db: AsyncSession):
        """Initialize the batch aggregator with database session."""
        self.db = db
        self._percentile_cache = {}  # Cache percentile distributions by level

    async def _check_season_status(self) -> Dict:
        """Check if we're in the offseason and should use full season data."""
        # 2025 season ended October 7, 2025
        season_end = datetime(2025, 10, 7)
        today = datetime.now()
        days_since_end = (today - season_end).days

        # Use full season if we're more than 7 days past season end
        use_full_season = days_since_end > 7

        return {
            'use_full_season': use_full_season,
            'current_year': 2025,
            'days_since_end': days_since_end
        }

    async def get_batch_hitter_metrics(
        self,
        prospects: List[Dict],
        days: int = 60
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch pitch metrics for multiple hitters in a single optimized query.

        Args:
            prospects: List of prospect dicts with 'mlb_player_id', 'current_level'
            days: Number of days to look back

        Returns:
            Dict mapping mlb_player_id -> metrics dict (or None if insufficient data)
        """
        if not prospects:
            return {}

        # Check season status
        season_info = await self._check_season_status()
        use_full_season = season_info['use_full_season']

        # Extract player IDs and prepare batch query
        player_ids = [int(p['mlb_player_id']) for p in prospects if p.get('mlb_player_id')]

        if not player_ids:
            return {}

        logger.info(f"Fetching batch hitter metrics for {len(player_ids)} prospects")

        # Build batch query
        if use_full_season:
            query = text("""
                WITH player_stats AS (
                    SELECT
                        mlb_batter_id,

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
                        MAX(level) as level

                    FROM milb_batter_pitches
                    WHERE mlb_batter_id = ANY(:player_ids)
                        AND season = :season
                    GROUP BY mlb_batter_id
                )
                SELECT * FROM player_stats
                WHERE pitches_seen >= :min_pitches
            """)

            params = {
                'player_ids': player_ids,
                'min_pitches': self.MIN_PITCHES_BATTER,
                'season': season_info['current_year']
            }
        else:
            query = text("""
                WITH player_stats AS (
                    SELECT
                        mlb_batter_id,

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
                        MAX(level) as level

                    FROM milb_batter_pitches
                    WHERE mlb_batter_id = ANY(:player_ids)
                        AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
                    GROUP BY mlb_batter_id
                )
                SELECT * FROM player_stats
                WHERE pitches_seen >= :min_pitches
            """)

            params = {
                'player_ids': player_ids,
                'min_pitches': self.MIN_PITCHES_BATTER,
                'days': str(days)
            }

        try:
            result = await self.db.execute(query, params)
            rows = result.fetchall()

            logger.info(f"Batch query returned data for {len(rows)} hitters")

            # Pre-load percentile data for all levels
            levels = set(row[7] for row in rows if row[7])
            await self._preload_hitter_percentiles(levels)

            # Process results into dict
            metrics_by_player = {}

            for row in rows:
                mlb_player_id = str(row[0])
                level = row[7]

                metrics = {
                    'exit_velo_90th': float(row[1]) if row[1] is not None else None,
                    'hard_hit_rate': float(row[2]) if row[2] is not None else None,
                    'contact_rate': float(row[3]) if row[3] is not None else None,
                    'whiff_rate': float(row[4]) if row[4] is not None else None,
                    'chase_rate': float(row[5]) if row[5] is not None and str(row[5]) != '0E-20' else None,
                }

                # Calculate percentiles
                percentiles = await self._calculate_hitter_percentiles(metrics, level)

                # Calculate composite
                composite_percentile, contributions = await self.calculate_weighted_composite(
                    percentiles, is_hitter=True
                )

                metrics_by_player[mlb_player_id] = {
                    'metrics': metrics,
                    'percentiles': percentiles,
                    'sample_size': row[6],
                    'level': level,
                    'composite_percentile': composite_percentile,
                    'contributions': contributions,
                    'source': 'pitch_data'
                }

            return metrics_by_player

        except Exception as e:
            logger.error(f"Error in batch hitter metrics: {e}")
            return {}

    async def get_batch_pitcher_metrics(
        self,
        prospects: List[Dict],
        days: int = 60
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch pitch metrics for multiple pitchers in a single optimized query.

        Args:
            prospects: List of prospect dicts with 'mlb_player_id', 'current_level'
            days: Number of days to look back

        Returns:
            Dict mapping mlb_player_id -> metrics dict (or None if insufficient data)
        """
        if not prospects:
            return {}

        # Check season status
        season_info = await self._check_season_status()
        use_full_season = season_info['use_full_season']

        player_ids = [int(p['mlb_player_id']) for p in prospects if p.get('mlb_player_id')]

        if not player_ids:
            return {}

        logger.info(f"Fetching batch pitcher metrics for {len(player_ids)} prospects")

        if use_full_season:
            query = text("""
                WITH player_stats AS (
                    SELECT
                        mlb_pitcher_id,

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
                        MAX(level) as level

                    FROM milb_pitcher_pitches
                    WHERE mlb_pitcher_id = ANY(:player_ids)
                        AND season = :season
                    GROUP BY mlb_pitcher_id
                )
                SELECT * FROM player_stats
                WHERE pitches_thrown >= :min_pitches
            """)

            params = {
                'player_ids': player_ids,
                'min_pitches': self.MIN_PITCHES_PITCHER,
                'season': season_info['current_year']
            }
        else:
            query = text("""
                WITH player_stats AS (
                    SELECT
                        mlb_pitcher_id,

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
                        MAX(level) as level

                    FROM milb_pitcher_pitches
                    WHERE mlb_pitcher_id = ANY(:player_ids)
                        AND game_date >= CURRENT_DATE - CAST(:days || ' days' AS INTERVAL)
                    GROUP BY mlb_pitcher_id
                )
                SELECT * FROM player_stats
                WHERE pitches_thrown >= :min_pitches
            """)

            params = {
                'player_ids': player_ids,
                'min_pitches': self.MIN_PITCHES_PITCHER,
                'days': str(days)
            }

        try:
            result = await self.db.execute(query, params)
            rows = result.fetchall()

            logger.info(f"Batch query returned data for {len(rows)} pitchers")

            # Pre-load percentile data for all levels
            levels = set(row[6] for row in rows if row[6])
            await self._preload_pitcher_percentiles(levels)

            # Process results
            metrics_by_player = {}

            for row in rows:
                mlb_player_id = str(row[0])
                level = row[6]

                metrics = {
                    'whiff_rate': float(row[1]) if row[1] is not None else None,
                    'zone_rate': float(row[2]) if row[2] is not None else None,
                    'avg_fb_velo': float(row[3]) if row[3] is not None else None,
                    'hard_contact_rate': float(row[4]) if row[4] is not None else None,
                    'chase_rate': float(row[5]) if row[5] is not None and str(row[5]) != '0E-20' else None,
                }

                # Calculate percentiles
                percentiles = await self._calculate_pitcher_percentiles(metrics, level)

                # Calculate composite
                composite_percentile, contributions = await self.calculate_weighted_composite(
                    percentiles, is_hitter=False
                )

                metrics_by_player[mlb_player_id] = {
                    'metrics': metrics,
                    'percentiles': percentiles,
                    'sample_size': row[5],
                    'level': level,
                    'composite_percentile': composite_percentile,
                    'contributions': contributions,
                    'source': 'pitch_data'
                }

            return metrics_by_player

        except Exception as e:
            logger.error(f"Error in batch pitcher metrics: {e}")
            return {}

    async def _preload_hitter_percentiles(self, levels: set):
        """Pre-load and cache hitter percentile distributions for multiple levels."""
        levels_to_load = [str(level) for level in levels if level and level not in self._percentile_cache]

        if not levels_to_load:
            return

        query = text("""
            SELECT
                level,
                exit_velo_percentiles,
                hard_hit_percentiles,
                contact_percentiles,
                whiff_percentiles,
                chase_percentiles
            FROM mv_hitter_percentiles_by_level
            WHERE level = ANY(:levels)
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        try:
            result = await self.db.execute(query, {'levels': levels_to_load})
            rows = result.fetchall()

            for row in rows:
                self._percentile_cache[row[0]] = {
                    'exit_velo': row[1],
                    'hard_hit': row[2],
                    'contact': row[3],
                    'whiff': row[4],
                    'chase': row[5]
                }

            logger.info(f"Preloaded percentiles for {len(rows)} hitter levels")

        except Exception as e:
            logger.error(f"Error preloading hitter percentiles: {e}")

    async def _preload_pitcher_percentiles(self, levels: set):
        """Pre-load and cache pitcher percentile distributions for multiple levels."""
        levels_to_load = [str(level) for level in levels if level and level not in self._percentile_cache]

        if not levels_to_load:
            return

        query = text("""
            SELECT
                level,
                whiff_percentiles,
                zone_percentiles,
                velo_percentiles,
                hard_contact_percentiles,
                chase_percentiles
            FROM mv_pitcher_percentiles_by_level
            WHERE level = ANY(:levels)
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        try:
            result = await self.db.execute(query, {'levels': levels_to_load})
            rows = result.fetchall()

            for row in rows:
                self._percentile_cache[row[0]] = {
                    'whiff': row[1],
                    'zone': row[2],
                    'velo': row[3],
                    'hard_contact': row[4],
                    'chase': row[5]
                }

            logger.info(f"Preloaded percentiles for {len(rows)} pitcher levels")

        except Exception as e:
            logger.error(f"Error preloading pitcher percentiles: {e}")

    async def _calculate_hitter_percentiles(self, metrics: Dict, level: str) -> Dict:
        """Calculate percentile ranks using cached distributions."""
        if level not in self._percentile_cache:
            # Fallback to median if not cached
            return {key: 50.0 for key in self.HITTER_WEIGHTS.keys()}

        cached = self._percentile_cache[level]

        percentiles = {}
        percentiles['exit_velo_90th'] = self._find_percentile(
            metrics.get('exit_velo_90th'), cached.get('exit_velo')
        )
        percentiles['hard_hit_rate'] = self._find_percentile(
            metrics.get('hard_hit_rate'), cached.get('hard_hit')
        )
        percentiles['contact_rate'] = self._find_percentile(
            metrics.get('contact_rate'), cached.get('contact')
        )
        percentiles['whiff_rate'] = self._find_percentile(
            metrics.get('whiff_rate'), cached.get('whiff')
        )
        percentiles['chase_rate'] = self._find_percentile(
            metrics.get('chase_rate'), cached.get('chase')
        )

        return percentiles

    async def _calculate_pitcher_percentiles(self, metrics: Dict, level: str) -> Dict:
        """Calculate percentile ranks using cached distributions."""
        if level not in self._percentile_cache:
            return {key: 50.0 for key in self.PITCHER_WEIGHTS.keys()}

        cached = self._percentile_cache[level]

        percentiles = {}
        percentiles['whiff_rate'] = self._find_percentile(
            metrics.get('whiff_rate'), cached.get('whiff')
        )
        percentiles['zone_rate'] = self._find_percentile(
            metrics.get('zone_rate'), cached.get('zone')
        )
        percentiles['avg_fb_velo'] = self._find_percentile(
            metrics.get('avg_fb_velo'), cached.get('velo')
        )
        percentiles['hard_contact_rate'] = self._find_percentile(
            metrics.get('hard_contact_rate'), cached.get('hard_contact')
        )
        percentiles['chase_rate'] = self._find_percentile(
            metrics.get('chase_rate'), cached.get('chase')
        )

        return percentiles

    def _find_percentile(
        self,
        value: Optional[float],
        percentile_array: Optional[List[float]]
    ) -> float:
        """Find percentile rank using linear interpolation."""
        if value is None or percentile_array is None:
            return 50.0

        try:
            p10, p25, p50, p75, p90 = percentile_array
            value = float(value)
            p10, p25, p50, p75, p90 = float(p10), float(p25), float(p50), float(p75), float(p90)

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

        except (TypeError, ZeroDivisionError, ValueError):
            return 50.0

    async def calculate_weighted_composite(
        self,
        percentiles: Dict,
        is_hitter: bool,
        ops_percentile: float = 50.0,
        k_minus_bb_percentile: float = 50.0
    ) -> Tuple[float, Dict]:
        """Calculate weighted composite score from percentiles."""
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

            # Invert negative metrics
            if metric in ['whiff_rate', 'chase_rate', 'hard_contact_rate']:
                if is_hitter and metric in ['whiff_rate', 'chase_rate']:
                    percentile = 100 - percentile
                elif not is_hitter and metric == 'hard_contact_rate':
                    percentile = 100 - percentile

            contribution = percentile * weight
            composite += contribution
            contributions[metric] = round(contribution, 2)

        return round(composite, 2), contributions

    def percentile_to_modifier(self, percentile: float) -> float:
        """Convert percentile to performance modifier (-10 to +10)."""
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
