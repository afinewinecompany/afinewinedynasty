"""
Age-Adjusted MiLB to MLB Performance Predictor

This script creates ML models that account for:
1. Age-relative-to-level performance (19yo in A+ vs 24yo in A+)
2. Level progression rates (improvement from A+ to AA to AAA)
3. Cross-level translations (how A+ stats project to AA/AAA/MLB)
"""

import asyncio
import logging
from typing import Tuple, Dict, List
from datetime import datetime
import os

import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

# Add parent directory to path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgeAdjustedPredictor:
    """
    ML predictor that accounts for age-relative-to-level performance.
    """

    def __init__(self):
        self.models = {}
        self.feature_names = []
        self.target_names = []

    async def load_milb_features_with_age(self) -> pd.DataFrame:
        """Load MiLB stats with age at each level/season."""
        logger.info("Loading MiLB game logs with age context...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    m.mlb_player_id,
                    m.level,
                    m.season,
                    EXTRACT(YEAR FROM MIN(m.game_date)) - EXTRACT(YEAR FROM p.birth_date) as age_at_level,
                    COUNT(*) as games_played,
                    SUM(m.plate_appearances) as total_pa,
                    SUM(m.at_bats) as total_ab,
                    SUM(m.runs) as total_runs,
                    SUM(m.hits) as total_hits,
                    SUM(m.doubles) as total_2b,
                    SUM(m.triples) as total_3b,
                    SUM(m.home_runs) as total_hr,
                    SUM(m.rbi) as total_rbi,
                    SUM(m.walks) as total_bb,
                    SUM(m.strikeouts) as total_so,
                    SUM(m.stolen_bases) as total_sb,
                    SUM(m.caught_stealing) as total_cs,
                    SUM(m.hit_by_pitch) as total_hbp,
                    AVG(m.batting_avg) as avg_ba,
                    AVG(m.on_base_pct) as avg_obp,
                    AVG(m.slugging_pct) as avg_slg,
                    AVG(m.ops) as avg_ops,
                    AVG(m.babip) as avg_babip
                FROM milb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                WHERE m.data_source = 'mlb_stats_api_gamelog'
                AND m.mlb_player_id IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND (m.games_pitched IS NULL OR m.games_pitched = 0)
                GROUP BY m.mlb_player_id, m.level, m.season, p.birth_date
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'level', 'season', 'age_at_level', 'games_played',
                'total_pa', 'total_ab', 'total_runs', 'total_hits', 'total_2b',
                'total_3b', 'total_hr', 'total_rbi', 'total_bb', 'total_so',
                'total_sb', 'total_cs', 'total_hbp', 'avg_ba', 'avg_obp',
                'avg_slg', 'avg_ops', 'avg_babip'
            ])

        # Convert all numeric columns to float to avoid Decimal issues
        numeric_cols = ['age_at_level', 'games_played', 'total_pa', 'total_ab', 'total_runs',
                       'total_hits', 'total_2b', 'total_3b', 'total_hr', 'total_rbi',
                       'total_bb', 'total_so', 'total_sb', 'total_cs', 'total_hbp',
                       'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops', 'avg_babip']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

        logger.info(f"Loaded {len(df)} MiLB player-level-season records with age")
        return df

    def calculate_age_adjusted_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate age-adjusted performance metrics.

        Age adjustments based on typical age for each level:
        - AAA: 25 years (league average)
        - AA: 23 years
        - A+: 22 years
        - A: 21 years
        """
        level_avg_ages = {
            'AAA': 25,
            'AA': 23,
            'A+': 22,
            'A': 21,
            'Rookie': 19,
            'Rookie+': 18
        }

        df = df.copy()

        # Calculate age differential (younger = positive adjustment)
        df['age_diff'] = df.apply(
            lambda row: level_avg_ages.get(row['level'], 22) - row['age_at_level']
            if pd.notna(row['age_at_level']) else 0,
            axis=1
        )

        # Age-adjusted OPS (add 10 points per year younger than average)
        df['age_adj_ops'] = df['avg_ops'] + (df['age_diff'] * 0.010)

        # Age-adjusted ISO
        df['iso'] = df['avg_slg'] - df['avg_ba']
        df['age_adj_iso'] = df['iso'] + (df['age_diff'] * 0.005)

        # Age-adjusted walk rate
        df['bb_rate'] = np.where(df['total_pa'] > 0, df['total_bb'] / df['total_pa'], 0)
        df['age_adj_bb_rate'] = df['bb_rate'] + (df['age_diff'] * 0.005)

        # Age-adjusted strikeout rate (lower is better, so subtract)
        df['so_rate'] = np.where(df['total_pa'] > 0, df['total_so'] / df['total_pa'], 0)
        df['age_adj_so_rate'] = df['so_rate'] - (df['age_diff'] * 0.008)

        return df

    def calculate_progression_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate how players progress between levels.

        For each player, track:
        - Performance change from A+ to AA
        - Performance change from AA to AAA
        - Age at first appearance at each level
        """
        progression_features = []

        # Group by player
        for player_id, player_df in df.groupby('mlb_player_id'):
            player_data = {'mlb_player_id': player_id}

            # Sort by level progression
            level_order = {'A': 1, 'A+': 2, 'AA': 3, 'AAA': 4}
            player_df['level_num'] = player_df['level'].map(level_order)
            player_df = player_df.sort_values('level_num')

            # Track ages at each level
            for _, row in player_df.iterrows():
                level = row['level']
                if pd.notna(row['age_at_level']):
                    player_data[f'age_at_{level}'] = row['age_at_level']

            # Calculate OPS progression between levels
            levels_with_ops = player_df[player_df['avg_ops'].notna()].copy()
            if len(levels_with_ops) >= 2:
                # OPS change from first to last recorded level
                first_ops = levels_with_ops.iloc[0]['age_adj_ops']
                last_ops = levels_with_ops.iloc[-1]['age_adj_ops']
                player_data['ops_progression_rate'] = last_ops - first_ops

                # Age at progression
                first_age = levels_with_ops.iloc[0]['age_at_level']
                last_age = levels_with_ops.iloc[-1]['age_at_level']
                if pd.notna(first_age) and pd.notna(last_age) and last_age > first_age:
                    player_data['ops_improvement_per_year'] = (last_ops - first_ops) / (last_age - first_age)
                else:
                    player_data['ops_improvement_per_year'] = 0
            else:
                player_data['ops_progression_rate'] = 0
                player_data['ops_improvement_per_year'] = 0

            progression_features.append(player_data)

        return pd.DataFrame(progression_features)

    async def prepare_age_adjusted_dataset(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare dataset with age-adjusted features."""
        logger.info("Preparing age-adjusted ML dataset...")

        # Load MiLB data with ages
        milb_raw = await self.load_milb_features_with_age()

        # Calculate age-adjusted metrics
        milb_adjusted = self.calculate_age_adjusted_metrics(milb_raw)

        # Aggregate by player and level
        agg_features = milb_adjusted.groupby(['mlb_player_id', 'level']).agg({
            'age_at_level': 'first',
            'age_diff': 'mean',
            'games_played': 'sum',
            'total_pa': 'sum',
            'total_ab': 'sum',
            'total_hr': 'sum',
            'total_bb': 'sum',
            'total_so': 'sum',
            'total_sb': 'sum',
            'avg_ops': 'mean',
            'avg_obp': 'mean',
            'avg_slg': 'mean',
            'avg_ba': 'mean',
            'age_adj_ops': 'mean',
            'age_adj_iso': 'mean',
            'age_adj_bb_rate': 'mean',
            'age_adj_so_rate': 'mean',
            'iso': 'mean',
            'bb_rate': 'mean',
            'so_rate': 'mean'
        }).reset_index()

        # Pivot by level
        level_features = []
        for level in ['AAA', 'AA', 'A+', 'A']:
            level_df = agg_features[agg_features['level'] == level].copy()
            level_df = level_df.drop('level', axis=1)
            level_df.columns = [f'{col}_{level}' if col != 'mlb_player_id' else col
                               for col in level_df.columns]
            level_features.append(level_df)

        # Merge all levels
        milb_features = level_features[0]
        for level_df in level_features[1:]:
            milb_features = milb_features.merge(level_df, on='mlb_player_id', how='outer')

        milb_features = milb_features.fillna(0)

        # Add progression metrics
        progression = self.calculate_progression_metrics(milb_adjusted)
        milb_features = milb_features.merge(progression, on='mlb_player_id', how='left')
        milb_features = milb_features.fillna(0)

        # Load MLB targets (reuse from original script)
        mlb_targets = await self.load_mlb_targets()

        # Merge
        dataset = milb_features.merge(mlb_targets, on='mlb_player_id', how='inner')

        logger.info(f"Combined dataset: {len(dataset)} players with both MiLB and MLB data")

        # Filter for sufficient data
        dataset = dataset[dataset['total_pa_AAA'] >= 50]  # At least 50 AAA PA
        dataset = dataset[dataset['mlb_total_pa'] >= 50]  # At least 50 MLB PA

        logger.info(f"After filtering: {len(dataset)} players")

        # Separate features and targets
        feature_cols = [col for col in dataset.columns
                       if not col.startswith('mlb_') and col != 'mlb_player_id']
        target_cols = ['mlb_wrc_plus', 'mlb_woba', 'mlb_avg_ops', 'mlb_iso',
                      'mlb_bb_rate', 'mlb_so_rate', 'mlb_hr_rate']

        self.feature_names = feature_cols
        self.target_names = target_cols

        X = dataset[feature_cols]
        y = dataset[target_cols]

        # Handle any remaining NaN
        X = X.fillna(0)

        logger.info(f"Features: {len(feature_cols)} columns")
        logger.info(f"Targets: {len(target_cols)} columns")

        return X, y

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load MLB targets (same as original)."""
        logger.info("Loading MLB targets...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    mlb_player_id,
                    SUM(plate_appearances) as mlb_total_pa,
                    SUM(at_bats) as mlb_total_ab,
                    SUM(hits) as mlb_total_hits,
                    SUM(doubles) as mlb_total_2b,
                    SUM(triples) as mlb_total_3b,
                    SUM(home_runs) as mlb_total_hr,
                    SUM(walks) as mlb_total_bb,
                    SUM(strikeouts) as mlb_total_so,
                    SUM(hit_by_pitch) as mlb_total_hbp,
                    SUM(sacrifice_flies) as mlb_total_sf,
                    AVG(batting_avg) as mlb_avg_ba,
                    AVG(on_base_pct) as mlb_avg_obp,
                    AVG(slugging_pct) as mlb_avg_slg,
                    AVG(ops) as mlb_avg_ops
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'mlb_total_pa', 'mlb_total_ab', 'mlb_total_hits',
                'mlb_total_2b', 'mlb_total_3b', 'mlb_total_hr', 'mlb_total_bb',
                'mlb_total_so', 'mlb_total_hbp', 'mlb_total_sf',
                'mlb_avg_ba', 'mlb_avg_obp', 'mlb_avg_slg', 'mlb_avg_ops'
            ])

        # Convert to float
        for col in ['mlb_avg_ba', 'mlb_avg_obp', 'mlb_avg_slg', 'mlb_avg_ops']:
            df[col] = df[col].astype(float)

        # Calculate metrics
        df['mlb_bb_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_bb'] / df['mlb_total_pa'], 0)
        df['mlb_so_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_so'] / df['mlb_total_pa'], 0)
        df['mlb_hr_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_hr'] / df['mlb_total_pa'], 0)
        df['mlb_iso'] = df['mlb_avg_slg'] - df['mlb_avg_ba']

        # wOBA and wRC+
        singles = df['mlb_total_hits'] - df['mlb_total_2b'] - df['mlb_total_3b'] - df['mlb_total_hr']
        woba_numerator = (
            0.69 * df['mlb_total_bb'] +
            0.72 * df['mlb_total_hbp'] +
            0.88 * singles +
            1.24 * df['mlb_total_2b'] +
            1.56 * df['mlb_total_3b'] +
            1.95 * df['mlb_total_hr']
        )
        woba_denominator = df['mlb_total_ab'] + df['mlb_total_bb'] + df['mlb_total_sf'] + df['mlb_total_hbp']
        df['mlb_woba'] = np.where(woba_denominator > 0, woba_numerator / woba_denominator, 0)
        df['mlb_wrc_plus'] = ((df['mlb_woba'] - 0.320) / 1.25) * 100 + 100

        logger.info(f"Loaded MLB stats for {len(df)} players")
        return df

    async def train_models(self, X: pd.DataFrame, y: pd.DataFrame):
        """Train multiple models for each target."""
        logger.info("Training age-adjusted ML models...")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        models_to_train = {
            'Linear Regression': LinearRegression(),
            'Ridge Regression': Ridge(alpha=1.0),
            'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10, n_jobs=-1),
            'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=5)
        }

        results = []
        feature_importance_data = {}

        for target in self.target_names:
            logger.info(f"\nTraining models for {target}...")

            for model_name, model in models_to_train.items():
                # Train
                model.fit(X_train, y_train[target])

                # Predict
                y_pred = model.predict(X_test)

                # Metrics
                r2 = r2_score(y_test[target], y_pred)
                mae = mean_absolute_error(y_test[target], y_pred)
                mse = mean_squared_error(y_test[target], y_pred)

                logger.info(f"  {model_name}: R2={r2:.3f}, MAE={mae:.4f}")

                results.append({
                    'target': target,
                    'model': model_name,
                    'r2': r2,
                    'mae': mae,
                    'mse': mse
                })

                # Get feature importance for Random Forest
                if model_name == 'Random Forest' and target == 'mlb_wrc_plus':
                    importance = pd.DataFrame({
                        'feature': self.feature_names,
                        'importance': model.feature_importances_
                    }).sort_values('importance', ascending=False)
                    feature_importance_data['wrc_plus'] = importance

        self.results = pd.DataFrame(results)
        self.feature_importance = feature_importance_data

        return self.results

    def analyze_feature_importance(self):
        """Analyze which age-adjusted features are most predictive."""
        logger.info("\nAnalyzing age-adjusted feature importance...")

        if 'wrc_plus' in self.feature_importance:
            importance = self.feature_importance['wrc_plus']

            # Categorize features
            age_features = importance[importance['feature'].str.contains('age')]
            progression_features = importance[importance['feature'].str.contains('progression|improvement')]
            raw_stats = importance[~importance['feature'].str.contains('age|progression|improvement')]

            print("\n" + "="*80)
            print("AGE-ADJUSTED FEATURES - Top 10:")
            print("="*80)
            for _, row in age_features.head(10).iterrows():
                print(f"  {row['feature']:40s}: {row['importance']:6.1%}")

            print("\n" + "="*80)
            print("PROGRESSION FEATURES:")
            print("="*80)
            for _, row in progression_features.iterrows():
                print(f"  {row['feature']:40s}: {row['importance']:6.1%}")

            print("\n" + "="*80)
            print("RAW STATS FEATURES - Top 10:")
            print("="*80)
            for _, row in raw_stats.head(10).iterrows():
                print(f"  {row['feature']:40s}: {row['importance']:6.1%}")


async def main():
    """Main execution function."""
    logger.info("="*80)
    logger.info("Age-Adjusted MiLB to MLB Performance Predictor")
    logger.info("="*80)

    predictor = AgeAdjustedPredictor()

    # Prepare dataset
    X, y = await predictor.prepare_age_adjusted_dataset()

    # Train models
    results = await predictor.train_models(X, y)

    # Analyze feature importance
    predictor.analyze_feature_importance()

    # Save results
    logger.info("\nSaving results...")
    os.makedirs('ml_results', exist_ok=True)
    results.to_csv('ml_results/age_adjusted_results.csv', index=False)

    logger.info("\n" + "="*80)
    logger.info("Age-Adjusted ML Training Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
