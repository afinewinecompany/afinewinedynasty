#!/usr/bin/env python3
"""
Calculate Advanced Metrics (wRC+, wOBA) from Game Logs

Implements Fangraphs-style linear weights calculations.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import asyncio
from sqlalchemy import text
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AdvancedMetricsCalculator:
    """Calculate wOBA and wRC+ from raw statistics."""

    def __init__(self, season: int = 2024):
        self.season = season

        # Linear weights for wOBA calculation (2024 values)
        self.weights = {
            'walk': 0.689,
            'hbp': 0.720,
            'single': 0.883,
            'double': 1.244,
            'triple': 1.569,
            'home_run': 2.004
        }

        # League averages (will be calculated from data)
        self.league_avg = {}

        # Park factors (default to neutral)
        self.park_factors = {}

    async def calculate_league_averages(self, level: str = 'AAA') -> Dict:
        """Calculate league average statistics for a given level."""

        query = """
            SELECT
                AVG(batting_avg) as avg_ba,
                AVG(obp) as avg_obp,
                AVG(slg) as avg_slg,
                AVG(ops) as avg_ops,
                SUM(plate_appearances) as total_pa,
                SUM(at_bats) as total_ab,
                SUM(hits) as total_h,
                SUM(walks) as total_bb,
                SUM(hit_by_pitch) as total_hbp,
                SUM(singles) as total_1b,
                SUM(doubles) as total_2b,
                SUM(triples) as total_3b,
                SUM(home_runs) as total_hr,
                SUM(sacrifice_flies) as total_sf
            FROM (
                SELECT
                    *,
                    hits - doubles - triples - home_runs as singles
                FROM milb_game_logs
                WHERE season = :season
                AND level = :level
                AND plate_appearances > 0
            ) t
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"season": self.season, "level": level}
            )
            row = result.fetchone()

        if not row or row.total_pa == 0:
            logger.warning(f"No data found for {level} in {self.season}")
            return self._get_default_averages()

        # Calculate league wOBA
        league_woba = self.calculate_woba_from_components(
            pa=row.total_pa,
            walks=row.total_bb or 0,
            hbp=row.total_hbp or 0,
            singles=row.total_1b or 0,
            doubles=row.total_2b or 0,
            triples=row.total_3b or 0,
            homers=row.total_hr or 0,
            ab=row.total_ab or 0,
            sf=row.total_sf or 0
        )

        return {
            'avg': row.avg_ba or .250,
            'obp': row.avg_obp or .320,
            'slg': row.avg_slg or .400,
            'ops': row.avg_ops or .720,
            'woba': league_woba
        }

    def calculate_woba_from_components(
        self,
        pa: int,
        walks: int,
        hbp: int,
        singles: int,
        doubles: int,
        triples: int,
        homers: int,
        ab: int,
        sf: int
    ) -> float:
        """Calculate wOBA from component stats."""

        if pa == 0:
            return 0.0

        # Apply linear weights
        numerator = (
            self.weights['walk'] * walks +
            self.weights['hbp'] * hbp +
            self.weights['single'] * singles +
            self.weights['double'] * doubles +
            self.weights['triple'] * triples +
            self.weights['home_run'] * homers
        )

        # Denominator excludes intentional walks (not tracked separately here)
        denominator = ab + walks + sf + hbp

        if denominator == 0:
            return 0.0

        return round(numerator / denominator, 3)

    def calculate_woba(self, player_stats: Dict) -> float:
        """Calculate wOBA for a player."""

        # Extract components
        pa = player_stats.get('plate_appearances', 0)
        ab = player_stats.get('at_bats', 0)
        hits = player_stats.get('hits', 0)
        doubles = player_stats.get('doubles', 0)
        triples = player_stats.get('triples', 0)
        homers = player_stats.get('home_runs', 0)
        walks = player_stats.get('walks', 0)
        hbp = player_stats.get('hit_by_pitch', 0)
        sf = player_stats.get('sacrifice_flies', 0)

        # Calculate singles
        singles = hits - doubles - triples - homers

        return self.calculate_woba_from_components(
            pa=pa,
            walks=walks,
            hbp=hbp,
            singles=singles,
            doubles=doubles,
            triples=triples,
            homers=homers,
            ab=ab,
            sf=sf
        )

    def calculate_wrc_plus(
        self,
        player_woba: float,
        league_woba: float,
        league_r_per_pa: float = 0.115,
        park_factor: float = 1.0
    ) -> int:
        """
        Calculate wRC+ (Weighted Runs Created Plus).

        Formula: ((wOBA - League wOBA) / wOBA Scale + League R/PA) * PA * 100 / League R/PA / Park Factor

        For simplification, we normalize to 100 = average.
        """

        if league_woba == 0:
            return 100

        # wOBA scale (typically around 1.15-1.25)
        woba_scale = 1.20

        # Calculate wRC+
        # Simplified formula: (player_wOBA / league_wOBA) * 100 / park_factor
        wrc_plus = ((player_woba - league_woba) / woba_scale + league_r_per_pa) / league_r_per_pa * 100

        # Adjust for park
        wrc_plus = wrc_plus / park_factor

        return round(wrc_plus)

    async def calculate_player_metrics(self, player_id: int) -> Dict:
        """Calculate wOBA and wRC+ for a player."""

        # Get player's aggregated stats
        query = """
            SELECT
                mlb_player_id,
                level,
                COUNT(*) as games,
                SUM(plate_appearances) as pa,
                SUM(at_bats) as ab,
                SUM(hits) as h,
                SUM(doubles) as d,
                SUM(triples) as t,
                SUM(home_runs) as hr,
                SUM(walks) as bb,
                SUM(hit_by_pitch) as hbp,
                SUM(sacrifice_flies) as sf,
                AVG(batting_avg) as avg,
                AVG(obp) as obp,
                AVG(slg) as slg
            FROM milb_game_logs
            WHERE mlb_player_id = :player_id
            AND season = :season
            AND plate_appearances > 0
            GROUP BY mlb_player_id, level
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"player_id": player_id, "season": self.season}
            )
            rows = result.fetchall()

        if not rows:
            return {}

        metrics = []

        for row in rows:
            level = row.level

            # Get league averages for this level
            if level not in self.league_avg:
                self.league_avg[level] = await self.calculate_league_averages(level)

            # Calculate player wOBA
            player_stats = {
                'plate_appearances': row.pa,
                'at_bats': row.ab,
                'hits': row.h,
                'doubles': row.d,
                'triples': row.t,
                'home_runs': row.hr,
                'walks': row.bb,
                'hit_by_pitch': row.hbp,
                'sacrifice_flies': row.sf
            }

            woba = self.calculate_woba(player_stats)

            # Calculate wRC+
            league_woba = self.league_avg[level]['woba']
            wrc_plus = self.calculate_wrc_plus(woba, league_woba)

            metrics.append({
                'level': level,
                'games': row.games,
                'pa': row.pa,
                'avg': row.avg,
                'obp': row.obp,
                'slg': row.slg,
                'woba': woba,
                'wrc_plus': wrc_plus
            })

        # Weight by plate appearances if multiple levels
        if len(metrics) > 1:
            total_pa = sum(m['pa'] for m in metrics)
            weighted_woba = sum(m['woba'] * m['pa'] for m in metrics) / total_pa
            weighted_wrc_plus = sum(m['wrc_plus'] * m['pa'] for m in metrics) / total_pa

            return {
                'player_id': player_id,
                'season': self.season,
                'levels': metrics,
                'overall_woba': round(weighted_woba, 3),
                'overall_wrc_plus': round(weighted_wrc_plus)
            }
        else:
            return {
                'player_id': player_id,
                'season': self.season,
                'levels': metrics,
                'overall_woba': metrics[0]['woba'],
                'overall_wrc_plus': metrics[0]['wrc_plus']
            }

    def _get_default_averages(self) -> Dict:
        """Get default league averages if data not available."""

        return {
            'avg': .250,
            'obp': .320,
            'slg': .400,
            'ops': .720,
            'woba': .315
        }

    async def batch_calculate_metrics(self, player_ids: list) -> pd.DataFrame:
        """Calculate metrics for multiple players."""

        all_metrics = []

        for i, player_id in enumerate(player_ids):
            if i % 100 == 0:
                logger.info(f"Processing player {i}/{len(player_ids)}")

            try:
                metrics = await self.calculate_player_metrics(player_id)
                if metrics:
                    all_metrics.append(metrics)
            except Exception as e:
                logger.error(f"Error processing player {player_id}: {str(e)}")
                continue

        return pd.DataFrame(all_metrics)


async def update_database_with_metrics():
    """Update database with calculated wOBA and wRC+ values."""

    calculator = AdvancedMetricsCalculator(season=2024)

    # Get all players with sufficient plate appearances
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND plate_appearances > 50
            LIMIT 100  -- Process first 100 for demo
        """))

        player_ids = [row[0] for row in result.fetchall()]

    logger.info(f"Calculating metrics for {len(player_ids)} players...")

    # Calculate metrics
    metrics_df = await calculator.batch_calculate_metrics(player_ids)

    # Save to CSV
    output_file = "calculated_metrics_2024.csv"
    metrics_df.to_csv(output_file, index=False)
    logger.info(f"Saved metrics to {output_file}")

    # Display sample
    print("\nSample Calculated Metrics:")
    print("=" * 80)
    sample = metrics_df.head(10)[['player_id', 'overall_woba', 'overall_wrc_plus']]
    print(sample)

    # Show distribution
    print("\nwRC+ Distribution:")
    print(f"  Mean: {metrics_df['overall_wrc_plus'].mean():.0f}")
    print(f"  Median: {metrics_df['overall_wrc_plus'].median():.0f}")
    print(f"  Std Dev: {metrics_df['overall_wrc_plus'].std():.1f}")
    print(f"  Min: {metrics_df['overall_wrc_plus'].min()}")
    print(f"  Max: {metrics_df['overall_wrc_plus'].max()}")


