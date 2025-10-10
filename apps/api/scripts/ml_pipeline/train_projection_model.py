#!/usr/bin/env python3
"""
Train ML Models for MiLB → MLB Projection

Trains ensemble models (XGBoost, Random Forest, Neural Network) to predict:
- wRC+ (primary target)
- wOBA (secondary target)
- Peak wRC+ (age-adjusted ceiling)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import pickle
import asyncio
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import VotingRegressor
import logging
import sys
import os
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.database import engine
from sqlalchemy import text

# Import our custom modules
from calculate_advanced_metrics import AdvancedMetricsCalculator
from age_curve_model import AgeAdjustedProjector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to use unified Fangraphs features if available
try:
    from feature_engineering_unified_fangraphs import UnifiedFangraphsFeatureEngineer as FeatureEngineer
    logger.info("Using unified Fangraphs feature engineering (2022-2025 data)")
except ImportError:
    try:
        from feature_engineering_with_fangraphs import FangraphsFeatureEngineer as FeatureEngineer
        logger.info("Using Fangraphs-enhanced feature engineering")
    except ImportError:
        from feature_engineering import FeatureEngineer
        logger.warning("Fangraphs integration not available, using base features")


class ProjectionModelTrainer:
    """Train ensemble models for player projections."""

    def __init__(self, target: str = 'wrc_plus'):
        self.target = target
        self.feature_engineer = FeatureEngineer()
        self.metrics_calculator = AdvancedMetricsCalculator()
        self.age_projector = AgeAdjustedProjector()

        self.models = {}
        self.scaler = StandardScaler()
        self.feature_importance = {}

        # Feature columns to use (will be refined after feature selection)
        self.feature_cols = []
        self.categorical_features = ['highest_level']

    async def prepare_training_data(
        self,
        min_pa: int = 100,
        seasons: List[int] = [2021, 2022, 2023, 2024, 2025]
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare training data with features and targets."""

        logger.info("Loading players with sufficient plate appearances...")

        # Get players who have played in both MiLB and MLB
        query = """
            WITH milb_players AS (
                SELECT DISTINCT mlb_player_id
                FROM milb_game_logs
                WHERE season IN :seasons
                AND plate_appearances > 0
                GROUP BY mlb_player_id
                HAVING SUM(plate_appearances) >= :min_pa
            ),
            mlb_players AS (
                SELECT DISTINCT mlb_player_id,
                       AVG(wrc_plus) as mlb_wrc_plus,
                       AVG(woba) as mlb_woba
                FROM mlb_game_logs
                WHERE mlb_player_id IN (SELECT mlb_player_id FROM milb_players)
                GROUP BY mlb_player_id
            )
            SELECT m.mlb_player_id, m.mlb_wrc_plus, m.mlb_woba
            FROM mlb_players m
            WHERE m.mlb_wrc_plus IS NOT NULL
        """

        async with engine.begin() as conn:
            result = await conn.execute(
                text(query),
                {"seasons": tuple(seasons), "min_pa": min_pa}
            )
            target_data = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Found {len(target_data)} players with MLB performance data")

        # Get features for these players
        all_features = []
        for i, player_id in enumerate(target_data['mlb_player_id'].values):
            if i % 50 == 0:
                logger.info(f"Processing features for player {i}/{len(target_data)}")

            try:
                # Get MiLB features for the season before MLB
                features = await self.feature_engineer.create_player_features(player_id)
                if features:
                    all_features.append(features)
            except Exception as e:
                logger.error(f"Error getting features for player {player_id}: {str(e)}")
                continue

        # Create feature dataframe
        feature_df = pd.DataFrame(all_features)

        # Merge with targets
        data = feature_df.merge(
            target_data,
            left_on='player_id',
            right_on='mlb_player_id',
            how='inner'
        )

        logger.info(f"Final training dataset: {len(data)} players with {len(feature_df.columns)} features")

        # Separate features and target
        if self.target == 'wrc_plus':
            y = data['mlb_wrc_plus']
        elif self.target == 'woba':
            y = data['mlb_woba']
        else:
            raise ValueError(f"Unknown target: {self.target}")

        # Drop target columns and IDs from features
        X = data.drop(columns=['mlb_player_id', 'player_id', 'mlb_wrc_plus', 'mlb_woba', 'feature_date'], errors='ignore')

        return X, y

    def select_features(self, X: pd.DataFrame, y: pd.Series, top_n: int = 30) -> List[str]:
        """Select most important features using Random Forest."""

        logger.info("Selecting top features...")

        # Handle categorical features
        X_encoded = pd.get_dummies(X, columns=[col for col in self.categorical_features if col in X.columns])

        # Remove columns with too many nulls
        null_threshold = 0.3
        valid_cols = X_encoded.columns[X_encoded.isnull().mean() < null_threshold]
        X_clean = X_encoded[valid_cols].fillna(0)

        # Train RF for feature importance
        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(X_clean, y)

        # Get feature importances
        importances = pd.DataFrame({
            'feature': X_clean.columns,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)

        # Select top features
        top_features = importances.head(top_n)['feature'].tolist()

        logger.info(f"Top 10 features: {importances.head(10)[['feature', 'importance']].values.tolist()}")

        return top_features

    def train_xgboost(self, X_train, y_train, X_val, y_val) -> xgb.XGBRegressor:
        """Train XGBoost model."""

        logger.info("Training XGBoost model...")

        params = {
            'objective': 'reg:squarederror',
            'n_estimators': 300,
            'max_depth': 6,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'min_child_weight': 3,
            'gamma': 0.1,
            'random_state': 42,
            'n_jobs': -1
        }

        model = xgb.XGBRegressor(**params)

        # Early stopping
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=False
        )

        # Evaluate
        val_pred = model.predict(X_val)
        mae = mean_absolute_error(y_val, val_pred)
        r2 = r2_score(y_val, val_pred)

        logger.info(f"XGBoost - MAE: {mae:.2f}, R2: {r2:.3f}")

        return model

    def train_random_forest(self, X_train, y_train, X_val, y_val) -> RandomForestRegressor:
        """Train Random Forest model."""

        logger.info("Training Random Forest model...")

        params = {
            'n_estimators': 200,
            'max_depth': 12,
            'min_samples_split': 10,
            'min_samples_leaf': 5,
            'max_features': 'sqrt',
            'random_state': 42,
            'n_jobs': -1
        }

        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)

        # Evaluate
        val_pred = model.predict(X_val)
        mae = mean_absolute_error(y_val, val_pred)
        r2 = r2_score(y_val, val_pred)

        logger.info(f"Random Forest - MAE: {mae:.2f}, R2: {r2:.3f}")

        # Store feature importance
        self.feature_importance['rf'] = pd.DataFrame({
            'feature': X_train.columns,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        return model

    def train_neural_network(self, X_train, y_train, X_val, y_val) -> MLPRegressor:
        """Train Neural Network model."""

        logger.info("Training Neural Network model...")

        params = {
            'hidden_layer_sizes': (128, 64, 32),
            'activation': 'relu',
            'solver': 'adam',
            'learning_rate': 'adaptive',
            'learning_rate_init': 0.001,
            'max_iter': 500,
            'early_stopping': True,
            'validation_fraction': 0.1,
            'random_state': 42
        }

        model = MLPRegressor(**params)

        # Scale the data for neural network
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        model.fit(X_train_scaled, y_train)

        # Evaluate
        val_pred = model.predict(X_val_scaled)
        mae = mean_absolute_error(y_val, val_pred)
        r2 = r2_score(y_val, val_pred)

        logger.info(f"Neural Network - MAE: {mae:.2f}, R2: {r2:.3f}")

        return model

    def create_ensemble(
        self,
        xgb_model,
        rf_model,
        nn_model,
        X_train,
        y_train,
        X_val,
        y_val
    ) -> Dict:
        """Create ensemble model with weighted voting."""

        logger.info("Creating ensemble model...")

        # Create ensemble with custom weights based on validation performance
        models = [
            ('xgboost', xgb_model),
            ('random_forest', rf_model),
            ('neural_net', nn_model)
        ]

        # Calculate weights based on validation performance
        weights = []
        for name, model in models:
            if name == 'neural_net':
                val_pred = model.predict(self.scaler.transform(X_val))
            else:
                val_pred = model.predict(X_val)

            # Use R2 as weight
            weight = max(0, r2_score(y_val, val_pred))
            weights.append(weight)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w/total_weight for w in weights]

        logger.info(f"Ensemble weights - XGB: {weights[0]:.3f}, RF: {weights[1]:.3f}, NN: {weights[2]:.3f}")

        # Create custom ensemble predictions
        ensemble_pred = np.zeros(len(X_val))

        for (name, model), weight in zip(models, weights):
            if name == 'neural_net':
                pred = model.predict(self.scaler.transform(X_val))
            else:
                pred = model.predict(X_val)
            ensemble_pred += weight * pred

        # Evaluate ensemble
        mae = mean_absolute_error(y_val, ensemble_pred)
        r2 = r2_score(y_val, ensemble_pred)
        rmse = np.sqrt(mean_squared_error(y_val, ensemble_pred))

        logger.info(f"Ensemble - MAE: {mae:.2f}, R2: {r2:.3f}, RMSE: {rmse:.2f}")

        return {
            'models': models,
            'weights': weights,
            'scaler': self.scaler,
            'performance': {
                'mae': mae,
                'r2': r2,
                'rmse': rmse
            }
        }

    async def train_full_pipeline(
        self,
        save_path: str = 'projection_models.pkl'
    ) -> Dict:
        """Train the complete projection pipeline."""

        logger.info("Starting full pipeline training...")
        start_time = datetime.now()

        # Prepare data
        X, y = await self.prepare_training_data()

        if len(X) < 50:
            logger.error("Insufficient training data")
            return {}

        # Select features
        self.feature_cols = self.select_features(X, y)

        # Prepare feature matrix
        X_selected = pd.get_dummies(
            X[self.feature_cols],
            columns=[col for col in self.categorical_features if col in self.feature_cols]
        ).fillna(0)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_selected, y, test_size=0.2, random_state=42
        )

        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train, test_size=0.2, random_state=42
        )

        logger.info(f"Training set: {len(X_train)}, Validation: {len(X_val)}, Test: {len(X_test)}")

        # Train individual models
        xgb_model = self.train_xgboost(X_train, y_train, X_val, y_val)
        rf_model = self.train_random_forest(X_train, y_train, X_val, y_val)
        nn_model = self.train_neural_network(X_train, y_train, X_val, y_val)

        # Create ensemble
        ensemble = self.create_ensemble(
            xgb_model, rf_model, nn_model,
            X_train, y_train, X_val, y_val
        )

        # Test set evaluation
        logger.info("\nFinal test set evaluation:")
        test_predictions = self.predict_ensemble(ensemble, X_test)

        test_mae = mean_absolute_error(y_test, test_predictions)
        test_r2 = r2_score(y_test, test_predictions)
        test_rmse = np.sqrt(mean_squared_error(y_test, test_predictions))

        logger.info(f"Test Set - MAE: {test_mae:.2f}, R2: {test_r2:.3f}, RMSE: {test_rmse:.2f}")

        # Save models
        model_package = {
            'ensemble': ensemble,
            'feature_cols': self.feature_cols,
            'target': self.target,
            'feature_importance': self.feature_importance,
            'test_performance': {
                'mae': test_mae,
                'r2': test_r2,
                'rmse': test_rmse
            },
            'training_date': datetime.now().isoformat(),
            'n_training_samples': len(X_train)
        }

        with open(save_path, 'wb') as f:
            pickle.dump(model_package, f)

        logger.info(f"Models saved to {save_path}")

        elapsed = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"Training completed in {elapsed:.1f} minutes")

        return model_package

    def predict_ensemble(self, ensemble: Dict, X: pd.DataFrame) -> np.ndarray:
        """Make predictions using the ensemble."""

        predictions = np.zeros(len(X))

        for (name, model), weight in zip(ensemble['models'], ensemble['weights']):
            if name == 'neural_net':
                pred = model.predict(ensemble['scaler'].transform(X))
            else:
                pred = model.predict(X)
            predictions += weight * pred

        return predictions

    async def predict_player(
        self,
        player_id: int,
        model_package: Dict
    ) -> Dict:
        """Generate predictions for a single player."""

        # Get player features
        features = await self.feature_engineer.create_player_features(player_id)

        if not features:
            logger.error(f"Could not generate features for player {player_id}")
            return {}

        # Prepare feature vector
        feature_df = pd.DataFrame([features])
        X = pd.get_dummies(
            feature_df[model_package['feature_cols']],
            columns=[col for col in self.categorical_features if col in model_package['feature_cols']]
        ).fillna(0)

        # Ensure all expected columns are present
        for col in model_package['ensemble']['models'][0][1].feature_names_in_:
            if col not in X.columns:
                X[col] = 0
        X = X[model_package['ensemble']['models'][0][1].feature_names_in_]

        # Make prediction
        prediction = self.predict_ensemble(model_package['ensemble'], X)[0]

        # Get age-adjusted projections
        current_age = features.get('estimated_age', 22)
        current_stats = {
            'wrc_plus': prediction,
            'batting_avg': features.get('batting_avg', .250),
            'obp': features.get('obp', .320),
            'slg': features.get('slg', .400),
            'hr_rate': features.get('hr_rate', 0.03),
            'sb_rate': features.get('sb_rate', 0.02),
            'walk_rate': features.get('bb_rate', 0.08),
            'strikeout_rate': features.get('k_rate', 0.22),
            'war': prediction / 20  # Rough WAR estimate
        }

        # Generate career arc projections
        projections = self.age_projector.project_career_arc(
            current_stats=current_stats,
            current_age=current_age,
            position=features.get('highest_level', 'SS'),
            years_ahead=10
        )

        return {
            'player_id': player_id,
            'current_projection': {
                self.target: round(prediction, 1) if self.target == 'wrc_plus' else round(prediction, 3)
            },
            'peak_projection': {
                'age': max(projections, key=lambda x: x.get('projected_wrc_plus', 0))['age'],
                'wrc_plus': max(p.get('projected_wrc_plus', 0) for p in projections)
            },
            'yearly_projections': projections[:10],  # Next 10 years
            'confidence': self._calculate_prediction_confidence(features, model_package)
        }

    def _calculate_prediction_confidence(self, features: Dict, model_package: Dict) -> float:
        """Calculate confidence in the prediction based on data quality."""

        confidence = 0.5  # Base confidence

        # More games = higher confidence
        games = features.get('games_played', 0)
        if games > 100:
            confidence += 0.2
        elif games > 50:
            confidence += 0.1

        # Higher level = higher confidence
        level = features.get('highest_level', 'A')
        if level in ['AAA', 'MLB']:
            confidence += 0.15
        elif level == 'AA':
            confidence += 0.1
        elif level == 'A+':
            confidence += 0.05

        # Model performance
        model_r2 = model_package.get('test_performance', {}).get('r2', 0.5)
        confidence += model_r2 * 0.15

        return min(0.95, confidence)


