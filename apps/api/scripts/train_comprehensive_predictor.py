"""
Comprehensive MiLB Predictor - Trains on ALL players

Two-stage approach:
1. Classification: Predict MLB probability (Yes/No)
2. Regression: Predict MLB performance (IF they make it)
"""

import asyncio
import logging
from typing import Tuple
import os

import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    r2_score, mean_absolute_error, classification_report
)

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComprehensiveMLBPredictor:
    """ML predictor using ALL MiLB players (not just MLB players)."""

    def __init__(self):
        self.classification_models = {}
        self.regression_models = {}

    async def load_all_milb_players(self) -> pd.DataFrame:
        """Load ALL MiLB players with age-adjusted features."""
        logger.info("Loading ALL MiLB players with comprehensive features...")

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
                    SUM(m.hits) as total_hits,
                    SUM(m.doubles) as total_2b,
                    SUM(m.triples) as total_3b,
                    SUM(m.home_runs) as total_hr,
                    SUM(m.walks) as total_bb,
                    SUM(m.strikeouts) as total_so,
                    SUM(m.stolen_bases) as total_sb,
                    AVG(m.batting_avg) as avg_ba,
                    AVG(m.on_base_pct) as avg_obp,
                    AVG(m.slugging_pct) as avg_slg,
                    AVG(m.ops) as avg_ops
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
                'total_pa', 'total_ab', 'total_hits', 'total_2b', 'total_3b',
                'total_hr', 'total_bb', 'total_so', 'total_sb',
                'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops'
            ])

        # Convert to float
        numeric_cols = ['age_at_level', 'games_played', 'total_pa', 'total_ab',
                       'total_hits', 'total_2b', 'total_3b', 'total_hr', 'total_bb',
                       'total_so', 'total_sb', 'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

        logger.info(f"Loaded {len(df)} MiLB player-level-season records")
        return df

    def create_player_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate player-level features across levels."""

        # Calculate age-adjusted metrics
        level_avg_ages = {'AAA': 25, 'AA': 23, 'A+': 22, 'A': 21}
        df['age_diff'] = df.apply(
            lambda row: level_avg_ages.get(row['level'], 22) - row['age_at_level']
            if pd.notna(row['age_at_level']) else 0,
            axis=1
        )
        df['age_adj_ops'] = df['avg_ops'] + (df['age_diff'] * 0.010)

        # Aggregate by player and level
        agg_features = df.groupby(['mlb_player_id', 'level']).agg({
            'age_at_level': 'first',
            'games_played': 'sum',
            'total_pa': 'sum',
            'total_ab': 'sum',
            'total_hits': 'sum',
            'total_hr': 'sum',
            'total_bb': 'sum',
            'total_so': 'sum',
            'total_sb': 'sum',
            'avg_ops': 'mean',
            'avg_obp': 'mean',
            'avg_slg': 'mean',
            'age_adj_ops': 'mean'
        }).reset_index()

        # Pivot by level
        level_features = []
        for level in ['AAA', 'AA', 'A+', 'A']:
            level_df = agg_features[agg_features['level'] == level].copy()
            level_df = level_df.drop('level', axis=1)
            level_df.columns = [f'{col}_{level}' if col != 'mlb_player_id' else col
                               for col in level_df.columns]
            level_features.append(level_df)

        # Merge
        player_features = level_features[0]
        for level_df in level_features[1:]:
            player_features = player_features.merge(level_df, on='mlb_player_id', how='outer')

        player_features = player_features.fillna(0)

        # Add derived features
        player_features['total_milb_pa'] = (
            player_features['total_pa_AAA'] + player_features['total_pa_AA'] +
            player_features['total_pa_A+'] + player_features['total_pa_A']
        )
        player_features['highest_level_reached'] = 0
        if 'total_pa_AAA' in player_features.columns:
            player_features.loc[player_features['total_pa_AAA'] > 0, 'highest_level_reached'] = 4
            player_features.loc[(player_features['total_pa_AAA'] == 0) & (player_features['total_pa_AA'] > 0), 'highest_level_reached'] = 3
            player_features.loc[(player_features['total_pa_AA'] == 0) & (player_features['total_pa_A+'] > 0), 'highest_level_reached'] = 2
            player_features.loc[(player_features['total_pa_A+'] == 0) & (player_features['total_pa_A'] > 0), 'highest_level_reached'] = 1

        logger.info(f"Created features for {len(player_features)} unique players")
        return player_features

    async def load_mlb_outcomes(self) -> pd.DataFrame:
        """Load MLB outcomes for classification and regression."""
        logger.info("Loading MLB outcomes...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    mlb_player_id,
                    SUM(plate_appearances) as mlb_total_pa,
                    AVG(ops) as mlb_avg_ops,
                    AVG(on_base_pct) as mlb_avg_obp,
                    AVG(slugging_pct) as mlb_avg_slg
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'mlb_total_pa', 'mlb_avg_ops', 'mlb_avg_obp', 'mlb_avg_slg'
            ])

        # Convert to float
        for col in ['mlb_avg_ops', 'mlb_avg_obp', 'mlb_avg_slg']:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

        # Create binary outcome
        df['made_mlb'] = 1
        df.loc[df['mlb_total_pa'] < 10, 'made_mlb'] = 0  # Less than 10 PA = didn't really make it

        logger.info(f"Loaded MLB outcomes for {len(df)} players")
        logger.info(f"  {df['made_mlb'].sum()} made MLB (10+ PA)")
        logger.info(f"  {len(df) - df['made_mlb'].sum()} cup of coffee (<10 PA)")

        return df

    async def prepare_classification_dataset(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare dataset for MLB classification (Yes/No)."""
        logger.info("Preparing classification dataset...")

        # Load all MiLB players
        milb_raw = await self.load_all_milb_players()
        player_features = self.create_player_features(milb_raw)

        # Load MLB outcomes (LEFT join to keep all MiLB players)
        mlb_outcomes = await self.load_mlb_outcomes()

        dataset = player_features.merge(
            mlb_outcomes[['mlb_player_id', 'made_mlb', 'mlb_total_pa']],
            on='mlb_player_id',
            how='left'
        )

        # Players with no MLB data = didn't make it
        dataset['made_mlb'] = dataset['made_mlb'].fillna(0)
        dataset['mlb_total_pa'] = dataset['mlb_total_pa'].fillna(0)

        # Filter: only players with substantial MiLB time (at least 100 PA total)
        dataset = dataset[dataset['total_milb_pa'] >= 100]

        logger.info(f"Classification dataset: {len(dataset)} players")
        logger.info(f"  Made MLB: {dataset['made_mlb'].sum()} ({dataset['made_mlb'].mean()*100:.1f}%)")
        logger.info(f"  Didn't make MLB: {(1-dataset['made_mlb']).sum()} ({(1-dataset['made_mlb']).mean()*100:.1f}%)")

        # Features and target
        feature_cols = [col for col in dataset.columns
                       if not col.startswith('mlb_') and col != 'mlb_player_id' and col != 'made_mlb']

        X = dataset[feature_cols]
        y = dataset['made_mlb']

        X = X.fillna(0)

        return X, y, feature_cols

    async def prepare_regression_dataset(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare dataset for MLB performance regression (only players who made MLB)."""
        logger.info("Preparing regression dataset...")

        milb_raw = await self.load_all_milb_players()
        player_features = self.create_player_features(milb_raw)
        mlb_outcomes = await self.load_mlb_outcomes()

        # INNER join - only players who made MLB
        dataset = player_features.merge(mlb_outcomes, on='mlb_player_id', how='inner')

        # Filter for meaningful MLB samples
        dataset = dataset[dataset['mlb_total_pa'] >= 50]

        logger.info(f"Regression dataset: {len(dataset)} players with 50+ MLB PA")

        feature_cols = [col for col in dataset.columns
                       if not col.startswith('mlb_') and col != 'mlb_player_id' and col != 'made_mlb']
        target_cols = ['mlb_avg_ops', 'mlb_avg_obp', 'mlb_avg_slg']

        X = dataset[feature_cols]
        y = dataset[target_cols]

        X = X.fillna(0)

        return X, y, feature_cols, target_cols

    async def train_classification_models(self):
        """Train models to predict MLB probability."""
        logger.info("\n" + "="*80)
        logger.info("STAGE 1: MLB CLASSIFICATION (Will they make it?)")
        logger.info("="*80)

        X, y, feature_cols = await self.prepare_classification_dataset()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        models = {
            'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
            'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
        }

        results = []

        for model_name, model in models.items():
            logger.info(f"\nTraining {model_name}...")

            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else None

            acc = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            auc = roc_auc_score(y_test, y_proba) if y_proba is not None else 0

            logger.info(f"  Accuracy: {acc:.3f}")
            logger.info(f"  Precision: {precision:.3f}")
            logger.info(f"  Recall: {recall:.3f}")
            logger.info(f"  F1 Score: {f1:.3f}")
            logger.info(f"  ROC AUC: {auc:.3f}")

            results.append({
                'model': model_name,
                'accuracy': acc,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'auc': auc
            })

            # Feature importance
            if model_name == 'Random Forest':
                importance = pd.DataFrame({
                    'feature': feature_cols,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)

                logger.info("\nTop 15 Features for MLB Classification:")
                for idx, row in importance.head(15).iterrows():
                    logger.info(f"  {row['feature']:40s}: {row['importance']:6.1%}")

        return pd.DataFrame(results)

    async def train_regression_models(self):
        """Train models to predict MLB performance."""
        logger.info("\n" + "="*80)
        logger.info("STAGE 2: MLB PERFORMANCE REGRESSION (How good will they be?)")
        logger.info("="*80)

        X, y, feature_cols, target_cols = await self.prepare_regression_dataset()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        models = {
            'Ridge': Ridge(alpha=1.0),
            'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10),
            'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=5)
        }

        for target in target_cols:
            logger.info(f"\n--- Predicting {target} ---")

            for model_name, model in models.items():
                model.fit(X_train, y_train[target])
                y_pred = model.predict(X_test)

                r2 = r2_score(y_test[target], y_pred)
                mae = mean_absolute_error(y_test[target], y_pred)

                logger.info(f"  {model_name}: R²={r2:.3f}, MAE={mae:.4f}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Comprehensive MLB Predictor - ALL Players")
    logger.info("="*80)

    predictor = ComprehensiveMLBPredictor()

    # Stage 1: Classification
    classification_results = await predictor.train_classification_models()

    # Stage 2: Regression
    await predictor.train_regression_models()

    logger.info("\n" + "="*80)
    logger.info("Training Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