async def demo_single_player():
    """Demo calculation for a single player."""

    calculator = AdvancedMetricsCalculator(season=2024)

    # Get a sample player
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT mlb_player_id, COUNT(*) as games
            FROM milb_game_logs
            WHERE season = 2024
            AND plate_appearances > 0
            GROUP BY mlb_player_id
            ORDER BY games DESC
            LIMIT 1
        """))

        player_id = result.fetchone()[0]

    # Calculate metrics
    metrics = await calculator.calculate_player_metrics(player_id)

    print("\n" + "=" * 80)
    print(f"ADVANCED METRICS FOR PLAYER {player_id}")
    print("=" * 80)

    if metrics:
        print(f"\nOverall wOBA: {metrics['overall_woba']}")
        print(f"Overall wRC+: {metrics['overall_wrc_plus']}")

        print("\nBy Level:")
        for level_data in metrics['levels']:
            print(f"\n  {level_data['level']}:")
            print(f"    Games: {level_data['games']}")
            print(f"    AVG/OBP/SLG: {level_data['avg']:.3f}/{level_data['obp']:.3f}/{level_data['slg']:.3f}")
            print(f"    wOBA: {level_data['woba']}")
            print(f"    wRC+: {level_data['wrc_plus']}")


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_single_player())

    # To update all players, uncomment:
    # asyncio.run(update_database_with_metrics())