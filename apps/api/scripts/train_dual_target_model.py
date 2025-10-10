"""
Train ML models to predict BOTH OPS and wRC+ for prospects.
Uses MiLB stats and FanGraphs grades to predict future MLB performance.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import xgboost as xgb
import pickle
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DualTargetMLPipeline:
    """Train models to predict both OPS and wRC+ simultaneously."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}

    async def load_training_data(self):
        """Load MiLB stats with calculated advanced metrics and MLB outcomes."""

        query = """
        WITH milb_stats AS (
            -- Get MiLB performance with advanced metrics
            SELECT
                mlg.mlb_player_id,
                AVG(mlg.batting_avg) as avg_batting_avg,
                AVG(mlg.ops) as avg_ops,
                SUM(mlg.games_played) as total_games,
                SUM(mlg.hits) as total_hits,
                SUM(mlg.home_runs) as total_home_runs,
                SUM(mlg.stolen_bases) as total_stolen_bases,
                SUM(mlg.walks) as total_walks,
                SUM(mlg.strikeouts) as total_strikeouts,
                COUNT(DISTINCT mlg.season) as seasons_played,
                MAX(mlg.season) as latest_season,
                STRING_AGG(DISTINCT mlg.level, ',') as levels_played,
                -- Advanced metrics
                AVG(am.woba) as avg_woba,
                AVG(am.wrc_plus) as avg_wrc_plus,
                AVG(am.iso) as avg_iso,
                AVG(am.babip) as avg_babip,
                AVG(am.bb_rate) as avg_bb_rate,
                AVG(am.k_rate) as avg_k_rate,
                AVG(am.ops_plus) as avg_ops_plus
            FROM milb_game_logs mlg
            LEFT JOIN advanced_metrics_milb am
                ON mlg.mlb_player_id = am.mlb_player_id
                AND mlg.season = am.season
                AND mlg.level = am.level
            WHERE mlg.season >= 2022
              AND mlg.games_played > 0
              AND mlg.mlb_player_id IS NOT NULL
            GROUP BY mlg.mlb_player_id
            HAVING SUM(mlg.games_played) >= 50
        ),
        mlb_outcomes AS (
            -- Get MLB outcomes with advanced metrics
            SELECT
                mlb.mlb_player_id,
                AVG(mlb.ops) as mlb_ops,
                AVG(mlb.batting_avg) as mlb_avg,
                SUM(mlb.home_runs) as mlb_hr,
                SUM(mlb.stolen_bases) as mlb_sb,
                COUNT(DISTINCT mlb.season) as mlb_seasons,
                SUM(mlb.games_played) as mlb_games,
                -- Advanced metrics from MLB
                AVG(am.wrc_plus) as mlb_wrc_plus,
                AVG(am.woba) as mlb_woba,
                AVG(am.iso) as mlb_iso,
                AVG(am.ops_plus) as mlb_ops_plus
            FROM mlb_game_logs mlb
            LEFT JOIN advanced_metrics_mlb am
                ON mlb.mlb_player_id = am.mlb_player_id
                AND mlb.season = am.season
            WHERE mlb.season >= 2022
              AND mlb.games_played > 0
            GROUP BY mlb.mlb_player_id
            HAVING SUM(mlb.games_played) >= 30
        )
        SELECT
            ms.*,
            mo.mlb_ops,
            mo.mlb_wrc_plus,
            mo.mlb_woba,
            mo.mlb_iso,
            mo.mlb_games,
            mo.mlb_seasons,
            CASE WHEN mo.mlb_ops IS NOT NULL THEN 1 ELSE 0 END as made_mlb
        FROM milb_stats ms
        LEFT JOIN mlb_outcomes mo ON ms.mlb_player_id = mo.mlb_player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to numeric
        for col in df.columns:
            if col not in ['levels_played']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Fill missing values
        df['mlb_ops'] = df['mlb_ops'].fillna(df['avg_ops'] * 0.85)
        df['mlb_wrc_plus'] = df['mlb_wrc_plus'].fillna(df['avg_wrc_plus'] * 0.85)

        logger.info(f"Loaded {len(df)} players for training")
        logger.info(f"Players who made MLB: {df['made_mlb'].sum()} ({df['made_mlb'].mean()*100:.1f}%)")

        return df

    def create_features(self, df):
        """Create engineered features."""

        # Performance ratios
        df['power_speed'] = df['total_home_runs'] / (df['total_stolen_bases'] + 1)
        df['k_bb_ratio'] = df['total_strikeouts'] / (df['total_walks'] + 1)

        # Production rates
        df['hr_per_game'] = df['total_home_runs'] / (df['total_games'] + 1)
        df['hits_per_game'] = df['total_hits'] / (df['total_games'] + 1)

        # Level progression
        df['reached_aaa'] = df['levels_played'].str.contains('AAA', na=False).astype(int)
        df['reached_aa'] = df['levels_played'].str.contains('AA', na=False).astype(int)

        # Experience
        df['games_per_season'] = df['total_games'] / (df['seasons_played'] + 1)

        # Recent performance
        df['is_recent'] = (df['latest_season'] >= 2024).astype(int)

        # Advanced metric features
        df['woba_consistency'] = df['avg_woba'] / (df['avg_k_rate'] + 0.01)
        df['iso_power'] = df['avg_iso'] * df['total_home_runs']

        return df

    def prepare_data(self, df):
        """Prepare features and targets for modeling."""

        # Create features
        df = self.create_features(df)

        # Select feature columns
        feature_cols = [
            # Basic performance
            'avg_batting_avg', 'avg_ops',
            'total_games', 'total_hits', 'total_home_runs', 'total_stolen_bases',
            'total_walks', 'total_strikeouts',
            # Advanced metrics
            'avg_woba', 'avg_wrc_plus', 'avg_iso', 'avg_babip',
            'avg_bb_rate', 'avg_k_rate', 'avg_ops_plus',
            # Engineered features
            'power_speed', 'k_bb_ratio', 'hr_per_game', 'hits_per_game',
            'reached_aaa', 'reached_aa', 'games_per_season', 'is_recent',
            'woba_consistency', 'iso_power',
            # Experience
            'seasons_played'
        ]

        # Remove columns not in dataframe
        available_features = [col for col in feature_cols if col in df.columns]

        X = df[available_features].fillna(0)

        # Prepare dual targets
        y_ops = df['mlb_ops'].fillna(0.700)
        y_wrc_plus = df['mlb_wrc_plus'].fillna(100)

        # Combine targets
        y = pd.DataFrame({
            'ops': y_ops,
            'wrc_plus': y_wrc_plus
        })

        # Remove infinite values
        X = X.replace([np.inf, -np.inf], 0)

        logger.info(f"Feature set: {len(available_features)} features, {len(X)} samples")
        logger.info(f"Target OPS range: {y_ops.min():.3f} - {y_ops.max():.3f}")
        logger.info(f"Target wRC+ range: {y_wrc_plus.min():.1f} - {y_wrc_plus.max():.1f}")

        return X, y, df, available_features

    async def train_models(self, X, y):
        """Train multiple models for dual-target prediction."""

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers['standard'] = scaler

        print("\n" + "="*80)
        print("DUAL-TARGET MODEL PERFORMANCE (OPS & wRC+)")
        print("="*80)

        # Define models
        base_models = {
            'xgboost': xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42),
            'random_forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
            'gradient_boost': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        }

        best_r2_ops = -1
        best_r2_wrc = -1
        best_model_ops = None
        best_model_wrc = None

        for name, base_model in base_models.items():
            # Create multi-output version
            if name == 'gradient_boost':
                # Train separate models for gradient boost
                model_ops = base_model
                model_wrc = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)

                # Train for OPS
                model_ops.fit(X_train_scaled, y_train['ops'])
                y_pred_ops = model_ops.predict(X_test_scaled)

                # Train for wRC+
                model_wrc.fit(X_train_scaled, y_train['wrc_plus'])
                y_pred_wrc = model_wrc.predict(X_test_scaled)

                self.models[f'{name}_ops'] = model_ops
                self.models[f'{name}_wrc'] = model_wrc

            else:
                # Use MultiOutputRegressor for others
                model = MultiOutputRegressor(base_model)
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)

                y_pred_ops = y_pred[:, 0]
                y_pred_wrc = y_pred[:, 1]

                self.models[name] = model

            # Evaluate OPS prediction
            r2_ops = r2_score(y_test['ops'], y_pred_ops)
            rmse_ops = np.sqrt(mean_squared_error(y_test['ops'], y_pred_ops))
            mae_ops = mean_absolute_error(y_test['ops'], y_pred_ops)

            # Evaluate wRC+ prediction
            r2_wrc = r2_score(y_test['wrc_plus'], y_pred_wrc)
            rmse_wrc = np.sqrt(mean_squared_error(y_test['wrc_plus'], y_pred_wrc))
            mae_wrc = mean_absolute_error(y_test['wrc_plus'], y_pred_wrc)

            print(f"\n{name:15s}:")
            print(f"  OPS   - R²: {r2_ops:.3f}, RMSE: {rmse_ops:.3f}, MAE: {mae_ops:.3f}")
            print(f"  wRC+  - R²: {r2_wrc:.3f}, RMSE: {rmse_wrc:.1f}, MAE: {mae_wrc:.1f}")

            if r2_ops > best_r2_ops:
                best_r2_ops = r2_ops
                best_model_ops = name

            if r2_wrc > best_r2_wrc:
                best_r2_wrc = r2_wrc
                best_model_wrc = name

        print(f"\nBest model for OPS: {best_model_ops} (R² = {best_r2_ops:.3f})")
        print(f"Best model for wRC+: {best_model_wrc} (R² = {best_r2_wrc:.3f})")

        return X_train, y_train

    async def generate_predictions(self, df, feature_cols):
        """Generate predictions for all players."""

        # Prepare features
        df = self.create_features(df)
        X_all = df[feature_cols].fillna(0)
        X_all = X_all.replace([np.inf, -np.inf], 0)

        # Scale
        X_all_scaled = self.scalers['standard'].transform(X_all)

        # Generate predictions
        predictions_ops = []
        predictions_wrc = []

        for name, model in self.models.items():
            if '_ops' in name:
                pred = model.predict(X_all_scaled)
                predictions_ops.append(pred)
            elif '_wrc' in name:
                pred = model.predict(X_all_scaled)
                predictions_wrc.append(pred)
            elif hasattr(model, 'predict'):
                pred = model.predict(X_all_scaled)
                if len(pred.shape) > 1:
                    predictions_ops.append(pred[:, 0])
                    predictions_wrc.append(pred[:, 1])

        # Average predictions
        df['predicted_ops'] = np.mean(predictions_ops, axis=0)
        df['predicted_wrc_plus'] = np.mean(predictions_wrc, axis=0)

        # Calculate composite score (weighted average)
        df['composite_score'] = (df['predicted_ops'] / 0.750) * 50 + (df['predicted_wrc_plus'] / 100) * 50

        return df

    async def run_pipeline(self):
        """Run complete dual-target training pipeline."""

        # Load data
        logger.info("Loading training data...")
        df = await self.load_training_data()

        # Prepare data
        logger.info("Preparing features...")
        X, y, df, feature_cols = self.prepare_data(df)

        # Train models
        logger.info("Training models...")
        X_train, y_train = await self.train_models(X, y)

        # Feature importance (from first model for simplicity)
        if 'xgboost_ops' in self.models:
            model = self.models['xgboost_ops']
        elif 'gradient_boost_ops' in self.models:
            model = self.models['gradient_boost_ops']
        else:
            model = list(self.models.values())[0]

        if hasattr(model, 'feature_importances_'):
            importance_df = pd.DataFrame({
                'feature': feature_cols,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)

            print("\n" + "="*80)
            print("TOP 15 FEATURE IMPORTANCE")
            print("="*80)
            print(importance_df.head(15).to_string(index=False))

        # Generate predictions for all players
        logger.info("Generating predictions...")
        df = await self.generate_predictions(df, feature_cols)

        # Rank players
        df = df.sort_values('composite_score', ascending=False)

        print("\n" + "="*80)
        print("TOP 30 PROSPECTS BY COMPOSITE SCORE")
        print("="*80)
        display_cols = ['mlb_player_id', 'avg_ops', 'predicted_ops', 'predicted_wrc_plus',
                       'composite_score', 'made_mlb']
        print(df[display_cols].head(30).to_string(index=False))

        # Save results
        df.to_csv('dual_target_predictions.csv', index=False)
        logger.info("Predictions saved to dual_target_predictions.csv")

        # Save models
        with open('dual_target_models.pkl', 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scalers': self.scalers,
                'feature_cols': feature_cols
            }, f)
        logger.info("Models saved to dual_target_models.pkl")

        return self


async def main():
    pipeline = DualTargetMLPipeline()
    await pipeline.run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())