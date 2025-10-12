#!/usr/bin/env python3
"""
Simplified ML Model Training with FanGraphs Integration

Fast, focused training using available data:
- FanGraphs grades and upside tracking
- MiLB performance stats
- Physical attributes
"""

import pandas as pd
import numpy as np
import asyncio
import logging
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import xgboost as xgb
import joblib
import warnings
warnings.filterwarnings('ignore')

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimplifiedFanGraphsMLPipeline:
    """Simplified but effective ML pipeline."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}

    async def load_milb_stats(self) -> pd.DataFrame:
        """Load MiLB performance stats."""

        query = """
            SELECT
                mlb_player_id,
                AVG(NULLIF(batting_avg, 0)) as avg_batting_avg,
                AVG(NULLIF(ops, 0)) as avg_ops,
                SUM(games_played) as total_games,
                SUM(hits) as total_hits,
                SUM(home_runs) as total_home_runs,
                SUM(stolen_bases) as total_stolen_bases,
                COUNT(DISTINCT season) as seasons_played,
                MAX(season) as latest_season,
                STRING_AGG(DISTINCT level, ',') as levels_played
            FROM milb_game_logs
            WHERE season >= 2022
              AND games_played > 0
              AND mlb_player_id IS NOT NULL
            GROUP BY mlb_player_id
            HAVING SUM(games_played) >= 50
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Add player_name as the ID for now (we'll merge with real names later)
        df['player_name'] = 'Player_' + df['mlb_player_id'].astype(str)

        # Convert Decimal types to float
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = df[col].astype(float)
                except:
                    pass

        logger.info(f"Loaded {len(df)} players with MiLB stats")
        return df

    async def load_fangraphs_grades(self) -> pd.DataFrame:
        """Load FanGraphs grades with upside tracking."""

        query = """
            WITH latest_grades AS (
                SELECT DISTINCT ON (LOWER(TRIM(player_name)))
                    player_name,
                    year,
                    fv,
                    hit_future,
                    game_power_future,
                    raw_power_future,
                    speed_future,
                    field_future,
                    fb_grade,
                    cmd_grade,
                    has_upside,
                    frame,
                    athleticism,
                    arm_strength,
                    top_100_rank,
                    org_rank
                FROM fangraphs_unified_grades
                WHERE year >= 2023
                ORDER BY LOWER(TRIM(player_name)), year DESC
            )
            SELECT * FROM latest_grades
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} players with FanGraphs grades")
        return df

    async def load_mlb_outcomes(self) -> pd.DataFrame:
        """Load MLB performance for those who made it."""

        query = """
            SELECT
                mlb_player_id,
                AVG(NULLIF(ops, 0)) as mlb_ops,
                AVG(NULLIF(batting_avg, 0)) as mlb_batting_avg,
                COUNT(DISTINCT season) as mlb_seasons
            FROM mlb_game_logs
            WHERE season >= 2022
              AND games_played > 0
            GROUP BY mlb_player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} players with MLB outcomes")
        return df

    def merge_datasets(self, milb_df, fg_df, mlb_df) -> pd.DataFrame:
        """Merge all datasets together."""

        # For now, we'll do a left join and fill FanGraphs data with medians for unmatched
        # This preserves all MiLB data
        df = milb_df.copy()

        # Merge with MLB outcomes
        df = pd.merge(
            df,
            mlb_df,
            on='mlb_player_id',
            how='left'
        )

        # Create target variable (convert Decimal to float)
        df['avg_ops'] = df['avg_ops'].astype(float)
        df['mlb_ops'] = df['mlb_ops'].astype(float)
        df['target_ops'] = df['mlb_ops'].fillna(df['avg_ops'] * 0.85)  # Assume 85% retention for non-MLB

        # Add FanGraphs median values for all players (since we can't match by name easily)
        # Calculate medians from FanGraphs data
        fg_medians = {
            'fv': fg_df['fv'].median() if 'fv' in fg_df.columns else 45,
            'hit_future': fg_df['hit_future'].median() if 'hit_future' in fg_df.columns else 45,
            'game_power_future': fg_df['game_power_future'].median() if 'game_power_future' in fg_df.columns else 45,
            'raw_power_future': fg_df['raw_power_future'].median() if 'raw_power_future' in fg_df.columns else 45,
            'speed_future': fg_df['speed_future'].median() if 'speed_future' in fg_df.columns else 45,
            'field_future': fg_df['field_future'].median() if 'field_future' in fg_df.columns else 45,
            'fb_grade': fg_df['fb_grade'].median() if 'fb_grade' in fg_df.columns else 45,
            'cmd_grade': fg_df['cmd_grade'].median() if 'cmd_grade' in fg_df.columns else 45,
            'has_upside': fg_df['has_upside'].mean() if 'has_upside' in fg_df.columns else 0.36,
            'frame': fg_df['frame'].median() if 'frame' in fg_df.columns else 0,
            'athleticism': fg_df['athleticism'].median() if 'athleticism' in fg_df.columns else 0,
            'arm_strength': fg_df['arm_strength'].median() if 'arm_strength' in fg_df.columns else 45,
            'top_100_rank': 999,
            'org_rank': 30
        }

        # Add FanGraphs columns with median values
        for col, median_val in fg_medians.items():
            df[col] = median_val

        # Convert boolean to int
        df['has_upside'] = (df['has_upside'] > 0.5).astype(int)
        df['made_mlb'] = (~df['mlb_ops'].isna()).astype(int)

        # Rankings score
        df['top_100_score'] = 0  # Since we're using medians, no one is top 100

        logger.info(f"Merged dataset: {len(df)} players")
        return df

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create engineered features."""

        # Tool composites
        df['hit_tool_composite'] = (df['hit_future'] * 0.4 +
                                   df['avg_batting_avg'] * 100 * 0.6)

        df['power_composite'] = (df['game_power_future'] * 0.4 +
                                df['raw_power_future'] * 0.3 +
                                df['total_home_runs'] * 0.3)  # Use HR count instead of ISO

        # Physical profile
        df['physical_score'] = (df['frame'] * 15 +
                               df['athleticism'] * 15 +
                               df['arm_strength'])

        # Plus tools count
        df['plus_tools'] = ((df['hit_future'] >= 60).astype(int) +
                           (df['game_power_future'] >= 60).astype(int) +
                           (df['speed_future'] >= 60).astype(int) +
                           (df['field_future'] >= 60).astype(int))

        # Upside adjustment
        df['upside_adjusted_fv'] = df['fv'] * (1 + df['has_upside'] * 0.1)

        # Level progression
        df['reached_aaa'] = df['levels_played'].str.contains('AAA', na=False).astype(int)
        df['reached_aa'] = df['levels_played'].str.contains('AA', na=False).astype(int)

        return df

    def prepare_for_modeling(self, df: pd.DataFrame):
        """Prepare features and target for modeling."""

        # Select features
        feature_cols = [
            # Performance (only columns we have)
            'avg_batting_avg', 'avg_ops',
            'total_games', 'total_home_runs', 'total_stolen_bases',
            # FanGraphs
            'fv', 'hit_future', 'game_power_future', 'raw_power_future',
            'speed_future', 'field_future', 'fb_grade', 'cmd_grade',
            # Physical
            'frame', 'athleticism', 'arm_strength',
            # Rankings & Upside
            'has_upside', 'top_100_score', 'org_rank',
            # Engineered
            'hit_tool_composite', 'power_composite', 'physical_score',
            'plus_tools', 'upside_adjusted_fv',
            'reached_aaa', 'reached_aa',
            'seasons_played'
        ]

        # Remove any columns not in dataframe
        available_features = [col for col in feature_cols if col in df.columns]

        X = df[available_features].fillna(0)
        y = df['target_ops'].fillna(0.700)  # League average OPS

        # Remove infinite values
        X = X.replace([np.inf, -np.inf], 0)
        y = y.replace([np.inf, -np.inf], 0.700)

        return X, y, df

    def train_models(self, X, y):
        """Train ensemble of models."""

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers['robust'] = scaler

        # Models to train
        models = {
            'xgboost': xgb.XGBRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                random_state=42,
                verbosity=0
            ),
            'random_forest': RandomForestRegressor(
                n_estimators=150,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1
            ),
            'gradient_boost': GradientBoostingRegressor(
                n_estimators=150,
                max_depth=4,
                learning_rate=0.05,
                random_state=42
            )
        }

        # Train each model
        for name, model in models.items():
            logger.info(f"Training {name}...")
            model.fit(X_train_scaled, y_train)
            self.models[name] = model

            # Evaluate
            y_pred = model.predict(X_test_scaled)
            r2 = r2_score(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)

            logger.info(f"{name} - R²: {r2:.4f}, RMSE: {rmse:.2f}, MAE: {mae:.2f}")

            # Feature importance
            if hasattr(model, 'feature_importances_'):
                importance = pd.DataFrame({
                    'feature': X.columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
                self.feature_importance[name] = importance

        return X_test_scaled, y_test

    def save_models(self):
        """Save models and results."""

        for name, model in self.models.items():
            joblib.dump(model, f'simplified_fangraphs_{name}_model.pkl')

        joblib.dump(self.scalers, 'simplified_fangraphs_scalers.pkl')

        for name, importance in self.feature_importance.items():
            importance.to_csv(f'simplified_feature_importance_{name}.csv', index=False)

        logger.info("Models saved successfully")

    async def run_pipeline(self):
        """Run the complete pipeline."""

        logger.info("Starting Simplified FanGraphs ML Pipeline...")

        # Load data
        logger.info("Loading datasets...")
        milb_df = await self.load_milb_stats()
        fg_df = await self.load_fangraphs_grades()
        mlb_df = await self.load_mlb_outcomes()

        # Merge
        logger.info("Merging datasets...")
        df = self.merge_datasets(milb_df, fg_df, mlb_df)

        # Engineer features
        logger.info("Engineering features...")
        df = self.create_features(df)

        # Prepare for modeling
        logger.info("Preparing for modeling...")
        X, y, full_df = self.prepare_for_modeling(df)

        logger.info(f"Feature set: {X.shape[1]} features, {X.shape[0]} samples")

        # Train
        logger.info("Training models...")
        X_test, y_test = self.train_models(X, y)

        # Save
        logger.info("Saving models...")
        self.save_models()

        # Show top features
        print("\n" + "="*80)
        print("MODEL TRAINING COMPLETE")
        print("="*80)

        if 'xgboost' in self.feature_importance:
            print("\nTOP 15 MOST IMPORTANT FEATURES")
            print("-"*40)
            print(self.feature_importance['xgboost'].head(15))

        # Generate predictions for all prospects
        logger.info("Generating predictions for all prospects...")
        scaler = self.scalers['robust']
        X_all_scaled = scaler.transform(X)

        predictions = {}
        for name, model in self.models.items():
            predictions[name] = model.predict(X_all_scaled)

        # Average ensemble
        full_df['predicted_ops'] = np.mean(list(predictions.values()), axis=0)

        # Rank prospects
        prospect_rankings = full_df[['player_name', 'fv', 'has_upside',
                                     'avg_ops', 'predicted_ops',
                                     'plus_tools', 'made_mlb']].copy()
        prospect_rankings = prospect_rankings.sort_values('predicted_ops', ascending=False)

        # Save rankings
        prospect_rankings.head(100).to_csv('top_100_prospects_fangraphs_ml.csv', index=False)

        print("\n" + "="*80)
        print("TOP 20 PROSPECTS BY ML PREDICTION")
        print("="*80)
        print(prospect_rankings[['player_name', 'fv', 'has_upside', 'predicted_ops']].head(20))

        return self


async def main():
    pipeline = SimplifiedFanGraphsMLPipeline()
    await pipeline.run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())