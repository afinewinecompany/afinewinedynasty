"""
Train ensemble ML models for prospect prediction.

Uses multiple algorithms (Random Forest, XGBoost, LightGBM, CatBoost)
combined in a voting ensemble for robust predictions.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from app.db.database import engine
import logging
from datetime import datetime
from typing import Tuple, Dict, List
import pickle
import json

from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostRegressor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnsembleProspectPredictor:
    """Train ensemble models for prospect prediction."""

    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_names = []
        self.feature_importance = {}

    async def load_milb_features(self) -> pd.DataFrame:
        """Load MiLB game logs and calculate features."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    prospect_id,
                    season,
                    level,
                    SUM(plate_appearances) as total_pa,
                    SUM(at_bats) as total_ab,
                    SUM(hits) as total_h,
                    SUM(doubles) as total_2b,
                    SUM(triples) as total_3b,
                    SUM(home_runs) as total_hr,
                    SUM(walks) as total_bb,
                    SUM(strikeouts) as total_so,
                    SUM(stolen_bases) as total_sb,
                    SUM(hit_by_pitch) as total_hbp,
                    SUM(sacrifice_flies) as total_sf,
                    AVG(batting_avg) as avg_ba,
                    AVG(on_base_pct) as avg_obp,
                    AVG(slugging_pct) as avg_slg,
                    AVG(ops) as avg_ops,
                    COUNT(*) as games_played
                FROM milb_game_logs
                WHERE plate_appearances > 0
                GROUP BY prospect_id, season, level
                ORDER BY prospect_id, season, level
            """))
            rows = result.fetchall()

        if not rows:
            logger.error("No MiLB game logs found")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'season', 'level', 'total_pa', 'total_ab', 'total_h',
            'total_2b', 'total_3b', 'total_hr', 'total_bb', 'total_so', 'total_sb',
            'total_hbp', 'total_sf', 'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops', 'games_played'
        ])

        # Convert to numeric
        numeric_cols = df.columns.difference(['prospect_id', 'level'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded {len(df):,} prospect-season-level records")
        return df

    async def load_statcast_metrics(self) -> pd.DataFrame:
        """Load aggregated Statcast metrics."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id as prospect_id,
                    season,
                    level,
                    avg_ev,
                    max_ev,
                    ev_90th,
                    hard_hit_pct,
                    avg_la,
                    avg_la_hard,
                    fb_ev,
                    barrel_pct,
                    gb_pct,
                    ld_pct,
                    fb_pct
                FROM milb_statcast_metrics
            """))
            rows = result.fetchall()

        if not rows:
            logger.warning("No Statcast metrics found - will continue without them")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'season', 'level', 'avg_ev', 'max_ev', 'ev_90th',
            'hard_hit_pct', 'avg_la', 'avg_la_hard', 'fb_ev', 'barrel_pct',
            'gb_pct', 'ld_pct', 'fb_pct'
        ])

        logger.info(f"Loaded Statcast metrics for {df['prospect_id'].nunique()} prospects")
        return df

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load MLB performance as training targets."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id as prospect_id,
                    SUM(plate_appearances) as mlb_pa,
                    SUM(at_bats) as mlb_ab,
                    SUM(hits) as mlb_h,
                    SUM(home_runs) as mlb_hr,
                    SUM(walks) as mlb_bb,
                    SUM(strikeouts) as mlb_so,
                    AVG(batting_avg) as mlb_ba,
                    AVG(on_base_pct) as mlb_obp,
                    AVG(slugging_pct) as mlb_slg,
                    AVG(ops) as mlb_ops
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        if not rows:
            logger.warning("No MLB targets found")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'mlb_pa', 'mlb_ab', 'mlb_h', 'mlb_hr', 'mlb_bb',
            'mlb_so', 'mlb_ba', 'mlb_obp', 'mlb_slg', 'mlb_ops'
        ])

        for col in df.columns:
            if col != 'prospect_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded MLB targets for {len(df)} prospects")
        return df

    def calculate_features(self, milb_df: pd.DataFrame, statcast_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate aggregated features by prospect."""

        # Calculate derived stats
        milb_df['singles'] = milb_df['total_h'] - milb_df['total_2b'] - milb_df['total_3b'] - milb_df['total_hr']
        milb_df['tb'] = milb_df['singles'] + (milb_df['total_2b'] * 2) + (milb_df['total_3b'] * 3) + (milb_df['total_hr'] * 4)
        milb_df['iso'] = milb_df['avg_slg'] - milb_df['avg_ba']
        milb_df['bb_rate'] = milb_df['total_bb'] / milb_df['total_pa'].replace(0, np.nan)
        milb_df['so_rate'] = milb_df['total_so'] / milb_df['total_pa'].replace(0, np.nan)
        milb_df['hr_rate'] = milb_df['total_hr'] / milb_df['total_pa'].replace(0, np.nan)

        # Aggregate by prospect
        player_agg = milb_df.groupby('prospect_id').agg({
            'total_pa': 'sum',
            'total_ab': 'sum',
            'total_h': 'sum',
            'total_hr': 'sum',
            'total_bb': 'sum',
            'total_so': 'sum',
            'tb': 'sum',
            'avg_ops': 'mean',
            'avg_obp': 'mean',
            'avg_slg': 'mean',
            'iso': 'mean',
            'bb_rate': 'mean',
            'so_rate': 'mean',
            'hr_rate': 'mean',
            'season': 'nunique',
            'level': 'nunique'
        }).reset_index()

        player_agg.columns = [
            'prospect_id', 'total_pa', 'total_ab', 'total_h', 'total_hr', 'total_bb',
            'total_so', 'total_tb', 'avg_ops', 'avg_obp', 'avg_slg', 'iso',
            'bb_rate', 'so_rate', 'hr_rate', 'seasons_played', 'levels_played'
        ]

        # Get highest level stats
        level_order = {'AAA': 6, 'AA': 5, 'A+': 4, 'A': 3, 'Rookie+': 2, 'Rookie': 1}
        milb_df['level_rank'] = milb_df['level'].map(level_order).fillna(0)

        highest_level = milb_df.loc[milb_df.groupby('prospect_id')['level_rank'].idxmax()]
        highest_level_features = highest_level.groupby('prospect_id').agg({
            'level': 'first',
            'avg_ops': 'first',
            'bb_rate': 'first',
            'so_rate': 'first',
            'total_pa': 'sum'
        }).reset_index()

        highest_level_features.columns = [
            'prospect_id', 'highest_level', 'highest_level_ops',
            'highest_level_bb_rate', 'highest_level_so_rate', 'highest_level_pa'
        ]

        # Merge features
        features = player_agg.merge(highest_level_features, on='prospect_id', how='left')

        # Add Statcast metrics if available
        if not statcast_df.empty:
            # Get most recent Statcast metrics for each prospect
            statcast_recent = statcast_df.sort_values('season', ascending=False).groupby('prospect_id').first().reset_index()
            statcast_features = statcast_recent[[
                'prospect_id', 'avg_ev', 'max_ev', 'ev_90th', 'hard_hit_pct',
                'avg_la', 'fb_ev', 'barrel_pct', 'gb_pct'
            ]]
            features = features.merge(statcast_features, on='prospect_id', how='left')

        # Fill NaN values
        features = features.fillna(0)

        logger.info(f"Calculated features for {len(features)} prospects")
        return features

    def train_ensemble(self, X: pd.DataFrame, y: pd.Series, target_name: str) -> Dict:
        """Train ensemble of multiple models."""

        logger.info(f"\nTraining ensemble for {target_name}...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers[target_name] = scaler

        # Individual models
        rf_model = RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )

        xgb_model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )

        lgb_model = lgb.LGBMRegressor(
            n_estimators=200,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1
        )

        cat_model = CatBoostRegressor(
            iterations=200,
            depth=8,
            learning_rate=0.05,
            random_state=42,
            verbose=False
        )

        # Train individual models
        logger.info("  Training Random Forest...")
        rf_model.fit(X_train, y_train)
        rf_score = r2_score(y_test, rf_model.predict(X_test))

        logger.info("  Training XGBoost...")
        xgb_model.fit(X_train, y_train)
        xgb_score = r2_score(y_test, xgb_model.predict(X_test))

        logger.info("  Training LightGBM...")
        lgb_model.fit(X_train, y_train)
        lgb_score = r2_score(y_test, lgb_model.predict(X_test))

        logger.info("  Training CatBoost...")
        cat_model.fit(X_train, y_train)
        cat_score = r2_score(y_test, cat_model.predict(X_test))

        # Create weighted ensemble based on individual performance
        weights = np.array([rf_score, xgb_score, lgb_score, cat_score])
        weights = np.maximum(weights, 0)  # Remove negative weights
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(4) / 4

        logger.info(f"  Ensemble weights: RF={weights[0]:.3f}, XGB={weights[1]:.3f}, LGB={weights[2]:.3f}, CAT={weights[3]:.3f}")

        # Ensemble predictions
        ensemble_pred = (
            rf_model.predict(X_test) * weights[0] +
            xgb_model.predict(X_test) * weights[1] +
            lgb_model.predict(X_test) * weights[2] +
            cat_model.predict(X_test) * weights[3]
        )

        ensemble_score = r2_score(y_test, ensemble_pred)
        ensemble_mae = mean_absolute_error(y_test, ensemble_pred)

        logger.info(f"  Individual R² scores: RF={rf_score:.3f}, XGB={xgb_score:.3f}, LGB={lgb_score:.3f}, CAT={cat_score:.3f}")
        logger.info(f"  Ensemble R²: {ensemble_score:.3f}")
        logger.info(f"  Ensemble MAE: {ensemble_mae:.3f}")

        # Store models
        self.models[target_name] = {
            'rf': rf_model,
            'xgb': xgb_model,
            'lgb': lgb_model,
            'cat': cat_model,
            'weights': weights
        }

        # Feature importance (from RF)
        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': rf_model.feature_importances_
        }).sort_values('importance', ascending=False)

        self.feature_importance[target_name] = feature_importance

        return {
            'ensemble_r2': ensemble_score,
            'ensemble_mae': ensemble_mae,
            'rf_r2': rf_score,
            'xgb_r2': xgb_score,
            'lgb_r2': lgb_score,
            'cat_r2': cat_score,
            'feature_importance': feature_importance.head(10).to_dict('records')
        }

    def predict_ensemble(self, X: pd.DataFrame, target_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """Make ensemble predictions with confidence intervals."""

        if target_name not in self.models:
            raise ValueError(f"No model trained for {target_name}")

        # Scale features
        X_scaled = self.scalers[target_name].transform(X)

        models = self.models[target_name]
        weights = models['weights']

        # Get predictions from each model
        rf_pred = models['rf'].predict(X)
        xgb_pred = models['xgb'].predict(X)
        lgb_pred = models['lgb'].predict(X)
        cat_pred = models['cat'].predict(X)

        # Ensemble prediction
        ensemble_pred = (
            rf_pred * weights[0] +
            xgb_pred * weights[1] +
            lgb_pred * weights[2] +
            cat_pred * weights[3]
        )

        # Estimate confidence interval from model disagreement
        all_preds = np.column_stack([rf_pred, xgb_pred, lgb_pred, cat_pred])
        pred_std = np.std(all_preds, axis=1)

        return ensemble_pred, pred_std

    async def train_all_targets(self):
        """Train models for all target metrics."""

        # Load data
        milb_df = await self.load_milb_features()
        statcast_df = await self.load_statcast_metrics()
        mlb_targets = await self.load_mlb_targets()

        # Calculate features
        features = self.calculate_features(milb_df, statcast_df)

        # Merge with targets (LEFT JOIN to keep all prospects)
        dataset = features.merge(mlb_targets, on='prospect_id', how='left')

        # Fill missing MLB stats with zeros
        mlb_cols = [col for col in dataset.columns if col.startswith('mlb_')]
        dataset[mlb_cols] = dataset[mlb_cols].fillna(0)

        logger.info(f"\nDataset: {len(dataset)} prospects")
        logger.info(f"  With MLB data: {(dataset['mlb_pa'] > 0).sum()}")
        logger.info(f"  Prospects only: {(dataset['mlb_pa'] == 0).sum()}")

        # Define features
        feature_cols = [
            'total_pa', 'avg_ops', 'avg_obp', 'avg_slg', 'iso', 'bb_rate', 'so_rate', 'hr_rate',
            'highest_level_ops', 'highest_level_bb_rate', 'highest_level_so_rate',
            'seasons_played', 'levels_played'
        ]

        # Add Statcast if available
        statcast_cols = ['avg_ev', 'max_ev', 'ev_90th', 'hard_hit_pct', 'avg_la', 'fb_ev', 'barrel_pct', 'gb_pct']
        for col in statcast_cols:
            if col in dataset.columns and dataset[col].sum() > 0:
                feature_cols.append(col)

        self.feature_names = feature_cols
        X = dataset[feature_cols]

        # Train models for each target
        results = {}
        targets = ['mlb_ops', 'mlb_obp', 'mlb_slg']

        for target in targets:
            if target in dataset.columns:
                y = dataset[target]
                results[target] = self.train_ensemble(X, y, target)

        # Save models
        self.save_models()

        return results, dataset

    def save_models(self):
        """Save trained models to disk."""
        model_data = {
            'models': self.models,
            'scalers': self.scalers,
            'feature_names': self.feature_names,
            'feature_importance': {k: v.to_dict('records') for k, v in self.feature_importance.items()}
        }

        with open('ensemble_models.pkl', 'wb') as f:
            pickle.dump(model_data, f)

        logger.info("\nModels saved to ensemble_models.pkl")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Ensemble ML Model Training")
    logger.info("="*80)

    predictor = EnsembleProspectPredictor()

    # Train models
    results, dataset = await predictor.train_all_targets()

    # Print summary
    print("\n" + "="*80)
    print("TRAINING RESULTS")
    print("="*80)

    for target, metrics in results.items():
        print(f"\n{target}:")
        print(f"  Ensemble R²: {metrics['ensemble_r2']:.3f}")
        print(f"  Ensemble MAE: {metrics['ensemble_mae']:.3f}")
        print(f"  Individual R²: RF={metrics['rf_r2']:.3f}, XGB={metrics['xgb_r2']:.3f}, LGB={metrics['lgb_r2']:.3f}, CAT={metrics['cat_r2']:.3f}")
        print(f"\n  Top 5 Features:")
        for i, feat in enumerate(metrics['feature_importance'][:5], 1):
            print(f"    {i}. {feat['feature']}: {feat['importance']:.4f}")

    logger.info("\n" + "="*80)
    logger.info("Training Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
