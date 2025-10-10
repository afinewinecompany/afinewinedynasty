#!/usr/bin/env python3
"""
Complete ML Model Training with Full FanGraphs Integration

Incorporates:
- All FanGraphs grades (2022-2025)
- Upside potential tracking
- Physical attributes
- MiLB and MLB performance stats
- Statcast metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import asyncio
import logging
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import ElasticNet
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import xgboost as xgb
# import lightgbm as lgb  # Not installed, skip for now
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


class CompleteFanGraphsMLPipeline:
    """Complete ML pipeline with all FanGraphs data."""

    def __init__(self, target_metric: str = 'wrc_plus'):
        self.target_metric = target_metric
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.performance_metrics = {}

    async def load_complete_dataset(self) -> pd.DataFrame:
        """Load comprehensive dataset with all features."""

        query = """
            WITH player_stats AS (
                -- Get latest MiLB stats for each player
                SELECT
                    p.mlb_player_id,
                    p.player_name,
                    p.position,
                    p.draft_year,
                    p.draft_round,
                    p.current_age,
                    -- Aggregate MiLB performance
                    COUNT(DISTINCT mg.season) as seasons_played,
                    SUM(mg.games_played) as total_games,
                    AVG(mg.batting_avg) as avg_batting_avg,
                    AVG(mg.obp) as avg_obp,
                    AVG(mg.slg) as avg_slg,
                    AVG(mg.ops) as avg_ops,
                    SUM(mg.hits) as total_hits,
                    SUM(mg.doubles) as total_doubles,
                    SUM(mg.triples) as total_triples,
                    SUM(mg.home_runs) as total_home_runs,
                    SUM(mg.rbi) as total_rbi,
                    SUM(mg.stolen_bases) as total_stolen_bases,
                    AVG(mg.bb_rate) as avg_bb_rate,
                    AVG(mg.k_rate) as avg_k_rate,
                    AVG(mg.iso) as avg_iso,
                    AVG(mg.babip) as avg_babip,
                    AVG(mg.wrc_plus) as avg_wrc_plus,
                    MAX(mg.season) as latest_season,
                    STRING_AGG(DISTINCT mg.level, ',' ORDER BY mg.level) as levels_played
                FROM prospects p
                LEFT JOIN milb_game_logs mg ON p.mlb_player_id = mg.mlb_player_id
                WHERE mg.season >= 2022
                  AND mg.games_played > 0
                GROUP BY p.mlb_player_id, p.player_name, p.position, p.draft_year, p.draft_round, p.current_age
            ),
            fangraphs_latest AS (
                -- Get latest FanGraphs grades for each player
                SELECT DISTINCT ON (player_name)
                    player_name,
                    year,
                    fv,
                    hit_future,
                    game_power_future,
                    raw_power_future,
                    speed_future,
                    field_future,
                    fb_grade,
                    sl_grade,
                    cb_grade,
                    ch_grade,
                    cmd_grade,
                    has_upside,
                    frame,
                    athleticism,
                    levers,
                    arm_strength,
                    performance,
                    delivery,
                    top_100_rank,
                    org_rank
                FROM fangraphs_unified_grades
                WHERE year >= 2023
                ORDER BY player_name, year DESC
            ),
            statcast_metrics AS (
                -- Get Statcast metrics where available
                SELECT
                    player_id,
                    AVG(exit_velocity) as avg_exit_velo,
                    AVG(launch_angle) as avg_launch_angle,
                    MAX(exit_velocity) as max_exit_velo,
                    AVG(hard_hit_percent) as avg_hard_hit_pct,
                    AVG(barrel_percent) as avg_barrel_pct,
                    AVG(sweet_spot_percent) as avg_sweet_spot_pct,
                    AVG(sprint_speed) as avg_sprint_speed
                FROM milb_statcast_hitting
                WHERE season >= 2022
                GROUP BY player_id
            ),
            mlb_performance AS (
                -- Get MLB performance for those who made it
                SELECT
                    mlb_player_id,
                    AVG(wrc_plus) as mlb_wrc_plus,
                    AVG(war_162) as mlb_war_per_162,
                    COUNT(*) as mlb_seasons
                FROM mlb_season_stats
                WHERE season >= 2023
                GROUP BY mlb_player_id
            )
            SELECT
                ps.*,
                -- FanGraphs grades
                fg.fv,
                COALESCE(fg.hit_future, 45) as hit_future,
                COALESCE(fg.game_power_future, 45) as game_power_future,
                COALESCE(fg.raw_power_future, 45) as raw_power_future,
                COALESCE(fg.speed_future, 45) as speed_future,
                COALESCE(fg.field_future, 45) as field_future,
                COALESCE(fg.fb_grade, 45) as fb_grade,
                COALESCE(fg.sl_grade, 45) as sl_grade,
                COALESCE(fg.cb_grade, 45) as cb_grade,
                COALESCE(fg.ch_grade, 45) as ch_grade,
                COALESCE(fg.cmd_grade, 45) as cmd_grade,
                COALESCE(fg.has_upside, FALSE) as has_upside,
                -- Physical attributes
                COALESCE(fg.frame, 0) as frame,
                COALESCE(fg.athleticism, 0) as athleticism,
                CASE
                    WHEN fg.levers = 'Long' THEN 2
                    WHEN fg.levers = 'Med' THEN 1
                    WHEN fg.levers = 'Short' THEN -1
                    ELSE 0
                END as levers_score,
                COALESCE(fg.arm_strength, 45) as arm_strength,
                COALESCE(fg.performance, 0) as performance,
                COALESCE(fg.delivery, 0) as delivery,
                -- Rankings
                CASE WHEN fg.top_100_rank IS NOT NULL THEN 101 - fg.top_100_rank ELSE 0 END as top_100_score,
                COALESCE(fg.org_rank, 30) as org_rank,
                -- Statcast
                COALESCE(sc.avg_exit_velo, 85) as avg_exit_velo,
                COALESCE(sc.avg_launch_angle, 12) as avg_launch_angle,
                COALESCE(sc.max_exit_velo, 100) as max_exit_velo,
                COALESCE(sc.avg_hard_hit_pct, 30) as avg_hard_hit_pct,
                COALESCE(sc.avg_barrel_pct, 5) as avg_barrel_pct,
                COALESCE(sc.avg_sweet_spot_pct, 30) as avg_sweet_spot_pct,
                COALESCE(sc.avg_sprint_speed, 27) as avg_sprint_speed,
                -- Target variables
                COALESCE(mp.mlb_wrc_plus, ps.avg_wrc_plus) as target_wrc_plus,
                COALESCE(mp.mlb_war_per_162, 0) as target_war,
                CASE WHEN mp.mlb_player_id IS NOT NULL THEN 1 ELSE 0 END as made_mlb
            FROM player_stats ps
            LEFT JOIN fangraphs_latest fg
                ON LOWER(TRIM(ps.player_name)) = LOWER(TRIM(fg.player_name))
            LEFT JOIN statcast_metrics sc
                ON ps.mlb_player_id::varchar = sc.player_id::varchar
            LEFT JOIN mlb_performance mp
                ON ps.mlb_player_id = mp.mlb_player_id
            WHERE ps.total_games >= 50
              AND ps.current_age BETWEEN 18 AND 30
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} players with complete feature set")
        return df

    def create_engineered_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced engineered features."""

        # Tool grades composite scores
        df['hit_tool_composite'] = (df['hit_future'] * 0.4 +
                                    df['avg_batting_avg'] * 100 * 0.6)

        df['power_composite'] = (df['game_power_future'] * 0.3 +
                                 df['raw_power_future'] * 0.2 +
                                 df['avg_iso'] * 200 * 0.5)

        df['speed_athleticism'] = (df['speed_future'] * 0.4 +
                                   df['avg_sprint_speed'] * 2 * 0.3 +
                                   df['athleticism'] * 10 * 0.3)

        # Physical profile score
        df['physical_score'] = (df['frame'] * 15 +
                                df['athleticism'] * 15 +
                                df['levers_score'] * 10 +
                                df['arm_strength'])

        # Development indicators
        df['age_adjusted_performance'] = df['avg_wrc_plus'] * (1 + (23 - df['current_age']) * 0.05)

        df['upside_multiplier'] = np.where(df['has_upside'], 1.1, 1.0)

        # Grade consistency
        df['grade_variance'] = df[['hit_future', 'game_power_future', 'speed_future', 'field_future']].var(axis=1)

        # Plus tools count
        df['plus_tools'] = ((df['hit_future'] >= 60).astype(int) +
                           (df['game_power_future'] >= 60).astype(int) +
                           (df['speed_future'] >= 60).astype(int) +
                           (df['field_future'] >= 60).astype(int))

        # Statcast quality
        df['statcast_quality'] = (df['avg_exit_velo'] - 85) * 0.5 + \
                                 (df['avg_barrel_pct'] - 5) * 2 + \
                                 (df['avg_hard_hit_pct'] - 30) * 0.3

        # Level progression
        df['levels_count'] = df['levels_played'].str.count(',') + 1
        df['reached_aaa'] = df['levels_played'].str.contains('AAA').astype(int)
        df['reached_aa'] = df['levels_played'].str.contains('AA').astype(int)

        # Draft pedigree
        df['draft_pedigree'] = np.where(df['draft_round'] <= 3, 2,
                                        np.where(df['draft_round'] <= 10, 1, 0))

        return df

    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and target for modeling."""

        # Select feature columns
        feature_cols = [
            # Performance metrics
            'avg_batting_avg', 'avg_obp', 'avg_slg', 'avg_ops',
            'avg_bb_rate', 'avg_k_rate', 'avg_iso', 'avg_babip', 'avg_wrc_plus',
            # FanGraphs grades
            'fv', 'hit_future', 'game_power_future', 'raw_power_future',
            'speed_future', 'field_future',
            'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade',
            # Physical attributes
            'frame', 'athleticism', 'levers_score', 'arm_strength',
            'performance', 'delivery',
            # Upside and rankings
            'has_upside', 'top_100_score', 'org_rank',
            # Statcast
            'avg_exit_velo', 'avg_launch_angle', 'max_exit_velo',
            'avg_hard_hit_pct', 'avg_barrel_pct', 'avg_sweet_spot_pct', 'avg_sprint_speed',
            # Engineered features
            'hit_tool_composite', 'power_composite', 'speed_athleticism',
            'physical_score', 'age_adjusted_performance', 'upside_multiplier',
            'grade_variance', 'plus_tools', 'statcast_quality',
            'levels_count', 'reached_aaa', 'reached_aa', 'draft_pedigree',
            # Basic info
            'current_age', 'total_games', 'seasons_played'
        ]

        # Convert boolean to int
        df['has_upside'] = df['has_upside'].astype(int)

        # Remove any missing features
        available_features = [col for col in feature_cols if col in df.columns]
        X = df[available_features].fillna(0)

        # Target variable
        y = df[f'target_{self.target_metric}'].fillna(df[f'avg_{self.target_metric}'])

        # Remove infinite values
        X = X.replace([np.inf, -np.inf], 0)
        y = y.replace([np.inf, -np.inf], 0)

        return X, y

    def train_models(self, X: pd.DataFrame, y: pd.Series):
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

        # Train multiple models
        models = {
            'xgboost': xgb.XGBRegressor(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0
            ),
            # 'lightgbm': lgb.LGBMRegressor(  # Skip if not installed
            #     n_estimators=300,
            #     max_depth=6,
            #     learning_rate=0.05,
            #     subsample=0.8,
            #     colsample_bytree=0.8,
            #     random_state=42,
            #     verbosity=-1
            # ),
            'random_forest': RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            ),
            'gradient_boost': GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
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

            self.performance_metrics[name] = {
                'r2': r2,
                'rmse': rmse,
                'mae': mae
            }

            logger.info(f"{name} - R²: {r2:.4f}, RMSE: {rmse:.2f}, MAE: {mae:.2f}")

            # Feature importance for tree models
            if hasattr(model, 'feature_importances_'):
                importance = pd.DataFrame({
                    'feature': X.columns,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
                self.feature_importance[name] = importance

        # Create ensemble prediction
        self.create_ensemble_model(X_train_scaled, y_train, X_test_scaled, y_test)

    def create_ensemble_model(self, X_train, y_train, X_test, y_test):
        """Create weighted ensemble of all models."""

        # Get predictions from all models
        predictions = {}
        for name, model in self.models.items():
            predictions[name] = model.predict(X_test)

        # Weight by R² scores
        weights = {}
        total_r2 = sum([metrics['r2'] for metrics in self.performance_metrics.values()])
        for name, metrics in self.performance_metrics.items():
            weights[name] = metrics['r2'] / total_r2

        # Ensemble prediction
        ensemble_pred = np.zeros(len(y_test))
        for name, pred in predictions.items():
            ensemble_pred += pred * weights[name]

        # Evaluate ensemble
        r2 = r2_score(y_test, ensemble_pred)
        rmse = np.sqrt(mean_squared_error(y_test, ensemble_pred))
        mae = mean_absolute_error(y_test, ensemble_pred)

        self.performance_metrics['ensemble'] = {
            'r2': r2,
            'rmse': rmse,
            'mae': mae,
            'weights': weights
        }

        logger.info(f"Ensemble - R²: {r2:.4f}, RMSE: {rmse:.2f}, MAE: {mae:.2f}")

    def save_models(self):
        """Save trained models and scalers."""

        # Save individual models
        for name, model in self.models.items():
            joblib.dump(model, f'complete_fangraphs_{name}_model.pkl')

        # Save scalers
        joblib.dump(self.scalers, 'complete_fangraphs_scalers.pkl')

        # Save performance metrics
        pd.DataFrame(self.performance_metrics).to_csv('complete_fangraphs_model_performance.csv')

        # Save feature importance
        for name, importance in self.feature_importance.items():
            importance.to_csv(f'complete_fangraphs_feature_importance_{name}.csv', index=False)

        logger.info("Models saved successfully")

    async def run_complete_pipeline(self):
        """Run the complete ML pipeline."""

        logger.info("Starting Complete FanGraphs ML Pipeline...")

        # Load data
        logger.info("Loading comprehensive dataset...")
        df = await self.load_complete_dataset()

        # Engineer features
        logger.info("Engineering advanced features...")
        df = self.create_engineered_features(df)

        # Prepare for modeling
        logger.info("Preparing features...")
        X, y = self.prepare_features(df)

        logger.info(f"Feature set: {X.shape[1]} features, {X.shape[0]} samples")

        # Train models
        logger.info("Training models...")
        self.train_models(X, y)

        # Save everything
        logger.info("Saving models and results...")
        self.save_models()

        # Print summary
        print("\n" + "="*80)
        print("MODEL TRAINING COMPLETE")
        print("="*80)
        for name, metrics in self.performance_metrics.items():
            if name == 'ensemble':
                print(f"\n{name.upper()} (FINAL MODEL):")
                print(f"  R² Score: {metrics['r2']:.4f}")
                print(f"  RMSE: {metrics['rmse']:.2f}")
                print(f"  MAE: {metrics['mae']:.2f}")
                if 'weights' in metrics:
                    print("  Weights:")
                    for model_name, weight in metrics['weights'].items():
                        print(f"    {model_name}: {weight:.3f}")
            else:
                print(f"\n{name}:")
                print(f"  R² Score: {metrics['r2']:.4f}")
                print(f"  RMSE: {metrics['rmse']:.2f}")
                print(f"  MAE: {metrics['mae']:.2f}")

        # Show top features
        if 'xgboost' in self.feature_importance:
            print("\n" + "="*80)
            print("TOP 15 MOST IMPORTANT FEATURES (XGBoost)")
            print("="*80)
            print(self.feature_importance['xgboost'].head(15))

        return self


async def main():
    """Main execution."""

    pipeline = CompleteFanGraphsMLPipeline(target_metric='wrc_plus')
    await pipeline.run_complete_pipeline()


if __name__ == "__main__":
    asyncio.run(main())