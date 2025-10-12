"""
Train ML Model to Predict MLB Performance from MiLB Stats

This script:
1. Loads MiLB game logs as features (X)
2. Loads MLB game logs as target outcomes (Y)
3. Aggregates player-level statistics
4. Trains models to predict MLB success from MiLB performance
5. Identifies which MiLB statistics best predict MLB outcomes

Usage:
    python train_milb_to_mlb_predictor.py
"""

import argparse
import asyncio
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

from sqlalchemy import text
from app.db.database import engine

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MiLBToMLBPredictor:
    """Train models to predict MLB performance from MiLB statistics."""

    def __init__(self):
        self.milb_features = None
        self.mlb_targets = None
        self.feature_names = []
        self.target_names = []
        self.models = {}
        self.results = {}

    async def load_player_demographics(self) -> pd.DataFrame:
        """Load player demographic data (age, position, etc.)."""
        logger.info("Loading player demographics...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    mlb_player_id,
                    age,
                    position,
                    height_inches,
                    weight_lbs,
                    bats,
                    throws,
                    draft_year,
                    draft_round
                FROM prospects
                WHERE mlb_player_id IS NOT NULL
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'age', 'position', 'height_inches', 'weight_lbs',
                'bats', 'throws', 'draft_year', 'draft_round'
            ])

        # Convert mlb_player_id to int
        df['mlb_player_id'] = pd.to_numeric(df['mlb_player_id'], errors='coerce')
        df = df.dropna(subset=['mlb_player_id'])
        df['mlb_player_id'] = df['mlb_player_id'].astype(int)

        logger.info(f"Loaded demographics for {len(df)} players")
        return df

    async def load_milb_features(self) -> pd.DataFrame:
        """Load and aggregate MiLB stats as features - ALL available hitting stats."""
        logger.info("Loading MiLB game logs with comprehensive stats...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    mlb_player_id,
                    level,
                    season,
                    COUNT(*) as games_played,
                    SUM(plate_appearances) as total_pa,
                    SUM(at_bats) as total_ab,
                    SUM(runs) as total_runs,
                    SUM(hits) as total_hits,
                    SUM(doubles) as total_2b,
                    SUM(triples) as total_3b,
                    SUM(home_runs) as total_hr,
                    SUM(rbi) as total_rbi,
                    SUM(walks) as total_bb,
                    SUM(intentional_walks) as total_ibb,
                    SUM(strikeouts) as total_so,
                    SUM(stolen_bases) as total_sb,
                    SUM(caught_stealing) as total_cs,
                    SUM(hit_by_pitch) as total_hbp,
                    SUM(sacrifice_flies) as total_sf,
                    SUM(sacrifice_hits) as total_sh,
                    SUM(ground_outs) as total_go,
                    SUM(air_outs) as total_ao,
                    SUM(fly_outs) as total_fo,
                    SUM(ground_into_double_play) as total_gidp,
                    SUM(pitches_seen) as total_pitches,
                    SUM(left_on_base) as total_lob,
                    SUM(total_bases) as total_tb,
                    AVG(batting_avg) as avg_ba,
                    AVG(on_base_pct) as avg_obp,
                    AVG(slugging_pct) as avg_slg,
                    AVG(ops) as avg_ops,
                    AVG(babip) as avg_babip,
                    AVG(ground_outs_to_airouts) as avg_go_ao,
                    AVG(at_bats_per_home_run) as avg_ab_per_hr,
                    MIN(game_date) as first_game,
                    MAX(game_date) as last_game
                FROM milb_game_logs
                WHERE data_source = 'mlb_stats_api_gamelog'
                AND mlb_player_id IS NOT NULL
                AND games_pitched IS NULL OR games_pitched = 0
                GROUP BY mlb_player_id, level, season
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'level', 'season', 'games_played', 'total_pa', 'total_ab',
                'total_runs', 'total_hits', 'total_2b', 'total_3b', 'total_hr', 'total_rbi',
                'total_bb', 'total_ibb', 'total_so', 'total_sb', 'total_cs', 'total_hbp',
                'total_sf', 'total_sh', 'total_go', 'total_ao', 'total_fo', 'total_gidp',
                'total_pitches', 'total_lob', 'total_tb', 'avg_ba', 'avg_obp', 'avg_slg',
                'avg_ops', 'avg_babip', 'avg_go_ao', 'avg_ab_per_hr', 'first_game', 'last_game'
            ])

        logger.info(f"Loaded {len(df)} MiLB player-level-season records")

        # Aggregate by level (sum across seasons)
        df_agg = df.groupby(['mlb_player_id', 'level']).agg({
            'games_played': 'sum',
            'total_pa': 'sum',
            'total_ab': 'sum',
            'total_runs': 'sum',
            'total_hits': 'sum',
            'total_2b': 'sum',
            'total_3b': 'sum',
            'total_hr': 'sum',
            'total_rbi': 'sum',
            'total_bb': 'sum',
            'total_ibb': 'sum',
            'total_so': 'sum',
            'total_sb': 'sum',
            'total_cs': 'sum',
            'total_hbp': 'sum',
            'total_sf': 'sum',
            'total_sh': 'sum',
            'total_go': 'sum',
            'total_ao': 'sum',
            'total_fo': 'sum',
            'total_gidp': 'sum',
            'total_pitches': 'sum',
            'total_lob': 'sum',
            'total_tb': 'sum',
            'avg_ba': 'mean',
            'avg_obp': 'mean',
            'avg_slg': 'mean',
            'avg_ops': 'mean',
            'avg_babip': 'mean',
            'avg_go_ao': 'mean',
            'avg_ab_per_hr': 'mean'
        }).reset_index()

        # Pivot by level to get features per level
        level_features = []
        for level in ['AAA', 'AA', 'A+', 'A']:
            level_df = df_agg[df_agg['level'] == level].copy()
            level_df = level_df.drop('level', axis=1)
            level_df.columns = [f'{col}_{level}' if col != 'mlb_player_id' else col
                               for col in level_df.columns]
            level_features.append(level_df)

        # Merge all levels
        milb_features = level_features[0]
        for level_df in level_features[1:]:
            milb_features = milb_features.merge(level_df, on='mlb_player_id', how='outer')

        # Fill NaN with 0 for players who didn't play at certain levels
        milb_features = milb_features.fillna(0)

        # Calculate derived features
        milb_features['total_milb_games'] = (
            milb_features.filter(like='games_played_').sum(axis=1)
        )
        milb_features['total_milb_pa'] = (
            milb_features.filter(like='total_pa_').sum(axis=1)
        )

        # Calculate rate stats and advanced metrics
        for level in ['AAA', 'AA', 'A+', 'A']:
            pa_col = f'total_pa_{level}'
            ab_col = f'total_ab_{level}'
            hits_col = f'total_hits_{level}'
            hr_col = f'total_hr_{level}'
            bb_col = f'total_bb_{level}'
            so_col = f'total_so_{level}'
            doubles_col = f'total_2b_{level}'
            triples_col = f'total_3b_{level}'
            sb_col = f'total_sb_{level}'
            cs_col = f'total_cs_{level}'

            if pa_col in milb_features.columns:
                # Batting average
                milb_features[f'ba_{level}'] = np.where(
                    milb_features[ab_col] > 0,
                    milb_features[hits_col] / milb_features[ab_col],
                    0
                )

                # Walk rate
                milb_features[f'bb_rate_{level}'] = np.where(
                    milb_features[pa_col] > 0,
                    milb_features[bb_col] / milb_features[pa_col],
                    0
                )

                # Strikeout rate
                milb_features[f'so_rate_{level}'] = np.where(
                    milb_features[pa_col] > 0,
                    milb_features[so_col] / milb_features[pa_col],
                    0
                )

                # HR rate
                milb_features[f'hr_rate_{level}'] = np.where(
                    milb_features[pa_col] > 0,
                    milb_features[hr_col] / milb_features[pa_col],
                    0
                )

                # ISO (Isolated Power) = SLG - BA
                milb_features[f'iso_{level}'] = np.where(
                    milb_features[ab_col] > 0,
                    milb_features[f'avg_slg_{level}'] - milb_features[f'ba_{level}'],
                    0
                )

                # SB success rate
                milb_features[f'sb_success_{level}'] = np.where(
                    (milb_features[sb_col] + milb_features[cs_col]) > 0,
                    milb_features[sb_col] / (milb_features[sb_col] + milb_features[cs_col]),
                    0
                )

                # Extra base hit rate (2B + 3B + HR)
                milb_features[f'xbh_rate_{level}'] = np.where(
                    milb_features[ab_col] > 0,
                    (milb_features[doubles_col] + milb_features[triples_col] + milb_features[hr_col]) / milb_features[ab_col],
                    0
                )

        logger.info(f"Created {len(milb_features.columns) - 1} MiLB features")
        return milb_features

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load and aggregate MLB stats as target variables - comprehensive."""
        logger.info("Loading MLB game logs with comprehensive stats...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    mlb_player_id,
                    COUNT(*) as mlb_games_played,
                    SUM(plate_appearances) as mlb_total_pa,
                    SUM(at_bats) as mlb_total_ab,
                    SUM(hits) as mlb_total_hits,
                    SUM(doubles) as mlb_total_2b,
                    SUM(triples) as mlb_total_3b,
                    SUM(home_runs) as mlb_total_hr,
                    SUM(rbi) as mlb_total_rbi,
                    SUM(walks) as mlb_total_bb,
                    SUM(strikeouts) as mlb_total_so,
                    SUM(stolen_bases) as mlb_total_sb,
                    SUM(caught_stealing) as mlb_total_cs,
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
                'mlb_player_id', 'mlb_games_played', 'mlb_total_pa', 'mlb_total_ab',
                'mlb_total_hits', 'mlb_total_2b', 'mlb_total_3b', 'mlb_total_hr', 'mlb_total_rbi',
                'mlb_total_bb', 'mlb_total_so', 'mlb_total_sb', 'mlb_total_cs',
                'mlb_total_hbp', 'mlb_total_sf', 'mlb_avg_ba', 'mlb_avg_obp',
                'mlb_avg_slg', 'mlb_avg_ops'
            ])

        # Convert Decimal columns to float
        for col in ['mlb_avg_ba', 'mlb_avg_obp', 'mlb_avg_slg', 'mlb_avg_ops']:
            if col in df.columns:
                df[col] = df[col].astype(float)

        # Calculate additional MLB rate stats and advanced metrics
        df['mlb_ba'] = np.where(df['mlb_total_ab'] > 0, df['mlb_total_hits'] / df['mlb_total_ab'], 0)
        df['mlb_bb_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_bb'] / df['mlb_total_pa'], 0)
        df['mlb_so_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_so'] / df['mlb_total_pa'], 0)
        df['mlb_hr_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_hr'] / df['mlb_total_pa'], 0)

        # ISO (Isolated Power) = SLG - BA
        df['mlb_iso'] = df['mlb_avg_slg'] - df['mlb_ba']

        # wOBA approximation (using standard 2023 weights)
        # wOBA = (0.69×NIBB + 0.72×HBP + 0.88×1B + 1.24×2B + 1.56×3B + 1.95×HR) / (AB + BB - IBB + SF + HBP)
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

        # wRC+ approximation: ((wOBA - league_wOBA) / wOBA_scale) * 100 + 100
        # Using 2023 league average wOBA = 0.320, wOBA scale = 1.25
        league_woba = 0.320
        woba_scale = 1.25
        df['mlb_wrc_plus'] = ((df['mlb_woba'] - league_woba) / woba_scale) * 100 + 100

        logger.info(f"Loaded MLB stats for {len(df)} players")
        return df

    async def prepare_dataset(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare combined dataset with features and targets."""
        logger.info("Preparing ML dataset...")

        milb_features = await self.load_milb_features()
        mlb_targets = await self.load_mlb_targets()
        demographics = await self.load_player_demographics()

        # Merge on player ID
        dataset = milb_features.merge(mlb_targets, on='mlb_player_id', how='inner')
        dataset = dataset.merge(demographics, on='mlb_player_id', how='left')

        logger.info(f"Combined dataset: {len(dataset)} players with both MiLB and MLB data")

        # One-hot encode categorical variables
        if 'position' in dataset.columns:
            dataset = pd.get_dummies(dataset, columns=['position'], prefix='pos', drop_first=True)
        if 'bats' in dataset.columns:
            dataset = pd.get_dummies(dataset, columns=['bats'], prefix='bats', drop_first=True)
        if 'throws' in dataset.columns:
            dataset = pd.get_dummies(dataset, columns=['throws'], prefix='throws', drop_first=True)

        # Filter for players with sufficient data
        dataset = dataset[dataset['total_milb_pa'] >= 100]  # At least 100 MiLB PA
        dataset = dataset[dataset['mlb_total_pa'] >= 50]    # At least 50 MLB PA

        logger.info(f"After filtering: {len(dataset)} players")

        # Separate features and targets
        feature_cols = [col for col in dataset.columns
                       if not col.startswith('mlb_') and col != 'mlb_player_id']
        target_cols = ['mlb_wrc_plus', 'mlb_woba', 'mlb_avg_ops', 'mlb_avg_obp',
                      'mlb_avg_slg', 'mlb_iso', 'mlb_ba', 'mlb_bb_rate',
                      'mlb_so_rate', 'mlb_hr_rate']

        self.feature_names = feature_cols
        self.target_names = target_cols

        X = dataset[feature_cols]
        y = dataset[target_cols]

        # Handle missing values in features
        # Fill numeric columns with median
        numeric_cols = X.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if X[col].isna().any():
                X[col] = X[col].fillna(X[col].median())

        # Fill any remaining NaN with 0
        X = X.fillna(0)

        logger.info(f"Features: {len(feature_cols)} columns")
        logger.info(f"Targets: {len(target_cols)} columns")
        logger.info(f"Missing values after imputation: {X.isna().sum().sum()}")

        return X, y

    def train_models(self, X: pd.DataFrame, y: pd.DataFrame):
        """Train multiple ML models."""
        logger.info("Training ML models...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        models = {
            'Linear Regression': LinearRegression(),
            'Ridge Regression': Ridge(alpha=1.0),
            'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42)
        }

        results = {}

        for target in self.target_names:
            logger.info(f"\nTraining models for {target}...")
            results[target] = {}

            y_train_target = y_train[target]
            y_test_target = y_test[target]

            for model_name, model in models.items():
                # Train
                if 'Linear' in model_name or 'Ridge' in model_name:
                    model.fit(X_train_scaled, y_train_target)
                    y_pred = model.predict(X_test_scaled)
                else:
                    model.fit(X_train, y_train_target)
                    y_pred = model.predict(X_test)

                # Evaluate
                mse = mean_squared_error(y_test_target, y_pred)
                mae = mean_absolute_error(y_test_target, y_pred)
                r2 = r2_score(y_test_target, y_pred)

                results[target][model_name] = {
                    'model': model,
                    'mse': mse,
                    'mae': mae,
                    'r2': r2,
                    'predictions': y_pred,
                    'actuals': y_test_target
                }

                logger.info(f"  {model_name}: R2={r2:.3f}, MAE={mae:.4f}")

        self.models = models
        self.results = results
        self.scaler = scaler
        self.X_train = X_train
        self.X_test = X_test
        self.y_train = y_train
        self.y_test = y_test

    def analyze_feature_importance(self):
        """Analyze which MiLB features best predict MLB success."""
        logger.info("\nAnalyzing feature importance...")

        importance_results = {}

        for target in self.target_names:
            # Use Random Forest feature importance
            rf_model = self.results[target]['Random Forest']['model']
            importances = rf_model.feature_importances_

            feature_importance = pd.DataFrame({
                'feature': self.feature_names,
                'importance': importances
            }).sort_values('importance', ascending=False)

            importance_results[target] = feature_importance

            print(f"\n{target} - Top 10 Predictive Features:")
            print(feature_importance.head(10).to_string(index=False))

        return importance_results

    def save_results(self, output_dir: str = 'ml_results'):
        """Save model results and visualizations."""
        import os
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"Saving results to {output_dir}/...")

        # Save summary
        with open(f'{output_dir}/model_performance.txt', 'w') as f:
            f.write("ML Model Performance Summary\n")
            f.write("=" * 80 + "\n\n")

            for target in self.target_names:
                f.write(f"\nTarget: {target}\n")
                f.write("-" * 80 + "\n")
                for model_name, metrics in self.results[target].items():
                    f.write(f"{model_name}:\n")
                    f.write(f"  R2 Score: {metrics['r2']:.4f}\n")
                    f.write(f"  MAE: {metrics['mae']:.4f}\n")
                    f.write(f"  MSE: {metrics['mse']:.4f}\n\n")

        logger.info("Results saved successfully!")


async def main():
    """Main entry point."""
    logger.info("="*80)
    logger.info("MiLB to MLB Performance Predictor")
    logger.info("="*80)

    predictor = MiLBToMLBPredictor()

    # Prepare dataset
    X, y = await predictor.prepare_dataset()

    # Train models
    predictor.train_models(X, y)

    # Analyze feature importance
    predictor.analyze_feature_importance()

    # Save results
    predictor.save_results()

    logger.info("\n" + "="*80)
    logger.info("ML Training Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
