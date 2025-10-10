"""
Generate comprehensive ML-based prospect rankings for frontend integration.
Uses the dual-target model to predict both OPS and wRC+ for all prospects.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
import pickle
import json
from datetime import datetime
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MLPredictionsRankingGenerator:
    """Generate ML-based rankings for all prospects with proper formatting."""

    def __init__(self):
        self.model_data = None
        self.woba_weights = {
            'bb': 0.69,
            'hbp': 0.72,
            'single': 0.88,
            'double': 1.24,
            'triple': 1.56,
            'hr': 2.00
        }
        self.league_avg_woba = 0.320

    def calculate_woba(self, row):
        """Calculate weighted On-Base Average (wOBA)."""
        try:
            pa = row.get('plate_appearances', 0)
            if pa == 0:
                return 0.0

            bb = row.get('walks', 0)
            hbp = row.get('hit_by_pitch', 0)
            h = row.get('hits', 0)
            doubles = row.get('doubles', 0)
            triples = row.get('triples', 0)
            hr = row.get('home_runs', 0)

            singles = h - doubles - triples - hr

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

    def calculate_wrc_plus(self, woba):
        """Calculate wRC+ (Weighted Runs Created Plus)."""
        if self.league_avg_woba == 0:
            return 100
        wrc_plus = (woba / self.league_avg_woba) * 100
        return wrc_plus

    def calculate_iso(self, row):
        """Calculate Isolated Power (ISO)."""
        try:
            ab = row.get('at_bats', 0)
            if ab == 0:
                return 0.0

            doubles = row.get('doubles', 0)
            triples = row.get('triples', 0)
            hr = row.get('home_runs', 0)

            extra_bases = doubles + (2 * triples) + (3 * hr)
            iso = extra_bases / ab
            return iso
        except:
            return 0.0

    def calculate_babip(self, row):
        """Calculate Batting Average on Balls In Play (BABIP)."""
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

    async def load_prospect_data(self):
        """Load all prospect data with names and organization info."""

        query = """
        WITH milb_stats AS (
            -- Get MiLB performance with names
            SELECT
                mlg.mlb_player_id,
                COALESCE(p.name, CONCAT('Player_', mlg.mlb_player_id::text)) as player_name,
                COALESCE(MAX(mlg.team), 'Unknown') as organization,
                MAX(p.position) as position,
                MAX(p.age) as age,
                AVG(mlg.batting_avg) as avg_batting_avg,
                AVG(mlg.ops) as avg_ops,
                SUM(mlg.games_played) as total_games,
                SUM(mlg.plate_appearances) as plate_appearances,
                SUM(mlg.at_bats) as at_bats,
                SUM(mlg.hits) as hits,
                SUM(mlg.doubles) as doubles,
                SUM(mlg.triples) as triples,
                SUM(mlg.home_runs) as home_runs,
                SUM(mlg.stolen_bases) as stolen_bases,
                SUM(mlg.walks) as walks,
                SUM(mlg.strikeouts) as strikeouts,
                SUM(mlg.hit_by_pitch) as hit_by_pitch,
                COUNT(DISTINCT mlg.season) as seasons_played,
                MAX(mlg.season) as latest_season,
                STRING_AGG(DISTINCT mlg.level, ',') as levels_played
            FROM milb_game_logs mlg
            LEFT JOIN prospects p ON CAST(mlg.mlb_player_id AS VARCHAR) = p.mlb_player_id
            WHERE mlg.season >= 2022
              AND mlg.games_played > 0
              AND mlg.mlb_player_id IS NOT NULL
            GROUP BY mlg.mlb_player_id, p.name, p.position, p.age
            HAVING SUM(mlg.games_played) >= 30  -- Lower threshold for more coverage
        ),
        mlb_outcomes AS (
            -- Get MLB outcomes if available
            SELECT
                mlb_player_id,
                AVG(ops) as mlb_ops,
                AVG(batting_avg) as mlb_avg,
                SUM(home_runs) as mlb_hr,
                SUM(games_played) as mlb_games,
                COUNT(DISTINCT season) as mlb_seasons
            FROM mlb_game_logs
            WHERE season >= 2022
              AND games_played > 0
            GROUP BY mlb_player_id
        )
        SELECT
            ms.*,
            mo.mlb_ops,
            mo.mlb_avg,
            mo.mlb_hr,
            mo.mlb_games,
            mo.mlb_seasons,
            CASE WHEN mo.mlb_ops IS NOT NULL THEN 1 ELSE 0 END as made_mlb
        FROM milb_stats ms
        LEFT JOIN mlb_outcomes mo ON ms.mlb_player_id = mo.mlb_player_id
        WHERE ms.latest_season >= 2023  -- Focus on recent players
        ORDER BY ms.avg_ops DESC
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to numeric
        numeric_cols = ['avg_batting_avg', 'avg_ops', 'total_games', 'plate_appearances',
                       'at_bats', 'hits', 'doubles', 'triples', 'home_runs', 'stolen_bases',
                       'walks', 'strikeouts', 'hit_by_pitch', 'seasons_played', 'latest_season',
                       'mlb_ops', 'mlb_avg', 'mlb_hr', 'mlb_games', 'mlb_seasons', 'made_mlb',
                       'age']

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Calculate advanced metrics
        logger.info("Calculating advanced metrics...")
        df['milb_woba'] = df.apply(self.calculate_woba, axis=1)
        df['milb_wrc_plus'] = df['milb_woba'].apply(lambda x: self.calculate_wrc_plus(x))
        df['milb_iso'] = df.apply(self.calculate_iso, axis=1)
        df['milb_babip'] = df.apply(self.calculate_babip, axis=1)
        df['milb_bb_rate'] = df['walks'] / (df['plate_appearances'] + 1)
        df['milb_k_rate'] = df['strikeouts'] / (df['plate_appearances'] + 1)

        logger.info(f"Loaded {len(df)} prospects for ranking")
        return df

    def create_features(self, df):
        """Create engineered features for prediction."""

        # Performance ratios
        df['power_speed'] = df['home_runs'] / (df['stolen_bases'] + 1)
        df['k_bb_ratio'] = df['strikeouts'] / (df['walks'] + 1)

        # Production rates
        df['hr_per_game'] = df['home_runs'] / (df['total_games'] + 1)
        df['hits_per_game'] = df['hits'] / (df['total_games'] + 1)

        # Level progression
        df['reached_aaa'] = df['levels_played'].str.contains('AAA', na=False).astype(int)
        df['reached_aa'] = df['levels_played'].str.contains('AA', na=False).astype(int)

        # Experience
        df['games_per_season'] = df['total_games'] / (df['seasons_played'] + 1)

        # Recent performance
        df['is_recent'] = (df['latest_season'] >= 2024).astype(int)

        # Advanced metric features
        df['woba_consistency'] = df['milb_woba'] / (df['milb_k_rate'] + 0.01)
        df['iso_power'] = df['milb_iso'] * df['home_runs']

        return df

    def generate_predictions(self, df):
        """Generate predictions using the trained model."""

        # Create features
        df = self.create_features(df)

        # Load model
        with open('dual_target_models_inline.pkl', 'rb') as f:
            self.model_data = pickle.load(f)

        feature_cols = self.model_data['feature_cols']
        scaler = self.model_data['scalers']['standard']
        models = self.model_data['models']

        # Prepare features
        available_features = [col for col in feature_cols if col in df.columns]
        X = df[available_features].fillna(0)
        X = X.replace([np.inf, -np.inf], 0)

        # Scale features
        X_scaled = scaler.transform(X)

        # Generate predictions
        predictions_ops = []
        predictions_wrc = []

        for name, model in models.items():
            if '_ops' in name:
                pred = model.predict(X_scaled)
                predictions_ops.append(pred)
            elif '_wrc' in name:
                pred = model.predict(X_scaled)
                predictions_wrc.append(pred)
            elif hasattr(model, 'predict'):
                pred = model.predict(X_scaled)
                if len(pred.shape) > 1:
                    predictions_ops.append(pred[:, 0])
                    predictions_wrc.append(pred[:, 1])

        # Average predictions
        df['predicted_ops'] = np.mean(predictions_ops, axis=0) if predictions_ops else 0.700
        df['predicted_wrc_plus'] = np.mean(predictions_wrc, axis=0) if predictions_wrc else 100

        # Calculate composite score
        df['composite_score'] = (df['predicted_ops'] / 0.750) * 50 + (df['predicted_wrc_plus'] / 100) * 50

        # Add confidence score based on sample size and level
        df['confidence'] = (
            np.minimum(df['total_games'] / 200, 1.0) * 0.4 +  # Games played
            df['reached_aaa'].fillna(0) * 0.3 +                # AAA experience
            df['reached_aa'].fillna(0) * 0.2 +                 # AA experience
            (df['seasons_played'] / 5).clip(upper=1.0) * 0.1  # Experience
        )

        return df

    def format_rankings(self, df):
        """Format rankings for frontend consumption."""

        # Sort by composite score
        df = df.sort_values('composite_score', ascending=False).reset_index(drop=True)

        # Create rank
        df['rank'] = range(1, len(df) + 1)

        # Format the output
        rankings = []
        for _, row in df.iterrows():
            ranking_entry = {
                'rank': int(row['rank']),
                'mlb_player_id': int(row['mlb_player_id']),
                'player_name': row['player_name'] if pd.notna(row['player_name']) else f"Player_{row['mlb_player_id']}",
                'organization': row['organization'] if pd.notna(row['organization']) else 'Unknown',
                'position': row['position'] if pd.notna(row['position']) else 'Unknown',
                'age': int(row['age']) if pd.notna(row['age']) else None,

                # MiLB Stats
                'milb_stats': {
                    'games': int(row['total_games']),
                    'avg': float(row['avg_batting_avg']) if pd.notna(row['avg_batting_avg']) else 0,
                    'ops': float(row['avg_ops']) if pd.notna(row['avg_ops']) else 0,
                    'hr': int(row['home_runs']) if pd.notna(row['home_runs']) else 0,
                    'sb': int(row['stolen_bases']) if pd.notna(row['stolen_bases']) else 0,
                    'bb_rate': float(row['milb_bb_rate']) if pd.notna(row['milb_bb_rate']) else 0,
                    'k_rate': float(row['milb_k_rate']) if pd.notna(row['milb_k_rate']) else 0,
                    'woba': float(row['milb_woba']) if pd.notna(row['milb_woba']) else 0,
                    'wrc_plus': float(row['milb_wrc_plus']) if pd.notna(row['milb_wrc_plus']) else 0,
                    'iso': float(row['milb_iso']) if pd.notna(row['milb_iso']) else 0,
                    'levels': row['levels_played'] if pd.notna(row['levels_played']) else ''
                },

                # MLB Predictions
                'predictions': {
                    'ops': float(row['predicted_ops']),
                    'wrc_plus': float(row['predicted_wrc_plus']),
                    'composite_score': float(row['composite_score']),
                    'confidence': float(row['confidence'])
                },

                # MLB Outcomes (if available)
                'mlb_stats': {
                    'has_data': bool(row['made_mlb']),
                    'games': int(row['mlb_games']) if pd.notna(row['mlb_games']) else 0,
                    'ops': float(row['mlb_ops']) if pd.notna(row['mlb_ops']) else None,
                    'avg': float(row['mlb_avg']) if pd.notna(row['mlb_avg']) else None,
                    'hr': int(row['mlb_hr']) if pd.notna(row['mlb_hr']) else 0
                } if row['made_mlb'] else None
            }
            rankings.append(ranking_entry)

        return rankings

    async def generate_rankings(self):
        """Generate complete ML-based rankings."""

        # Load data
        logger.info("Loading prospect data...")
        df = await self.load_prospect_data()

        # Generate predictions
        logger.info("Generating predictions...")
        df = self.generate_predictions(df)

        # Format rankings
        logger.info("Formatting rankings...")
        rankings = self.format_rankings(df)

        # Save to JSON
        output_file = 'ml_predictions_rankings.json'
        with open(output_file, 'w') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'total_prospects': len(rankings),
                'model_version': 'dual_target_v1',
                'rankings': rankings
            }, f, indent=2)

        logger.info(f"Rankings saved to {output_file}")

        # Also save CSV for analysis
        df['rank'] = range(1, len(df) + 1)  # Add rank column
        df_output = df[['rank', 'mlb_player_id', 'player_name', 'organization', 'position', 'age',
                       'avg_ops', 'predicted_ops', 'predicted_wrc_plus', 'composite_score',
                       'confidence', 'made_mlb']].copy()
        df_output.to_csv('ml_predictions_rankings.csv', index=False)
        logger.info("CSV saved to ml_predictions_rankings.csv")

        # Print summary
        print("\n" + "="*80)
        print("ML PREDICTIONS RANKINGS - TOP 30 PROSPECTS")
        print("="*80)
        print(f"{'Rank':<6} {'Player':<25} {'Org':<5} {'Pos':<4} {'Age':<4} {'OPS':<7} {'Pred OPS':<9} {'Pred wRC+':<10} {'Score':<7}")
        print("-"*80)

        for i in range(min(30, len(rankings))):
            r = rankings[i]
            print(f"{r['rank']:<6} {r['player_name'][:24]:<25} {r['organization'][:4]:<5} "
                  f"{r['position'][:3]:<4} {r['age'] or '--':<4} "
                  f"{r['milb_stats']['ops']:<7.3f} {r['predictions']['ops']:<9.3f} "
                  f"{r['predictions']['wrc_plus']:<10.1f} {r['predictions']['composite_score']:<7.1f}")

        return rankings


async def main():
    generator = MLPredictionsRankingGenerator()
    rankings = await generator.generate_rankings()

    # Update todo list
    logger.info("Rankings generation complete!")


if __name__ == "__main__":
    asyncio.run(main())