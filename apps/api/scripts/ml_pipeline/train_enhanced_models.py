#!/usr/bin/env python3
"""
Enhanced Model Training with Full Historical Data

Leverages 2021-2024 MiLB data and 2020-2025 MLB data for improved predictions.
Includes cross-validation and temporal validation.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import pickle
import asyncio
from datetime import datetime
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine
from sqlalchemy import text

from train_projection_model import ProjectionModelTrainer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedModelTrainer(ProjectionModelTrainer):
    """Enhanced trainer using full historical dataset."""

    async def analyze_data_coverage(self) -> Dict:
        """Analyze data coverage across seasons."""

        logger.info("Analyzing data coverage...")

        queries = {
            'milb_coverage': """
                SELECT
                    season,
                    COUNT(DISTINCT mlb_player_id) as players,
                    COUNT(*) as games,
                    SUM(plate_appearances) as total_pa,
                    AVG(plate_appearances) as avg_pa
                FROM milb_game_logs
                WHERE season BETWEEN 2021 AND 2024
                AND plate_appearances > 0
                GROUP BY season
                ORDER BY season
            """,

            'mlb_coverage': """
                SELECT
                    season,
                    COUNT(DISTINCT mlb_player_id) as players,
                    COUNT(*) as games,
                    AVG(wrc_plus) as avg_wrc_plus
                FROM mlb_game_logs
                WHERE season BETWEEN 2020 AND 2025
                GROUP BY season
                ORDER BY season
            """,

            'transitions': """
                WITH milb_years AS (
                    SELECT
                        mlb_player_id,
                        MAX(season) as last_milb_season
                    FROM milb_game_logs
                    WHERE season BETWEEN 2021 AND 2024
                    GROUP BY mlb_player_id
                ),
                mlb_years AS (
                    SELECT
                        mlb_player_id,
                        MIN(season) as first_mlb_season
                    FROM mlb_game_logs
                    WHERE season BETWEEN 2020 AND 2025
                    GROUP BY mlb_player_id
                )
                SELECT
                    mi.last_milb_season as milb_season,
                    ml.first_mlb_season as mlb_season,
                    COUNT(*) as transition_count
                FROM milb_years mi
                INNER JOIN mlb_years ml ON mi.mlb_player_id = ml.mlb_player_id
                WHERE ml.first_mlb_season > mi.last_milb_season
                GROUP BY mi.last_milb_season, ml.first_mlb_season
                ORDER BY mi.last_milb_season, ml.first_mlb_season
            """
        }

        results = {}
        async with engine.begin() as conn:
            for name, query in queries.items():
                result = await conn.execute(text(query))
                results[name] = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Print summary
        print("\n" + "="*80)
        print("DATA COVERAGE ANALYSIS")
        print("="*80)

        print("\nMiLB Coverage (2021-2024):")
        print(results['milb_coverage'].to_string(index=False))

        print("\nMLB Coverage (2020-2025):")
        print(results['mlb_coverage'].to_string(index=False))

        print("\nMiLB->MLB Transitions by Year:")
        print(results['transitions'].to_string(index=False))

        return results

    async def prepare_temporal_splits(
        self,
        min_pa: int = 100
    ) -> Dict[str, Tuple[pd.DataFrame, pd.Series]]:
        """Prepare temporal train/validation/test splits."""

        logger.info("Creating temporal data splits...")

        splits = {
            'train': {
                'milb_seasons': [2021, 2022, 2023],
                'mlb_seasons': [2022, 2023, 2024]
            },
            'validation': {
                'milb_seasons': [2024],
                'mlb_seasons': [2024, 2025]
            },
            'test': {
                'milb_seasons': [2025],
                'mlb_seasons': [2025]
            }
        }

        datasets = {}

        for split_name, seasons in splits.items():
            logger.info(f"Preparing {split_name} split...")

            query = """
                WITH milb_stats AS (
                    SELECT
                        mlb_player_id,
                        AVG(batting_avg) as avg_ba,
                        AVG(obp) as avg_obp,
                        AVG(slg) as avg_slg,
                        AVG(ops) as avg_ops,
                        SUM(home_runs) as total_hr,
                        SUM(stolen_bases) as total_sb,
                        SUM(walks) as total_bb,
                        SUM(strikeouts) as total_so,
                        SUM(plate_appearances) as total_pa,
                        MAX(level) as highest_level
                    FROM milb_game_logs
                    WHERE season IN :milb_seasons
                    AND plate_appearances > 0
                    GROUP BY mlb_player_id
                    HAVING SUM(plate_appearances) >= :min_pa
                ),
                mlb_targets AS (
                    SELECT
                        mlb_player_id,
                        AVG(wrc_plus) as target_wrc_plus,
                        AVG(woba) as target_woba
                    FROM mlb_game_logs
                    WHERE season IN :mlb_seasons
                    AND mlb_player_id IN (SELECT mlb_player_id FROM milb_stats)
                    GROUP BY mlb_player_id
                )
                SELECT
                    ms.*,
                    mt.target_wrc_plus,
                    mt.target_woba
                FROM milb_stats ms
                INNER JOIN mlb_targets mt ON ms.mlb_player_id = mt.mlb_player_id
                WHERE mt.target_wrc_plus IS NOT NULL
            """

            async with engine.begin() as conn:
                result = await conn.execute(
                    text(query),
                    {
                        'milb_seasons': tuple(seasons['milb_seasons']),
                        'mlb_seasons': tuple(seasons['mlb_seasons']),
                        'min_pa': min_pa
                    }
                )
                data = pd.DataFrame(result.fetchall(), columns=result.keys())

            if len(data) > 0:
                # Prepare features
                feature_cols = [
                    'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops',
                    'total_hr', 'total_sb', 'total_bb', 'total_so', 'total_pa'
                ]

                # Add rate stats
                data['hr_rate'] = data['total_hr'] / data['total_pa']
                data['bb_rate'] = data['total_bb'] / data['total_pa']
                data['so_rate'] = data['total_so'] / data['total_pa']
                data['sb_rate'] = data['total_sb'] / data['total_pa']

                feature_cols.extend(['hr_rate', 'bb_rate', 'so_rate', 'sb_rate'])

                # Encode level
                level_mapping = {
                    'Rookie': 1, 'Rookie+': 2, 'A': 3, 'A+': 4,
                    'AA': 5, 'AAA': 6, 'MLB': 7
                }
                data['level_numeric'] = data['highest_level'].map(
                    lambda x: level_mapping.get(x, 3)
                )
                feature_cols.append('level_numeric')

                X = data[feature_cols].fillna(0)
                y_wrc = data['target_wrc_plus']
                y_woba = data['target_woba']

                datasets[split_name] = {
                    'X': X,
                    'y_wrc': y_wrc,
                    'y_woba': y_woba,
                    'n_samples': len(data),
                    'player_ids': data['mlb_player_id'].values
                }

                logger.info(f"{split_name}: {len(data)} samples")

        return datasets

    async def train_with_temporal_validation(self) -> Dict:
        """Train models with temporal validation."""

        # Get temporal splits
        datasets = await self.prepare_temporal_splits()

        if not all(k in datasets for k in ['train', 'validation', 'test']):
            logger.error("Insufficient data for temporal validation")
            return {}

        logger.info("\nTemporal Split Sizes:")
        for split in ['train', 'validation', 'test']:
            if split in datasets:
                logger.info(f"  {split}: {datasets[split]['n_samples']} samples")

        # Train models on training set
        logger.info("\nTraining models on temporal training set...")

        X_train = datasets['train']['X']
        y_train = datasets['train']['y_wrc']
        X_val = datasets['validation']['X']
        y_val = datasets['validation']['y_wrc']
        X_test = datasets['test']['X']
        y_test = datasets['test']['y_wrc']

        # Train ensemble
        xgb_model = self.train_xgboost(X_train, y_train, X_val, y_val)
        rf_model = self.train_random_forest(X_train, y_train, X_val, y_val)
        nn_model = self.train_neural_network(X_train, y_train, X_val, y_val)

        ensemble = self.create_ensemble(
            xgb_model, rf_model, nn_model,
            X_train, y_train, X_val, y_val
        )

        # Test on held-out future data
        logger.info("\n" + "="*50)
        logger.info("TEMPORAL TEST SET EVALUATION (2024 MiLB -> 2025 MLB)")
        test_predictions = self.predict_ensemble(ensemble, X_test)

        test_mae = mean_absolute_error(y_test, test_predictions)
        test_r2 = r2_score(y_test, test_predictions)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_predictions))

        logger.info(f"Test MAE: {test_mae:.2f}")
        logger.info(f"Test R2: {test_r2:.3f}")
        logger.info(f"Test RMSE: {test_rmse:.2f}")

        # Analyze prediction distribution
        errors = test_predictions - y_test
        logger.info(f"\nError Distribution:")
        logger.info(f"  Median Error: {np.median(errors):.1f}")
        logger.info(f"  90th Percentile Error: {np.percentile(np.abs(errors), 90):.1f}")
        logger.info(f"  Within ±10 wRC+: {(np.abs(errors) <= 10).mean():.1%}")
        logger.info(f"  Within ±20 wRC+: {(np.abs(errors) <= 20).mean():.1%}")

        return {
            'ensemble': ensemble,
            'datasets': datasets,
            'test_performance': {
                'mae': test_mae,
                'r2': test_r2,
                'rmse': test_rmse,
                'median_error': np.median(errors),
                'within_10': (np.abs(errors) <= 10).mean(),
                'within_20': (np.abs(errors) <= 20).mean()
            }
        }

    async def analyze_feature_importance(self, model_package: Dict):
        """Analyze which features are most predictive."""

        logger.info("\nAnalyzing feature importance...")

        # Get feature importances from RF model
        rf_model = model_package['ensemble']['models'][1][1]
        feature_names = model_package['datasets']['train']['X'].columns

        importances = pd.DataFrame({
            'feature': feature_names,
            'importance': rf_model.feature_importances_
        }).sort_values('importance', ascending=False)

        print("\n" + "="*50)
        print("TOP 10 MOST IMPORTANT FEATURES")
        print("="*50)
        for i, row in importances.head(10).iterrows():
            print(f"{row['feature']:20s} {row['importance']:.4f}")

        return importances


async def main():
    """Run enhanced training pipeline."""

    trainer = EnhancedModelTrainer(target='wrc_plus')

    # Analyze data coverage
    print("\nAnalyzing data coverage across all seasons...")
    coverage = await trainer.analyze_data_coverage()

    # Train with temporal validation
    print("\n" + "="*80)
    print("TRAINING MODELS WITH TEMPORAL VALIDATION")
    print("="*80)
    print("Training on: 2021-2023 MiLB -> 2022-2024 MLB")
    print("Validating on: 2024 MiLB -> 2024-2025 MLB")
    print("Testing on: 2025 MiLB -> 2025 MLB")
    print("="*80)

    model_package = await trainer.train_with_temporal_validation()

    if model_package:
        # Analyze features
        await trainer.analyze_feature_importance(model_package)

        # Save enhanced models
        save_path = 'enhanced_wrc_projection_model.pkl'
        with open(save_path, 'wb') as f:
            pickle.dump(model_package, f)
        logger.info(f"\nEnhanced models saved to {save_path}")

        # Summary
        print("\n" + "="*80)
        print("TRAINING COMPLETE")
        print("="*80)
        print(f"Training samples: {model_package['datasets']['train']['n_samples']}")
        print(f"Validation samples: {model_package['datasets']['validation']['n_samples']}")
        print(f"Test samples: {model_package['datasets']['test']['n_samples']}")
        print(f"\nTest Performance (2024 -> 2025):")
        print(f"  MAE: {model_package['test_performance']['mae']:.1f} wRC+")
        print(f"  R2: {model_package['test_performance']['r2']:.3f}")
        print(f"  Within ±20 wRC+: {model_package['test_performance']['within_20']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())