async def main():
    """Train and test the projection model."""

    trainer = ProjectionModelTrainer(target='wrc_plus')

    # Train the full pipeline
    model_package = await trainer.train_full_pipeline(
        save_path='wrc_plus_projection_model.pkl'
    )

    if not model_package:
        logger.error("Training failed")
        return

    # Test on a sample player
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT mlb_player_id
            FROM milb_game_logs
            WHERE season = 2024
            AND level = 'AAA'
            AND plate_appearances > 200
            ORDER BY ops DESC
            LIMIT 1
        """))
        test_player_id = result.fetchone()[0]

    # Generate prediction
    logger.info(f"\nGenerating prediction for player {test_player_id}...")
    prediction = await trainer.predict_player(test_player_id, model_package)

    if prediction:
        print("\n" + "="*80)
        print(f"PROJECTION FOR PLAYER {test_player_id}")
        print("="*80)
        print(f"Current wRC+ Projection: {prediction['current_projection']['wrc_plus']}")
        print(f"Peak Projection: {prediction['peak_projection']['wrc_plus']} at age {prediction['peak_projection']['age']}")
        print(f"Confidence: {prediction['confidence']:.1%}")

        print("\nYear-by-Year Projections:")
        for proj in prediction['yearly_projections'][:5]:
            print(f"  Age {proj['age']} ({proj['season']}): wRC+ {proj['projected_wrc_plus']} [{proj['confidence_band']['lower']}-{proj['confidence_band']['upper']}]")

    # Train wOBA model as well
    logger.info("\n" + "="*50)
    logger.info("Training wOBA projection model...")

    woba_trainer = ProjectionModelTrainer(target='woba')
    woba_model = await woba_trainer.train_full_pipeline(
        save_path='woba_projection_model.pkl'
    )


if __name__ == "__main__":
    asyncio.run(main())