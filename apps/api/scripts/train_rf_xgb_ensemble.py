"""
Train Random Forest + XGBoost ensemble for prospect prediction.
Uses only RF and XGBoost to avoid dependency issues.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from app.db.database import engine
import logging
from datetime import datetime
from typing import Tuple, Dict
import pickle

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    logging.warning("XGBoost not available, using Random Forest only")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimplifiedEnsemblePredictor:
    """Train simplified ensemble models for prospect prediction."""

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
                    AVG(batting_avg) as avg_ba,
                    AVG(on_base_pct) as avg_obp,
                    AVG(slugging_pct) as avg_slg,
                    AVG(ops) as avg_ops,
                    COUNT(*) as games_played
                FROM milb_game_logs
                WHERE plate_appearances > 0
                GROUP BY prospect_id, season, level
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'season', 'level', 'total_pa', 'total_ab', 'total_h',
            'total_2b', 'total_3b', 'total_hr', 'total_bb', 'total_so', 'total_sb',
            'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops', 'games_played'
        ])

        numeric_cols = df.columns.difference(['prospect_id', 'level'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded {len(df):,} prospect-season-level records")
        return df

    async def load_statcast_metrics(self) -> pd.DataFrame:
        """Load Statcast metrics."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id as prospect_id,
                    season,
                    avg_ev, max_ev, ev_90th, hard_hit_pct,
                    avg_la, fb_ev, barrel_pct
                FROM milb_statcast_metrics
            """))
            rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'prospect_id', 'season', 'avg_ev', 'max_ev', 'ev_90th',
            'hard_hit_pct', 'avg_la', 'fb_ev', 'barrel_pct'
        ])

        logger.info(f"Loaded Statcast for {df['prospect_id'].nunique()} prospects")
        return df

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load MLB targets."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT
                    mlb_player_id as prospect_id,
                    SUM(plate_appearances) as mlb_pa,
                    AVG(ops) as mlb_ops,
                    AVG(on_base_pct) as mlb_obp,
                    AVG(slugging_pct) as mlb_slg
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=['prospect_id', 'mlb_pa', 'mlb_ops', 'mlb_obp', 'mlb_slg'])
        for col in df.columns:
            if col != 'prospect_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded MLB targets for {len(df)} prospects")
        return df

    def calculate_features(self, milb_df: pd.DataFrame, statcast_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate features."""
        milb_df['singles'] = milb_df['total_h'] - milb_df['total_2b'] - milb_df['total_3b'] - milb_df['total_hr']
        milb_df['tb'] = milb_df['singles'] + (milb_df['total_2b'] * 2) + (milb_df['total_3b'] * 3) + (milb_df['total_hr'] * 4)
        milb_df['iso'] = milb_df['avg_slg'] - milb_df['avg_ba']
        milb_df['bb_rate'] = milb_df['total_bb'] / milb_df['total_pa'].replace(0, np.nan)
        milb_df['so_rate'] = milb_df['total_so'] / milb_df['total_pa'].replace(0, np.nan)
        milb_df['hr_rate'] = milb_df['total_hr'] / milb_df['total_pa'].replace(0, np.nan)

        player_agg = milb_df.groupby('prospect_id').agg({
            'total_pa': 'sum',
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
            'prospect_id', 'total_pa', 'avg_ops', 'avg_obp', 'avg_slg',
            'iso', 'bb_rate', 'so_rate', 'hr_rate', 'seasons_played', 'levels_played'
        ]

        # Highest level
        level_order = {'AAA': 6, 'AA': 5, 'A+': 4, 'A': 3, 'Rookie+': 2, 'Rookie': 1}
        milb_df['level_rank'] = milb_df['level'].map(level_order).fillna(0)
        highest = milb_df.loc[milb_df.groupby('prospect_id')['level_rank'].idxmax()]
        highest_features = highest.groupby('prospect_id').agg({
            'avg_ops': 'first',
            'bb_rate': 'first',
            'so_rate': 'first'
        }).reset_index()
        highest_features.columns = ['prospect_id', 'highest_level_ops', 'highest_level_bb_rate', 'highest_level_so_rate']

        features = player_agg.merge(highest_features, on='prospect_id', how='left')

        # Add Statcast
        if not statcast_df.empty:
            statcast_recent = statcast_df.sort_values('season', ascending=False).groupby('prospect_id').first().reset_index()
            features = features.merge(statcast_recent[['prospect_id', 'avg_ev', 'max_ev', 'fb_ev', 'barrel_pct']],
                                     on='prospect_id', how='left')

        features = features.fillna(0)
        logger.info(f"Calculated features for {len(features)} prospects")
        return features

    def train_ensemble(self, X: pd.DataFrame, y: pd.Series, target_name: str) -> Dict:
        """Train RF + XGBoost ensemble."""
        logger.info(f"\nTraining ensemble for {target_name}...")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Random Forest
        rf_model = RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            random_state=42,
            n_jobs=-1
        )

        logger.info("  Training Random Forest...")
        rf_model.fit(X_train, y_train)
        rf_pred = rf_model.predict(X_test)
        rf_score = r2_score(y_test, rf_pred)

        models_dict = {'rf': rf_model}
        predictions = [rf_pred]
        scores = [rf_score]

        # XGBoost if available
        if HAS_XGB:
            xgb_model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                random_state=42,
                n_jobs=-1
            )

            logger.info("  Training XGBoost...")
            xgb_model.fit(X_train, y_train)
            xgb_pred = xgb_model.predict(X_test)
            xgb_score = r2_score(y_test, xgb_pred)

            models_dict['xgb'] = xgb_model
            predictions.append(xgb_pred)
            scores.append(xgb_score)

        # Weighted ensemble
        weights = np.array(scores)
        weights = np.maximum(weights, 0)
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(len(scores)) / len(scores)

        ensemble_pred = sum(pred * w for pred, w in zip(predictions, weights))
        ensemble_score = r2_score(y_test, ensemble_pred)
        ensemble_mae = mean_absolute_error(y_test, ensemble_pred)

        logger.info(f"  R² scores: RF={rf_score:.3f}" + (f", XGB={xgb_score:.3f}" if HAS_XGB else ""))
        logger.info(f"  Ensemble R²: {ensemble_score:.3f}, MAE: {ensemble_mae:.3f}")

        models_dict['weights'] = weights
        self.models[target_name] = models_dict

        feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': rf_model.feature_importances_
        }).sort_values('importance', ascending=False)
        self.feature_importance[target_name] = feature_importance

        return {
            'ensemble_r2': ensemble_score,
            'ensemble_mae': ensemble_mae,
            'rf_r2': rf_score,
            'xgb_r2': xgb_score if HAS_XGB else None,
            'feature_importance': feature_importance.head(10).to_dict('records')
        }

    async def train_all_targets(self):
        """Train all models."""
        milb_df = await self.load_milb_features()
        statcast_df = await self.load_statcast_metrics()
        mlb_targets = await self.load_mlb_targets()

        features = self.calculate_features(milb_df, statcast_df)
        dataset = features.merge(mlb_targets, on='prospect_id', how='left')

        mlb_cols = [col for col in dataset.columns if col.startswith('mlb_')]
        dataset[mlb_cols] = dataset[mlb_cols].fillna(0)

        logger.info(f"\nDataset: {len(dataset)} prospects")
        logger.info(f"  With MLB data: {(dataset['mlb_pa'] > 0).sum()}")

        feature_cols = [
            'total_pa', 'avg_ops', 'avg_obp', 'avg_slg', 'iso', 'bb_rate', 'so_rate', 'hr_rate',
            'highest_level_ops', 'highest_level_bb_rate', 'highest_level_so_rate',
            'seasons_played', 'levels_played'
        ]

        statcast_cols = ['avg_ev', 'max_ev', 'fb_ev', 'barrel_pct']
        for col in statcast_cols:
            if col in dataset.columns and dataset[col].sum() > 0:
                feature_cols.append(col)

        self.feature_names = feature_cols
        X = dataset[feature_cols]

        results = {}
        for target in ['mlb_ops', 'mlb_obp', 'mlb_slg']:
            if target in dataset.columns:
                y = dataset[target]
                results[target] = self.train_ensemble(X, y, target)

        with open('simplified_ensemble_models.pkl', 'wb') as f:
            pickle.dump({
                'models': self.models,
                'feature_names': self.feature_names,
                'feature_importance': {k: v.to_dict('records') for k, v in self.feature_importance.items()}
            }, f)

        logger.info("\nModels saved to simplified_ensemble_models.pkl")
        return results, dataset


async def main():
    logger.info("="*80)
    logger.info("Simplified Ensemble ML Training (RF + XGBoost)")
    logger.info("="*80)

    predictor = SimplifiedEnsemblePredictor()
    results, dataset = await predictor.train_all_targets()

    print("\n" + "="*80)
    print("TRAINING RESULTS")
    print("="*80)

    for target, metrics in results.items():
        print(f"\n{target}:")
        print(f"  Ensemble R²: {metrics['ensemble_r2']:.3f}")
        print(f"  Ensemble MAE: {metrics['ensemble_mae']:.3f}")
        print(f"  RF R²: {metrics['rf_r2']:.3f}")
        if metrics['xgb_r2']:
            print(f"  XGBoost R²: {metrics['xgb_r2']:.3f}")
        print(f"\n  Top 5 Features:")
        for i, feat in enumerate(metrics['feature_importance'][:5], 1):
            print(f"    {i}. {feat['feature']}: {feat['importance']:.4f}")

    logger.info("\n" + "="*80)
    logger.info("Training Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
