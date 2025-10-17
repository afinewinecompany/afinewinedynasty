"""
Unified ML Model Training: Predict MLB Success from MiLB Stats + FanGraphs Grades

This script implements the ML API Reference specifications:
- Binary classification: MLB success probability (0.0 - 1.0)
- Features: MiLB stats, FanGraphs scouting grades, demographics
- Target: MLB success (≥500 PA for hitters, ≥200 IP for pitchers, within 5 years)
- Model: XGBoost with SHAP explainability
- Performance targets: AUC ≥ 0.85, F1 ≥ 0.78, Accuracy ≥ 82%

Usage:
    python scripts/train_unified_ml_predictor.py
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

import pandas as pd
import numpy as np
import joblib

from sqlalchemy import text
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    brier_score_loss,
    confusion_matrix,
    classification_report
)

import xgboost as xgb
import shap

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedMLPredictor:
    """Train unified XGBoost models for MLB success prediction."""

    def __init__(self):
        self.hitter_model = None
        self.pitcher_model = None
        self.hitter_explainer = None
        self.pitcher_explainer = None
        self.scaler = StandardScaler()
        self.model_version = f"v1.0.0_{datetime.now().strftime('%Y%m%d')}"

    async def load_hitter_training_data(self) -> pd.DataFrame:
        """
        Load comprehensive hitter training data:
        - MiLB game log stats (features)
        - FanGraphs prospect grades (features)
        - MLB career outcomes (labels)
        """
        logger.info("Loading hitter training data...")

        async with engine.begin() as conn:
            query = text('''
                WITH milb_stats AS (
                    -- Aggregate MiLB performance by player
                    SELECT
                        mlb_player_id,
                        COUNT(DISTINCT season) as milb_seasons,
                        SUM(plate_appearances) as total_milb_pa,
                        SUM(at_bats) as total_milb_ab,
                        SUM(hits)::float / NULLIF(SUM(at_bats), 0) as milb_avg,
                        SUM(home_runs)::float / NULLIF(SUM(plate_appearances), 0) as milb_hr_rate,
                        SUM(walks)::float / NULLIF(SUM(plate_appearances), 0) as milb_bb_rate,
                        SUM(strikeouts)::float / NULLIF(SUM(plate_appearances), 0) as milb_k_rate,
                        (SUM(hits) + SUM(walks))::float / NULLIF(SUM(plate_appearances), 0) as milb_obp,
                        (SUM(doubles) * 2 + SUM(triples) * 3 + SUM(home_runs) * 4 + SUM(hits))::float
                            / NULLIF(SUM(at_bats), 0) as milb_slg,
                        (SUM(doubles) + SUM(triples) + SUM(home_runs))::float / NULLIF(SUM(at_bats), 0) as milb_iso,
                        SUM(stolen_bases)::float / NULLIF(SUM(plate_appearances), 0) as milb_sb_rate,
                        MAX(
                            CASE level
                                WHEN 'AAA' THEN 4
                                WHEN 'AA' THEN 3
                                WHEN 'A+' THEN 2
                                WHEN 'A' THEN 1
                                ELSE 0
                            END
                        ) as highest_milb_level
                    FROM milb_game_logs
                    WHERE plate_appearances > 0
                      AND mlb_player_id IS NOT NULL
                    GROUP BY mlb_player_id
                    HAVING SUM(plate_appearances) >= 100  -- Minimum sample size
                ),
                mlb_outcomes AS (
                    -- Calculate MLB career outcomes for labels
                    SELECT
                        mlb_player_id,
                        SUM(plate_appearances) as mlb_total_pa,
                        SUM(at_bats) as mlb_total_ab,
                        SUM(hits)::float / NULLIF(SUM(at_bats), 0) as mlb_avg,
                        (SUM(hits) + SUM(walks))::float / NULLIF(SUM(plate_appearances), 0) as mlb_obp,
                        (SUM(doubles) * 2 + SUM(triples) * 3 + SUM(home_runs) * 4 + SUM(hits))::float
                            / NULLIF(SUM(at_bats), 0) as mlb_slg,
                        COUNT(DISTINCT season) as mlb_seasons,
                        -- Success label: ≥500 PA in MLB career
                        CASE WHEN SUM(plate_appearances) >= 500 THEN 1 ELSE 0 END as mlb_success
                    FROM mlb_game_logs
                    WHERE plate_appearances > 0
                      AND mlb_player_id IS NOT NULL
                    GROUP BY mlb_player_id
                ),
                prospect_info AS (
                    -- Get prospect demographics and linkage
                    SELECT
                        mlb_player_id,
                        fg_player_id,
                        age,
                        position,
                        organization,
                        height_inches,
                        weight_lbs,
                        draft_round
                    FROM prospects
                    WHERE mlb_player_id IS NOT NULL
                )
                SELECT
                    milb.*,
                    mlb.mlb_total_pa,
                    mlb.mlb_avg,
                    mlb.mlb_obp,
                    mlb.mlb_slg,
                    mlb.mlb_seasons,
                    mlb.mlb_success,
                    p.age,
                    p.position,
                    p.height_inches,
                    p.weight_lbs,
                    p.draft_round
                FROM milb_stats milb
                INNER JOIN mlb_outcomes mlb ON mlb.mlb_player_id = milb.mlb_player_id
                LEFT JOIN prospect_info p ON p.mlb_player_id = milb.mlb_player_id
                WHERE milb.total_milb_pa >= 100
                  AND mlb.mlb_total_pa >= 50  -- Must have made it to MLB
            ''')

            result = await conn.execute(query)
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} hitter training samples")
        logger.info(f"  Success rate: {df['mlb_success'].mean():.1%}")
        logger.info(f"  MiLB PA range: {df['total_milb_pa'].min()}-{df['total_milb_pa'].max()}")

        return df

    async def load_pitcher_training_data(self) -> pd.DataFrame:
        """
        Load comprehensive pitcher training data:
        - MiLB pitching stats (features)
        - FanGraphs grades (features)
        - MLB career outcomes (labels)
        """
        logger.info("Loading pitcher training data...")

        async with engine.begin() as conn:
            query = text('''
                WITH milb_stats AS (
                    -- Aggregate MiLB pitching performance
                    SELECT
                        mlb_player_id,
                        COUNT(DISTINCT season) as milb_seasons,
                        SUM(innings_pitched) as total_milb_ip,
                        SUM(earned_runs)::float / NULLIF(SUM(innings_pitched) / 9, 0) as milb_era,
                        (SUM(hits) + SUM(walks))::float / NULLIF(SUM(innings_pitched), 0) as milb_whip,
                        SUM(strikeouts)::float / NULLIF(SUM(innings_pitched) / 9, 0) as milb_k9,
                        SUM(walks)::float / NULLIF(SUM(innings_pitched) / 9, 0) as milb_bb9,
                        SUM(strikeouts)::float / NULLIF(SUM(walks), 0) as milb_k_bb_ratio,
                        SUM(home_runs)::float / NULLIF(SUM(innings_pitched) / 9, 0) as milb_hr9,
                        MAX(
                            CASE level
                                WHEN 'AAA' THEN 4
                                WHEN 'AA' THEN 3
                                WHEN 'A+' THEN 2
                                WHEN 'A' THEN 1
                                ELSE 0
                            END
                        ) as highest_milb_level
                    FROM milb_game_logs
                    WHERE innings_pitched > 0
                      AND mlb_player_id IS NOT NULL
                    GROUP BY mlb_player_id
                    HAVING SUM(innings_pitched) >= 50  -- Minimum sample size
                ),
                mlb_outcomes AS (
                    -- Calculate MLB pitcher career outcomes
                    SELECT
                        mlb_player_id,
                        SUM(innings_pitched) as mlb_total_ip,
                        SUM(earned_runs)::float / NULLIF(SUM(innings_pitched) / 9, 0) as mlb_era,
                        (SUM(hits) + SUM(walks))::float / NULLIF(SUM(innings_pitched), 0) as mlb_whip,
                        SUM(strikeouts)::float / NULLIF(SUM(innings_pitched) / 9, 0) as mlb_k9,
                        COUNT(DISTINCT season) as mlb_seasons,
                        -- Success label: ≥200 IP in MLB career
                        CASE WHEN SUM(innings_pitched) >= 200 THEN 1 ELSE 0 END as mlb_success
                    FROM mlb_game_logs
                    WHERE innings_pitched > 0
                      AND mlb_player_id IS NOT NULL
                    GROUP BY mlb_player_id
                ),
                fg_grades AS (
                    -- FanGraphs pitcher grades
                    SELECT
                        fg_player_id,
                        fv,
                        fb_grade,
                        sl_grade,
                        cb_grade,
                        ch_grade,
                        cmd_grade,
                        sits_velo,
                        tops_velo
                    FROM fangraphs_prospect_grades
                    WHERE fb_grade IS NOT NULL  -- Pitcher grades
                ),
                prospect_info AS (
                    SELECT
                        mlb_player_id,
                        fg_player_id,
                        age,
                        position,
                        organization,
                        height_inches,
                        weight_lbs,
                        draft_round
                    FROM prospects
                    WHERE mlb_player_id IS NOT NULL
                )
                SELECT
                    milb.*,
                    mlb.mlb_total_ip,
                    mlb.mlb_era,
                    mlb.mlb_whip,
                    mlb.mlb_k9,
                    mlb.mlb_seasons,
                    mlb.mlb_success,
                    fg.fv,
                    fg.fb_grade,
                    fg.sl_grade,
                    fg.cb_grade,
                    fg.ch_grade,
                    fg.cmd_grade,
                    fg.sits_velo,
                    fg.tops_velo,
                    p.age,
                    p.position,
                    p.height_inches,
                    p.weight_lbs,
                    p.draft_round
                FROM milb_stats milb
                INNER JOIN mlb_outcomes mlb ON mlb.mlb_player_id = milb.mlb_player_id
                LEFT JOIN prospect_info p ON p.mlb_player_id = milb.mlb_player_id
                LEFT JOIN fg_grades fg ON fg.fg_player_id = p.fg_player_id
                WHERE milb.total_milb_ip >= 50
                  AND mlb.mlb_total_ip >= 20  -- Must have made it to MLB
            ''')

            result = await conn.execute(query)
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} pitcher training samples")
        logger.info(f"  Success rate: {df['mlb_success'].mean():.1%}")
        logger.info(f"  MiLB IP range: {df['total_milb_ip'].min():.1f}-{df['total_milb_ip'].max():.1f}")

        return df

    def engineer_hitter_features(self, df: pd.DataFrame) -> tuple:
        """Build feature matrix for hitters."""
        features = []
        feature_names = []

        # MiLB performance features
        for col in ['milb_avg', 'milb_obp', 'milb_slg', 'milb_iso', 'milb_hr_rate',
                    'milb_bb_rate', 'milb_k_rate', 'milb_sb_rate']:
            features.append(df[col].fillna(0))
            feature_names.append(col)

        # MiLB experience
        features.append(df['milb_seasons'].fillna(0))
        feature_names.append('milb_seasons')

        features.append(np.log1p(df['total_milb_pa'].fillna(0)))  # Log transform PA
        feature_names.append('log_milb_pa')

        features.append(df['highest_milb_level'].fillna(0))
        feature_names.append('highest_milb_level')

        # Demographics
        features.append(df['age'].fillna(21))
        feature_names.append('age')

        features.append((df['age'].fillna(21)) ** 2)
        feature_names.append('age_squared')

        features.append(df['height_inches'].fillna(72))
        feature_names.append('height_inches')

        features.append(df['weight_lbs'].fillna(190))
        feature_names.append('weight_lbs')

        features.append(df['draft_round'].fillna(20))  # 20 = undrafted
        feature_names.append('draft_round')

        # Derived features
        features.append((df['milb_obp'] + df['milb_slg']).fillna(0))
        feature_names.append('milb_ops')

        features.append(df['highest_milb_level'] * df['milb_avg'])
        feature_names.append('level_x_avg')

        X = np.column_stack(features)
        return X, feature_names

    def engineer_pitcher_features(self, df: pd.DataFrame) -> tuple:
        """Build feature matrix for pitchers."""
        features = []
        feature_names = []

        # MiLB performance features
        for col in ['milb_era', 'milb_whip', 'milb_k9', 'milb_bb9', 'milb_k_bb_ratio', 'milb_hr9']:
            features.append(df[col].fillna(df[col].median() if len(df) > 0 else 0))
            feature_names.append(col)

        # FanGraphs grades
        for col in ['fv', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade']:
            features.append(df[col].fillna(40))  # 40 = below average
            feature_names.append(col)

        features.append(df['sits_velo'].fillna(92))
        feature_names.append('sits_velo')

        features.append(df['tops_velo'].fillna(94))
        feature_names.append('tops_velo')

        # MiLB experience
        features.append(df['milb_seasons'].fillna(0))
        feature_names.append('milb_seasons')

        features.append(np.log1p(df['total_milb_ip'].fillna(0)))
        feature_names.append('log_milb_ip')

        features.append(df['highest_milb_level'].fillna(0))
        feature_names.append('highest_milb_level')

        # Demographics
        features.append(df['age'].fillna(21))
        feature_names.append('age')

        features.append((df['age'].fillna(21)) ** 2)
        feature_names.append('age_squared')

        features.append(df['height_inches'].fillna(74))
        feature_names.append('height_inches')

        features.append(df['weight_lbs'].fillna(200))
        feature_names.append('weight_lbs')

        features.append(df['draft_round'].fillna(20))
        feature_names.append('draft_round')

        # Derived features
        features.append((df['fb_grade'] + df['sl_grade'] + df['cb_grade'] + df['ch_grade']) / 4)
        feature_names.append('avg_pitch_grade')

        features.append(df['cmd_grade'] * df['milb_k9'] / 100)
        feature_names.append('cmd_x_k9')

        X = np.column_stack(features)
        return X, feature_names

    def train_xgboost_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list,
        model_type: str
    ) -> tuple:
        """Train XGBoost classifier with optimal hyperparameters."""
        logger.info(f"\nTraining {model_type} XGBoost Model")
        logger.info("=" * 80)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"Training samples: {len(X_train)}")
        logger.info(f"Test samples: {len(X_test)}")
        logger.info(f"Positive class: {y_train.sum()} ({y_train.mean():.1%})")

        # Train XGBoost
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='auc'
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # Predictions
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)

        # Evaluate
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1': f1_score(y_test, y_pred, zero_division=0),
            'auc_roc': roc_auc_score(y_test, y_pred_proba),
            'brier': brier_score_loss(y_test, y_pred_proba)
        }

        logger.info("\nModel Performance:")
        logger.info(f"  Accuracy:  {metrics['accuracy']:.3f} (target: ≥0.82)")
        logger.info(f"  Precision: {metrics['precision']:.3f} (target: ≥0.80)")
        logger.info(f"  Recall:    {metrics['recall']:.3f} (target: ≥0.75)")
        logger.info(f"  F1 Score:  {metrics['f1']:.3f} (target: ≥0.78)")
        logger.info(f"  AUC-ROC:   {metrics['auc_roc']:.3f} (target: ≥0.85)")
        logger.info(f"  Brier:     {metrics['brier']:.3f} (target: <0.15)")

        # Feature importance
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info("\nTop 10 Most Important Features:")
        for idx, row in importance_df.head(10).iterrows():
            logger.info(f"  {row['feature']:<25} {row['importance']:.4f}")

        # Create SHAP explainer
        explainer = shap.TreeExplainer(model)

        return model, explainer, metrics, importance_df, (X_test, y_test, y_pred_proba)

    async def train_all_models(self):
        """Train both hitter and pitcher models."""
        logger.info("\n" + "=" * 80)
        logger.info("UNIFIED ML MODEL TRAINING")
        logger.info("=" * 80)
        logger.info(f"Model Version: {self.model_version}")
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Train hitter model
        try:
            hitter_df = await self.load_hitter_training_data()
            if len(hitter_df) >= 50:
                X_hit, hit_features = self.engineer_hitter_features(hitter_df)
                y_hit = hitter_df['mlb_success'].values

                self.hitter_model, self.hitter_explainer, hit_metrics, hit_importance, hit_test_data = self.train_xgboost_model(
                    X_hit, y_hit, hit_features, "HITTER"
                )
            else:
                logger.warning(f"Insufficient hitter data: {len(hitter_df)} samples (need ≥50)")
        except Exception as e:
            logger.error(f"Hitter model training failed: {str(e)}")

        # Train pitcher model
        try:
            pitcher_df = await self.load_pitcher_training_data()
            if len(pitcher_df) >= 50:
                X_pit, pit_features = self.engineer_pitcher_features(pitcher_df)
                y_pit = pitcher_df['mlb_success'].values

                self.pitcher_model, self.pitcher_explainer, pit_metrics, pit_importance, pit_test_data = self.train_xgboost_model(
                    X_pit, y_pit, pit_features, "PITCHER"
                )
            else:
                logger.warning(f"Insufficient pitcher data: {len(pitcher_df)} samples (need ≥50)")
        except Exception as e:
            logger.error(f"Pitcher model training failed: {str(e)}")

    def save_models(self, output_dir: str = 'models'):
        """Save trained models and metadata."""
        os.makedirs(output_dir, exist_ok=True)

        if self.hitter_model:
            hitter_path = os.path.join(output_dir, f'hitter_success_model_{self.model_version}.pkl')
            joblib.dump({
                'model': self.hitter_model,
                'explainer': self.hitter_explainer,
                'model_version': self.model_version,
                'training_date': datetime.now().isoformat(),
                'model_type': 'hitter_success_classifier'
            }, hitter_path)
            logger.info(f"\nSaved hitter model: {hitter_path}")

        if self.pitcher_model:
            pitcher_path = os.path.join(output_dir, f'pitcher_success_model_{self.model_version}.pkl')
            joblib.dump({
                'model': self.pitcher_model,
                'explainer': self.pitcher_explainer,
                'model_version': self.model_version,
                'training_date': datetime.now().isoformat(),
                'model_type': 'pitcher_success_classifier'
            }, pitcher_path)
            logger.info(f"Saved pitcher model: {pitcher_path}")

        logger.info("\n" + "=" * 80)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 80)


async def main():
    """Main training pipeline."""
    predictor = UnifiedMLPredictor()
    await predictor.train_all_models()
    predictor.save_models()


if __name__ == "__main__":
    asyncio.run(main())
