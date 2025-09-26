"""
ML Model training pipeline with XGBoost classifier.
Implements hyperparameter tuning, proper data splits, and overfitting prevention.
"""

import logging
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np
import pandas as pd
from sklearn.model_selection import (
    train_test_split, TimeSeriesSplit, GridSearchCV, RandomizedSearchCV
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix
)
import xgboost as xgb
import optuna
from optuna.samplers import TPESampler
import mlflow
import mlflow.xgboost
from mlflow.tracking import MlflowClient

from app.ml.feature_engineering import FeatureEngineeringPipeline

logger = logging.getLogger(__name__)


class XGBoostModelTrainer:
    """XGBoost classifier training with hyperparameter optimization."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.model = None
        self.best_params = None
        self.feature_importance = None
        self.training_history = []

    def get_default_params(self) -> Dict[str, Any]:
        """Get default XGBoost parameters from story specifications."""
        return {
            'n_estimators': 1000,
            'max_depth': 6,
            'learning_rate': 0.01,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'random_state': self.random_state,
            'early_stopping_rounds': 50,
            'verbosity': 0
        }

    def get_hyperparameter_space(self) -> Dict[str, Any]:
        """Define hyperparameter search space for optimization."""
        return {
            'n_estimators': [500, 1000, 1500, 2000],
            'max_depth': [3, 4, 5, 6, 7, 8],
            'learning_rate': [0.01, 0.05, 0.1, 0.15, 0.2],
            'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
            'min_child_weight': [1, 3, 5, 7],
            'gamma': [0, 0.1, 0.2, 0.3, 0.4],
            'reg_alpha': [0, 0.01, 0.1, 1, 10],
            'reg_lambda': [0, 0.01, 0.1, 1, 10]
        }

    def train_with_default_params(self, X_train: pd.DataFrame, y_train: pd.Series,
                                 X_val: pd.DataFrame = None, y_val: pd.Series = None) -> Dict[str, Any]:
        """
        Train XGBoost model with default parameters.

        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)

        Returns:
            Training results dictionary
        """
        logger.info("Training XGBoost model with default parameters")

        params = self.get_default_params()

        # Prepare evaluation sets
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))

        # Create and train model
        self.model = xgb.XGBClassifier(**params)

        # Train with early stopping
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            eval_metric=['logloss', 'auc'],
            verbose=False
        )

        # Store feature importance
        self.feature_importance = dict(zip(
            X_train.columns,
            self.model.feature_importances_
        ))

        # Generate training results
        train_results = self._evaluate_model(X_train, y_train, "training")
        if X_val is not None:
            val_results = self._evaluate_model(X_val, y_val, "validation")
            train_results.update({f"val_{k}": v for k, v in val_results.items()})

        train_results.update({
            'model_params': params,
            'feature_importance': self.feature_importance,
            'n_features': len(X_train.columns),
            'training_samples': len(X_train),
            'best_iteration': getattr(self.model, 'best_iteration', len(self.model.evals_result_['validation_0']['logloss']))
        })

        logger.info(f"Model training completed. Training accuracy: {train_results['accuracy']:.4f}")
        return train_results

    def tune_hyperparameters_grid_search(self, X_train: pd.DataFrame, y_train: pd.Series,
                                        cv_folds: int = 5,
                                        n_jobs: int = -1) -> Dict[str, Any]:
        """
        Tune hyperparameters using GridSearchCV.

        Args:
            X_train: Training features
            y_train: Training target
            cv_folds: Number of cross-validation folds
            n_jobs: Number of parallel jobs

        Returns:
            Tuning results dictionary
        """
        logger.info("Starting hyperparameter tuning with GridSearchCV")

        # Reduced parameter grid for computational efficiency
        param_grid = {
            'n_estimators': [500, 1000],
            'max_depth': [4, 5, 6],
            'learning_rate': [0.01, 0.05, 0.1],
            'subsample': [0.8, 0.9],
            'colsample_bytree': [0.8, 0.9]
        }

        base_params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'random_state': self.random_state,
            'verbosity': 0
        }

        # Create model with base parameters
        model = xgb.XGBClassifier(**base_params)

        # Grid search with cross-validation
        grid_search = GridSearchCV(
            model,
            param_grid,
            cv=cv_folds,
            scoring='roc_auc',
            n_jobs=n_jobs,
            verbose=1,
            return_train_score=True
        )

        grid_search.fit(X_train, y_train)

        # Store best model and parameters
        self.model = grid_search.best_estimator_
        self.best_params = grid_search.best_params_

        # Feature importance
        self.feature_importance = dict(zip(
            X_train.columns,
            self.model.feature_importances_
        ))

        results = {
            'best_params': self.best_params,
            'best_cv_score': grid_search.best_score_,
            'cv_results': grid_search.cv_results_,
            'feature_importance': self.feature_importance,
            'tuning_method': 'grid_search'
        }

        logger.info(f"Grid search completed. Best CV score: {grid_search.best_score_:.4f}")
        return results

    def tune_hyperparameters_optuna(self, X_train: pd.DataFrame, y_train: pd.Series,
                                   n_trials: int = 100,
                                   cv_folds: int = 5,
                                   timeout: int = 3600) -> Dict[str, Any]:
        """
        Tune hyperparameters using Optuna.

        Args:
            X_train: Training features
            y_train: Training target
            n_trials: Number of Optuna trials
            cv_folds: Number of cross-validation folds
            timeout: Maximum optimization time in seconds

        Returns:
            Tuning results dictionary
        """
        logger.info(f"Starting hyperparameter tuning with Optuna ({n_trials} trials)")

        def objective(trial):
            # Suggest hyperparameters
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 2000),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 0.5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 10, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 10, log=True),
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'random_state': self.random_state,
                'verbosity': 0
            }

            # Cross-validation
            model = xgb.XGBClassifier(**params)

            from sklearn.model_selection import cross_val_score
            cv_scores = cross_val_score(
                model, X_train, y_train,
                cv=cv_folds, scoring='roc_auc',
                n_jobs=1  # Avoid nested parallelization
            )

            return cv_scores.mean()

        # Create study
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=self.random_state)
        )

        # Optimize
        study.optimize(objective, n_trials=n_trials, timeout=timeout)

        # Train final model with best parameters
        best_params = study.best_params.copy()
        best_params.update({
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'random_state': self.random_state,
            'verbosity': 0
        })

        self.model = xgb.XGBClassifier(**best_params)
        self.model.fit(X_train, y_train)
        self.best_params = best_params

        # Feature importance
        self.feature_importance = dict(zip(
            X_train.columns,
            self.model.feature_importances_
        ))

        results = {
            'best_params': self.best_params,
            'best_cv_score': study.best_value,
            'n_trials': len(study.trials),
            'study_trials': [trial.value for trial in study.trials if trial.value is not None],
            'feature_importance': self.feature_importance,
            'tuning_method': 'optuna'
        }

        logger.info(f"Optuna optimization completed. Best CV score: {study.best_value:.4f}")
        return results

    def _evaluate_model(self, X: pd.DataFrame, y: pd.Series, dataset_name: str) -> Dict[str, float]:
        """Evaluate model performance on given dataset."""

        if self.model is None:
            raise ValueError("Model must be trained before evaluation")

        y_pred = self.model.predict(X)
        y_pred_proba = self.model.predict_proba(X)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, average='binary'),
            'recall': recall_score(y, y_pred, average='binary'),
            'f1': f1_score(y, y_pred, average='binary'),
            'roc_auc': roc_auc_score(y, y_pred_proba)
        }

        logger.info(f"{dataset_name} metrics: "
                   f"Accuracy={metrics['accuracy']:.4f}, "
                   f"AUC={metrics['roc_auc']:.4f}")

        return metrics

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions with trained model."""

        if self.model is None:
            raise ValueError("Model must be trained before making predictions")

        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)[:, 1]

        return predictions, probabilities

    def save_model(self, filepath: str) -> None:
        """Save trained model to file."""

        if self.model is None:
            raise ValueError("No model to save")

        model_data = {
            'model': self.model,
            'best_params': self.best_params,
            'feature_importance': self.feature_importance,
            'training_history': self.training_history,
            'random_state': self.random_state
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved to {filepath}")

    def load_model(self, filepath: str) -> None:
        """Load trained model from file."""

        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.best_params = model_data.get('best_params')
        self.feature_importance = model_data.get('feature_importance')
        self.training_history = model_data.get('training_history', [])
        self.random_state = model_data.get('random_state', 42)

        logger.info(f"Model loaded from {filepath}")


class ModelTrainingPipeline:
    """Complete model training pipeline with data preprocessing."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.feature_pipeline = FeatureEngineeringPipeline()
        self.model_trainer = XGBoostModelTrainer(random_state)
        self.training_results = {}

    def prepare_training_data(self, df: pd.DataFrame,
                             target_column: str,
                             test_size: float = 0.2,
                             temporal_split: bool = True) -> Dict[str, Any]:
        """
        Prepare training data with proper temporal splits.

        Args:
            df: Input DataFrame
            target_column: Target variable column
            test_size: Test set proportion
            temporal_split: Use temporal splitting

        Returns:
            Dictionary with train/validation/test splits
        """
        logger.info("Preparing training data with temporal splits")

        # Feature engineering
        feature_results = self.feature_pipeline.process_features(
            df, target_column=target_column,
            scale_features=True, select_features=True, k_features=50
        )

        processed_df = feature_results['processed_data']
        selected_features = feature_results['selected_features']

        # Prepare features and target
        X = processed_df[selected_features]
        y = processed_df[target_column]

        # Handle temporal splits
        if temporal_split and 'date_recorded' in processed_df.columns:
            # Sort by date for temporal split
            sorted_indices = processed_df.sort_values('date_recorded').index
            X = X.loc[sorted_indices]
            y = y.loc[sorted_indices]

            # Temporal split: older data for training, newer for testing
            split_idx = int(len(X) * (1 - test_size))
            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

            # Further split training into train/validation
            val_size = 0.2
            val_split_idx = int(len(X_train) * (1 - val_size))
            X_val = X_train.iloc[val_split_idx:]
            y_val = y_train.iloc[val_split_idx:]
            X_train = X_train.iloc[:val_split_idx]
            y_train = y_train.iloc[:val_split_idx]

        else:
            # Random split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=self.random_state,
                stratify=y if len(y.unique()) > 1 else None
            )

            X_train, X_val, y_train, y_val = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state,
                stratify=y_train if len(y_train.unique()) > 1 else None
            )

        data_splits = {
            'X_train': X_train,
            'X_val': X_val,
            'X_test': X_test,
            'y_train': y_train,
            'y_val': y_val,
            'y_test': y_test,
            'feature_names': selected_features,
            'feature_engineering_results': feature_results
        }

        logger.info(f"Data prepared: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
        return data_splits

    def train_model(self, data_splits: Dict[str, Any],
                   hyperparameter_tuning: str = 'none',
                   tuning_trials: int = 50) -> Dict[str, Any]:
        """
        Train model with optional hyperparameter tuning.

        Args:
            data_splits: Data splits from prepare_training_data
            hyperparameter_tuning: 'none', 'grid_search', or 'optuna'
            tuning_trials: Number of trials for optuna

        Returns:
            Training results dictionary
        """
        logger.info(f"Training model with {hyperparameter_tuning} hyperparameter tuning")

        X_train = data_splits['X_train']
        y_train = data_splits['y_train']
        X_val = data_splits['X_val']
        y_val = data_splits['y_val']

        # Train based on tuning method
        if hyperparameter_tuning == 'grid_search':
            tuning_results = self.model_trainer.tune_hyperparameters_grid_search(
                X_train, y_train, cv_folds=5
            )
        elif hyperparameter_tuning == 'optuna':
            tuning_results = self.model_trainer.tune_hyperparameters_optuna(
                X_train, y_train, n_trials=tuning_trials, cv_folds=5
            )
        else:
            tuning_results = self.model_trainer.train_with_default_params(
                X_train, y_train, X_val, y_val
            )

        # Evaluate on test set
        X_test = data_splits['X_test']
        y_test = data_splits['y_test']
        test_results = self.model_trainer._evaluate_model(X_test, y_test, "test")

        # Combine all results
        training_results = {
            'tuning_results': tuning_results,
            'test_results': test_results,
            'data_info': {
                'n_features': len(data_splits['feature_names']),
                'train_samples': len(X_train),
                'val_samples': len(X_val),
                'test_samples': len(X_test),
                'feature_names': data_splits['feature_names']
            },
            'target_accuracy_achieved': test_results['accuracy'] >= 0.65,
            'training_timestamp': datetime.now().isoformat()
        }

        self.training_results = training_results

        logger.info(f"Model training completed. Test accuracy: {test_results['accuracy']:.4f}")
        return training_results

    def get_model(self) -> XGBoostModelTrainer:
        """Get trained model."""
        return self.model_trainer