"""
Train ML models to predict BOTH OPS and wRC+ for prospects.
This version calculates advanced metrics inline rather than using pre-computed tables.
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
        # Linear weights for wOBA calculation (2023 FanGraphs values)
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
        """Calculate wRC+ (Weighted Runs Created Plus)."""
        if league_avg_woba is None:
            league_avg_woba = self.league_avg_woba

        if league_avg_woba == 0:
            return 100

        # Simplified wRC+ calculation
        wrc_plus = (woba / league_avg_woba) * 100
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

            # Total bases from extra base hits
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

    async def load_training_data(self):
        """Load MiLB stats and MLB outcomes with inline metric calculations."""

        query = """
        WITH milb_stats AS (
            -- Get MiLB performance
            SELECT
                mlb_player_id,
                AVG(batting_avg) as avg_batting_avg,
                AVG(ops) as avg_ops,
                SUM(games_played) as total_games,
                SUM(plate_appearances) as plate_appearances,
                SUM(at_bats) as at_bats,
                SUM(hits) as hits,
                SUM(doubles) as doubles,
                SUM(triples) as triples,
                SUM(home_runs) as home_runs,
                SUM(stolen_bases) as stolen_bases,
                SUM(walks) as walks,
                SUM(strikeouts) as strikeouts,
                SUM(hit_by_pitch) as hit_by_pitch,
                COUNT(DISTINCT season) as seasons_played,
                MAX(season) as latest_season,
                STRING_AGG(DISTINCT level, ',') as levels_played
            FROM milb_game_logs
            WHERE season >= 2022
              AND games_played > 0
              AND mlb_player_id IS NOT NULL
            GROUP BY mlb_player_id
            HAVING SUM(games_played) >= 50
        ),
        mlb_outcomes AS (
            -- Get MLB outcomes
            SELECT
                mlb_player_id,
                AVG(ops) as mlb_ops,
                AVG(batting_avg) as mlb_avg,
                SUM(home_runs) as mlb_hr,
                SUM(stolen_bases) as mlb_sb,
                COUNT(DISTINCT season) as mlb_seasons,
                SUM(games_played) as mlb_games,
                -- For wRC+ calculation
                SUM(plate_appearances) as mlb_pa,
                SUM(at_bats) as mlb_ab,
                SUM(hits) as mlb_hits,
                SUM(doubles) as mlb_doubles,
                SUM(triples) as mlb_triples,
                SUM(walks) as mlb_walks,
                SUM(strikeouts) as mlb_strikeouts,
                SUM(hit_by_pitch) as mlb_hbp
            FROM mlb_game_logs
            WHERE season >= 2022
              AND games_played > 0
            GROUP BY mlb_player_id
            HAVING SUM(games_played) >= 30
        )
        SELECT
            ms.*,
            mo.mlb_ops,
            mo.mlb_avg,
            mo.mlb_hr,
            mo.mlb_sb,
            mo.mlb_games,
            mo.mlb_seasons,
            mo.mlb_pa,
            mo.mlb_ab,
            mo.mlb_hits,
            mo.mlb_doubles,
            mo.mlb_triples,
            mo.mlb_walks,
            mo.mlb_strikeouts,
            mo.mlb_hbp,
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

        # Calculate advanced metrics inline
        logger.info("Calculating advanced metrics for MiLB data...")
        df['milb_woba'] = df.apply(self.calculate_woba, axis=1)
        df['milb_wrc_plus'] = df['milb_woba'].apply(lambda x: self.calculate_wrc_plus(x))
        df['milb_iso'] = df.apply(self.calculate_iso, axis=1)
        df['milb_babip'] = df.apply(self.calculate_babip, axis=1)
        df['milb_bb_rate'] = df['walks'] / (df['plate_appearances'] + 1)
        df['milb_k_rate'] = df['strikeouts'] / (df['plate_appearances'] + 1)

        # Calculate MLB wRC+ for those who made it
        logger.info("Calculating MLB wRC+ for outcomes...")
        mlb_mask = df['made_mlb'] == 1

        # Create temporary DataFrame for MLB calculations
        mlb_data = pd.DataFrame({
            'plate_appearances': df.loc[mlb_mask, 'mlb_pa'],
            'at_bats': df.loc[mlb_mask, 'mlb_ab'],
            'hits': df.loc[mlb_mask, 'mlb_hits'],
            'doubles': df.loc[mlb_mask, 'mlb_doubles'],
            'triples': df.loc[mlb_mask, 'mlb_triples'],
            'home_runs': df.loc[mlb_mask, 'mlb_hr'],
            'walks': df.loc[mlb_mask, 'mlb_walks'],
            'strikeouts': df.loc[mlb_mask, 'mlb_strikeouts'],
            'hit_by_pitch': df.loc[mlb_mask, 'mlb_hbp']
        })

        df.loc[mlb_mask, 'mlb_woba'] = mlb_data.apply(self.calculate_woba, axis=1).values
        df.loc[mlb_mask, 'mlb_wrc_plus'] = df.loc[mlb_mask, 'mlb_woba'].apply(lambda x: self.calculate_wrc_plus(x))

        # Fill missing MLB values with estimates based on MiLB performance
        df['mlb_ops'] = df['mlb_ops'].fillna(df['avg_ops'] * 0.85)
        df['mlb_wrc_plus'] = df['mlb_wrc_plus'].fillna(df['milb_wrc_plus'] * 0.85)

        logger.info(f"Loaded {len(df)} players for training")
        logger.info(f"Players who made MLB: {df['made_mlb'].sum()} ({df['made_mlb'].mean()*100:.1f}%)")

        return df

    def create_features(self, df):
        """Create engineered features."""

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

    def prepare_data(self, df):
        """Prepare features and targets for modeling."""

        # Create features
        df = self.create_features(df)

        # Select feature columns
        feature_cols = [
            # Basic performance
            'avg_batting_avg', 'avg_ops',
            'total_games', 'hits', 'home_runs', 'stolen_bases',
            'walks', 'strikeouts',
            # Advanced metrics
            'milb_woba', 'milb_wrc_plus', 'milb_iso', 'milb_babip',
            'milb_bb_rate', 'milb_k_rate',
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
        df.to_csv('dual_target_predictions_inline.csv', index=False)
        logger.info("Predictions saved to dual_target_predictions_inline.csv")

        # Save models
        with open('dual_target_models_inline.pkl', 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scalers': self.scalers,
                'feature_cols': feature_cols
            }, f)
        logger.info("Models saved to dual_target_models_inline.pkl")

        return self


async def main():
    pipeline = DualTargetMLPipeline()
    await pipeline.run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())