"""
Calculate advanced baseball metrics including wRC+ approximation, wOBA, ISO, and others.
These will be used as targets for ML models and for player evaluation.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AdvancedMetricsCalculator:
    """Calculate advanced baseball metrics from basic stats."""

    def __init__(self):
        # Linear weights for wOBA calculation (2023 FanGraphs values)
        self.woba_weights = {
            'bb': 0.69,
            'hbp': 0.72,
            'single': 0.88,
            'double': 1.24,
            'triple': 1.56,
            'hr': 2.00
        }

        # League average wOBA for scaling (typical MLB average)
        self.league_avg_woba = 0.320

        # wOBA scale for wRC+ calculation
        self.woba_scale = 1.185

    def calculate_woba(self, row):
        """
        Calculate weighted On-Base Average (wOBA).
        wOBA = (weight_BB × BB + weight_HBP × HBP + weight_1B × 1B +
                weight_2B × 2B + weight_3B × 3B + weight_HR × HR) / PA
        """
        try:
            # Extract stats
            pa = row.get('plate_appearances', 0)
            if pa == 0:
                return 0.0

            bb = row.get('walks', 0)
            hbp = row.get('hit_by_pitch', 0)
            h = row.get('hits', 0)
            doubles = row.get('doubles', 0)
            triples = row.get('triples', 0)
            hr = row.get('home_runs', 0)

            # Calculate singles
            singles = h - doubles - triples - hr

            # Calculate wOBA
            woba = (
                self.woba_weights['bb'] * bb +
                self.woba_weights['hbp'] * hbp +
                self.woba_weights['single'] * singles +
                self.woba_weights['double'] * doubles +
                self.woba_weights['triple'] * triples +
                self.woba_weights['hr'] * hr
            ) / pa

            return woba
        except:
            return 0.0

    def calculate_wrc_plus(self, woba, league_avg_woba=None):
        """
        Calculate wRC+ (Weighted Runs Created Plus).
        wRC+ = ((wOBA - League wOBA) / wOBA Scale + League R/PA) / (League R/PA) * 100

        Simplified version without park factors:
        wRC+ = (wOBA / League wOBA) * 100
        """
        if league_avg_woba is None:
            league_avg_woba = self.league_avg_woba

        if league_avg_woba == 0:
            return 100

        # Simplified wRC+ calculation
        wrc_plus = (woba / league_avg_woba) * 100

        return wrc_plus

    def calculate_iso(self, row):
        """
        Calculate Isolated Power (ISO).
        ISO = SLG - AVG = Extra Bases / At Bats
        """
        try:
            ab = row.get('at_bats', 0)
            if ab == 0:
                return 0.0

            # Method 1: If we have SLG and AVG
            if 'slg' in row and 'batting_avg' in row:
                return row['slg'] - row['batting_avg']

            # Method 2: Calculate from raw stats
            doubles = row.get('doubles', 0)
            triples = row.get('triples', 0)
            hr = row.get('home_runs', 0)

            # Total bases from extra base hits
            extra_bases = doubles + (2 * triples) + (3 * hr)

            iso = extra_bases / ab
            return iso
        except:
            return 0.0

    def calculate_babip(self, row):
        """
        Calculate Batting Average on Balls In Play (BABIP).
        BABIP = (H - HR) / (AB - K - HR)
        Note: Sacrifice flies not available, so using simplified formula
        """
        try:
            h = row.get('hits', 0)
            hr = row.get('home_runs', 0)
            ab = row.get('at_bats', 0)
            k = row.get('strikeouts', 0)

            denominator = ab - k - hr
            if denominator <= 0:
                return 0.0

            babip = (h - hr) / denominator
            return babip
        except:
            return 0.0

    def calculate_bb_rate(self, row):
        """Calculate walk rate (BB%)."""
        pa = row.get('plate_appearances', 0)
        bb = row.get('walks', 0)

        if pa == 0:
            return 0.0
        return bb / pa

    def calculate_k_rate(self, row):
        """Calculate strikeout rate (K%)."""
        pa = row.get('plate_appearances', 0)
        k = row.get('strikeouts', 0)

        if pa == 0:
            return 0.0
        return k / pa

    def calculate_obp(self, row):
        """
        Calculate On-Base Percentage if not available.
        OBP = (H + BB + HBP) / (AB + BB + HBP)
        Note: Sacrifice flies not available, so using simplified formula
        """
        try:
            h = row.get('hits', 0)
            bb = row.get('walks', 0)
            hbp = row.get('hit_by_pitch', 0)
            ab = row.get('at_bats', 0)

            denominator = ab + bb + hbp
            if denominator == 0:
                return 0.0

            obp = (h + bb + hbp) / denominator
            return obp
        except:
            return 0.0

    def calculate_slg(self, row):
        """
        Calculate Slugging Percentage if not available.
        SLG = Total Bases / AB
        """
        try:
            ab = row.get('at_bats', 0)
            if ab == 0:
                return 0.0

            h = row.get('hits', 0)
            doubles = row.get('doubles', 0)
            triples = row.get('triples', 0)
            hr = row.get('home_runs', 0)

            singles = h - doubles - triples - hr
            total_bases = singles + (2 * doubles) + (3 * triples) + (4 * hr)

            slg = total_bases / ab
            return slg
        except:
            return 0.0

    async def load_milb_stats(self):
        """Load MiLB stats for calculation."""

        query = """
        SELECT
            mlb_player_id,
            season,
            level,
            SUM(games_played) as games_played,
            SUM(plate_appearances) as plate_appearances,
            SUM(at_bats) as at_bats,
            SUM(hits) as hits,
            SUM(doubles) as doubles,
            SUM(triples) as triples,
            SUM(home_runs) as home_runs,
            SUM(runs) as runs,
            SUM(rbi) as rbi,
            SUM(walks) as walks,
            SUM(strikeouts) as strikeouts,
            SUM(stolen_bases) as stolen_bases,
            SUM(hit_by_pitch) as hit_by_pitch,
            AVG(NULLIF(batting_avg, 0)) as batting_avg,
            AVG(NULLIF(ops, 0)) as ops
        FROM milb_game_logs
        WHERE mlb_player_id IS NOT NULL
          AND games_played > 0
          AND season >= 2022
        GROUP BY mlb_player_id, season, level
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to numeric
        numeric_cols = df.select_dtypes(include=['object']).columns
        for col in numeric_cols:
            if col not in ['level']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"Loaded {len(df)} player-season-level records")
        return df

    async def load_mlb_stats(self):
        """Load MLB stats for calculation."""

        query = """
        SELECT
            mlb_player_id,
            season,
            SUM(games_played) as games_played,
            SUM(plate_appearances) as plate_appearances,
            SUM(at_bats) as at_bats,
            SUM(hits) as hits,
            SUM(doubles) as doubles,
            SUM(triples) as triples,
            SUM(home_runs) as home_runs,
            SUM(runs) as runs,
            SUM(rbi) as rbi,
            SUM(walks) as walks,
            SUM(strikeouts) as strikeouts,
            SUM(stolen_bases) as stolen_bases,
            SUM(hit_by_pitch) as hit_by_pitch,
            AVG(NULLIF(batting_avg, 0)) as batting_avg,
            AVG(NULLIF(ops, 0)) as ops
        FROM mlb_game_logs
        WHERE mlb_player_id IS NOT NULL
          AND games_played > 0
          AND season >= 2022
        GROUP BY mlb_player_id, season
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to numeric
        numeric_cols = df.select_dtypes(include=['object']).columns
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"Loaded {len(df)} MLB player-season records")
        return df

    def calculate_all_metrics(self, df):
        """Calculate all advanced metrics for a dataframe."""

        logger.info("Calculating advanced metrics...")

        # Calculate OBP and SLG if not present
        if 'obp' not in df.columns or df['obp'].isna().all():
            df['obp'] = df.apply(self.calculate_obp, axis=1)

        if 'slg' not in df.columns or df['slg'].isna().all():
            df['slg'] = df.apply(self.calculate_slg, axis=1)

        # Calculate wOBA
        df['woba'] = df.apply(self.calculate_woba, axis=1)

        # Calculate league average wOBA by level (for MiLB) or overall (for MLB)
        if 'level' in df.columns:
            level_avg_woba = df.groupby('level')['woba'].mean()
            df['league_woba'] = df['level'].map(level_avg_woba)
        else:
            df['league_woba'] = df['woba'].mean()

        # Calculate wRC+
        df['wrc_plus'] = df.apply(lambda row: self.calculate_wrc_plus(
            row['woba'], row['league_woba']
        ), axis=1)

        # Calculate other metrics
        df['iso'] = df.apply(self.calculate_iso, axis=1)
        df['babip'] = df.apply(self.calculate_babip, axis=1)
        df['bb_rate'] = df.apply(self.calculate_bb_rate, axis=1)
        df['k_rate'] = df.apply(self.calculate_k_rate, axis=1)

        # Calculate OPS+ (similar to wRC+ but based on OPS)
        if 'level' in df.columns:
            level_avg_ops = df.groupby('level')['ops'].mean()
            df['league_ops'] = df['level'].map(level_avg_ops)
        else:
            df['league_ops'] = df['ops'].mean()

        df['ops_plus'] = (df['ops'] / df['league_ops'].replace(0, 0.700)) * 100

        logger.info("Advanced metrics calculated successfully")
        return df

    async def save_metrics_to_db(self, df, table_suffix=''):
        """Save calculated metrics back to database."""

        # Create table for advanced metrics
        table_name = f"advanced_metrics{table_suffix}"

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            mlb_player_id INTEGER,
            season INTEGER,
            level VARCHAR(10),
            games_played INTEGER,
            plate_appearances INTEGER,
            woba FLOAT,
            wrc_plus FLOAT,
            iso FLOAT,
            babip FLOAT,
            bb_rate FLOAT,
            k_rate FLOAT,
            ops_plus FLOAT,
            obp FLOAT,
            slg FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(mlb_player_id, season, level)
        )
        """

        async with engine.begin() as conn:
            await conn.execute(text(create_table_query))

            # Insert metrics
            for _, row in df.iterrows():
                # Skip rows with invalid data
                if pd.isna(row.get('mlb_player_id')) or pd.isna(row.get('season')):
                    continue

                insert_query = f"""
                INSERT INTO {table_name} (
                    mlb_player_id, season, level, games_played, plate_appearances,
                    woba, wrc_plus, iso, babip, bb_rate, k_rate, ops_plus, obp, slg
                ) VALUES (
                    :mlb_player_id, :season, :level, :games_played, :plate_appearances,
                    :woba, :wrc_plus, :iso, :babip, :bb_rate, :k_rate, :ops_plus, :obp, :slg
                )
                ON CONFLICT (mlb_player_id, season, level) DO UPDATE SET
                    woba = EXCLUDED.woba,
                    wrc_plus = EXCLUDED.wrc_plus,
                    iso = EXCLUDED.iso,
                    babip = EXCLUDED.babip,
                    bb_rate = EXCLUDED.bb_rate,
                    k_rate = EXCLUDED.k_rate,
                    ops_plus = EXCLUDED.ops_plus
                """

                # Convert NaN values to None for database insertion
                def safe_value(val):
                    if pd.isna(val):
                        return None
                    if isinstance(val, (np.integer, np.floating)):
                        return float(val)
                    return val

                await conn.execute(text(insert_query), {
                    'mlb_player_id': int(row.get('mlb_player_id')),
                    'season': int(row.get('season')),
                    'level': row.get('level', 'MLB'),
                    'games_played': safe_value(row.get('games_played')),
                    'plate_appearances': safe_value(row.get('plate_appearances')),
                    'woba': safe_value(row.get('woba')),
                    'wrc_plus': safe_value(row.get('wrc_plus')),
                    'iso': safe_value(row.get('iso')),
                    'babip': safe_value(row.get('babip')),
                    'bb_rate': safe_value(row.get('bb_rate')),
                    'k_rate': safe_value(row.get('k_rate')),
                    'ops_plus': safe_value(row.get('ops_plus')),
                    'obp': safe_value(row.get('obp')),
                    'slg': safe_value(row.get('slg'))
                })

        logger.info(f"Saved {len(df)} records to {table_name}")

    async def run_calculations(self):
        """Run all calculations for MiLB and MLB data."""

        # Calculate MiLB metrics
        logger.info("Processing MiLB stats...")
        milb_df = await self.load_milb_stats()

        if not milb_df.empty:
            milb_df = self.calculate_all_metrics(milb_df)

            # Show summary
            print("\n" + "="*80)
            print("MiLB ADVANCED METRICS SUMMARY")
            print("="*80)
            print(f"Total Records: {len(milb_df):,}")
            print(f"Unique Players: {milb_df['mlb_player_id'].nunique():,}")
            print(f"\nLeague Averages by Level:")

            level_summary = milb_df.groupby('level').agg({
                'woba': 'mean',
                'wrc_plus': 'mean',
                'iso': 'mean',
                'ops': 'mean',
                'ops_plus': 'mean'
            }).round(3)
            print(level_summary)

            # Save to database
            await self.save_metrics_to_db(milb_df, '_milb')

            # Save to CSV for inspection
            milb_df.to_csv('milb_advanced_metrics.csv', index=False)
            logger.info("MiLB metrics saved to milb_advanced_metrics.csv")

        # Calculate MLB metrics
        logger.info("Processing MLB stats...")
        mlb_df = await self.load_mlb_stats()

        if not mlb_df.empty:
            mlb_df = self.calculate_all_metrics(mlb_df)

            # Show summary
            print("\n" + "="*80)
            print("MLB ADVANCED METRICS SUMMARY")
            print("="*80)
            print(f"Total Records: {len(mlb_df):,}")
            print(f"Unique Players: {mlb_df['mlb_player_id'].nunique():,}")
            print(f"\nOverall Averages:")

            overall_summary = mlb_df[['woba', 'wrc_plus', 'iso', 'ops', 'ops_plus']].mean().round(3)
            print(overall_summary)

            # Show top performers
            print("\n" + "="*80)
            print("TOP 20 PLAYERS BY wRC+ (min 50 PA)")
            print("="*80)

            qualified = mlb_df[mlb_df['plate_appearances'] >= 50].nlargest(20, 'wrc_plus')
            display_cols = ['mlb_player_id', 'season', 'wrc_plus', 'woba', 'ops', 'iso']
            print(qualified[display_cols].to_string(index=False))

            # Save to database
            await self.save_metrics_to_db(mlb_df, '_mlb')

            # Save to CSV
            mlb_df.to_csv('mlb_advanced_metrics.csv', index=False)
            logger.info("MLB metrics saved to mlb_advanced_metrics.csv")

        return milb_df, mlb_df


async def main():
    calculator = AdvancedMetricsCalculator()
    await calculator.run_calculations()


if __name__ == "__main__":
    asyncio.run(main())