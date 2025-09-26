"""
Unit tests for ML model training pipeline.
Tests XGBoost training, hyperparameter tuning, and pipeline integration.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.ml.training_pipeline import (
    XGBoostModelTrainer,
    ModelTrainingPipeline
)


class TestXGBoostModelTrainer:
    """Test XGBoost model trainer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.trainer = XGBoostModelTrainer(random_state=42)

        # Create sample training data
        np.random.seed(42)
        n_samples = 200
        n_features = 10

        self.X_train = pd.DataFrame(
            np.random.randn(n_samples, n_features),
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        self.y_train = pd.Series(np.random.choice([0, 1], n_samples, p=[0.6, 0.4]))

        self.X_val = pd.DataFrame(
            np.random.randn(50, n_features),
            columns=[f'feature_{i}' for i in range(n_features)]
        )
        self.y_val = pd.Series(np.random.choice([0, 1], 50, p=[0.6, 0.4]))

    def test_default_params(self):
        """Test default parameter configuration."""
        params = self.trainer.get_default_params()

        # Check that story-specified parameters are set
        assert params['n_estimators'] == 1000
        assert params['max_depth'] == 6
        assert params['learning_rate'] == 0.01
        assert params['subsample'] == 0.8
        assert params['colsample_bytree'] == 0.8
        assert params['objective'] == 'binary:logistic'
        assert params['random_state'] == 42

    def test_hyperparameter_space(self):
        """Test hyperparameter search space definition."""
        space = self.trainer.get_hyperparameter_space()

        # Check that all required parameters are defined
        required_params = ['n_estimators', 'max_depth', 'learning_rate', 'subsample', 'colsample_bytree']
        for param in required_params:
            assert param in space
            assert isinstance(space[param], list)
            assert len(space[param]) > 1

    def test_train_with_default_params(self):
        """Test training with default parameters."""
        results = self.trainer.train_with_default_params(
            self.X_train, self.y_train, self.X_val, self.y_val
        )

        # Check that model is trained
        assert self.trainer.model is not None
        assert hasattr(self.trainer.model, 'predict')

        # Check results structure
        assert 'accuracy' in results
        assert 'model_params' in results
        assert 'feature_importance' in results
        assert 'n_features' in results
        assert 'training_samples' in results

        # Check that feature importance is calculated
        assert len(results['feature_importance']) == len(self.X_train.columns)

        # Check that accuracy is reasonable (should be > 0.5 for binary classification)
        assert 0.4 <= results['accuracy'] <= 1.0

    def test_train_without_validation_set(self):
        """Test training without validation set."""
        results = self.trainer.train_with_default_params(self.X_train, self.y_train)

        assert self.trainer.model is not None
        assert 'accuracy' in results
        # Should not have validation metrics
        assert 'val_accuracy' not in results

    @patch('app.ml.training_pipeline.GridSearchCV')
    def test_grid_search_tuning(self, mock_grid_search):
        """Test hyperparameter tuning with GridSearchCV."""
        # Mock GridSearchCV
        mock_grid_instance = Mock()
        mock_grid_instance.best_estimator_ = Mock()
        mock_grid_instance.best_params_ = {'n_estimators': 500, 'max_depth': 4}
        mock_grid_instance.best_score_ = 0.75
        mock_grid_instance.cv_results_ = {'mean_test_score': [0.7, 0.75, 0.73]}

        # Mock feature_importances_
        mock_grid_instance.best_estimator_.feature_importances_ = np.random.rand(len(self.X_train.columns))

        mock_grid_search.return_value = mock_grid_instance

        results = self.trainer.tune_hyperparameters_grid_search(self.X_train, self.y_train)

        # Check that GridSearchCV was called
        mock_grid_search.assert_called_once()

        # Check results
        assert results['best_params'] == {'n_estimators': 500, 'max_depth': 4}
        assert results['best_cv_score'] == 0.75
        assert results['tuning_method'] == 'grid_search'
        assert 'feature_importance' in results

    @patch('app.ml.training_pipeline.optuna')
    def test_optuna_tuning(self, mock_optuna):
        """Test hyperparameter tuning with Optuna."""
        # Mock Optuna study
        mock_study = Mock()
        mock_study.best_params = {'n_estimators': 800, 'max_depth': 5, 'learning_rate': 0.05}
        mock_study.best_value = 0.78
        mock_study.trials = [Mock(value=0.7), Mock(value=0.75), Mock(value=0.78)]

        mock_optuna.create_study.return_value = mock_study

        results = self.trainer.tune_hyperparameters_optuna(
            self.X_train, self.y_train, n_trials=3
        )

        # Check that study was created and optimized
        mock_optuna.create_study.assert_called_once()
        mock_study.optimize.assert_called_once()

        # Check results
        assert 'best_params' in results
        assert results['best_cv_score'] == 0.78
        assert results['tuning_method'] == 'optuna'
        assert results['n_trials'] == 3

    def test_predict(self):
        """Test model prediction."""
        # Train model first
        self.trainer.train_with_default_params(self.X_train, self.y_train)

        # Make predictions
        predictions, probabilities = self.trainer.predict(self.X_val)

        # Check prediction shapes
        assert len(predictions) == len(self.X_val)
        assert len(probabilities) == len(self.X_val)

        # Check prediction values are valid
        assert all(pred in [0, 1] for pred in predictions)
        assert all(0 <= prob <= 1 for prob in probabilities)

    def test_predict_without_training(self):
        """Test that prediction fails when model is not trained."""
        with pytest.raises(ValueError, match="Model must be trained"):
            self.trainer.predict(self.X_val)

    def test_save_and_load_model(self, tmp_path):
        """Test model saving and loading."""
        # Train model
        self.trainer.train_with_default_params(self.X_train, self.y_train)

        # Save model
        model_path = tmp_path / "test_model.pkl"
        self.trainer.save_model(str(model_path))

        # Check that file was created
        assert model_path.exists()

        # Create new trainer and load model
        new_trainer = XGBoostModelTrainer()
        new_trainer.load_model(str(model_path))

        # Check that model was loaded correctly
        assert new_trainer.model is not None
        assert new_trainer.random_state == 42

        # Compare predictions
        original_pred, _ = self.trainer.predict(self.X_val)
        loaded_pred, _ = new_trainer.predict(self.X_val)

        np.testing.assert_array_equal(original_pred, loaded_pred)

    def test_save_without_model(self, tmp_path):
        """Test that saving fails when no model is trained."""
        model_path = tmp_path / "test_model.pkl"

        with pytest.raises(ValueError, match="No model to save"):
            self.trainer.save_model(str(model_path))

    def test_model_evaluation_metrics(self):
        """Test model evaluation metrics calculation."""
        # Train model
        self.trainer.train_with_default_params(self.X_train, self.y_train)

        # Test internal evaluation method
        metrics = self.trainer._evaluate_model(self.X_val, self.y_val, "test")

        # Check that all expected metrics are present
        expected_metrics = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']
        for metric in expected_metrics:
            assert metric in metrics
            assert 0 <= metrics[metric] <= 1


class TestModelTrainingPipeline:
    """Test complete model training pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = ModelTrainingPipeline(random_state=42)

        # Create sample data with target variable
        np.random.seed(42)
        n_samples = 300

        self.sample_data = pd.DataFrame({
            'mlb_id': np.repeat(range(75), 4),
            'age': np.random.randint(18, 26, n_samples),
            'level': np.random.choice(['Low-A', 'High-A', 'Double-A', 'Triple-A'], n_samples),
            'date_recorded': [datetime(2020, 1, 1) for _ in range(n_samples)],
            'batting_avg': np.random.uniform(0.200, 0.350, n_samples),
            'on_base_pct': np.random.uniform(0.250, 0.450, n_samples),
            'hits': np.random.randint(50, 150, n_samples),
            'at_bats': np.random.randint(300, 500, n_samples),
            'mlb_success': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])
        })

    @patch('app.ml.training_pipeline.FeatureEngineeringPipeline')
    def test_prepare_training_data(self, mock_feature_pipeline):
        """Test training data preparation."""
        # Mock feature engineering pipeline
        mock_pipeline_instance = Mock()
        mock_pipeline_instance.process_features.return_value = {
            'processed_data': self.sample_data,
            'selected_features': ['batting_avg', 'on_base_pct', 'hits'],
            'feature_engineering_results': {}
        }
        mock_feature_pipeline.return_value = mock_pipeline_instance

        data_splits = self.pipeline.prepare_training_data(
            self.sample_data, 'mlb_success', test_size=0.2, temporal_split=False
        )

        # Check that all expected splits are present
        expected_keys = ['X_train', 'X_val', 'X_test', 'y_train', 'y_val', 'y_test', 'feature_names']
        for key in expected_keys:
            assert key in data_splits

        # Check split sizes
        total_samples = len(data_splits['X_train']) + len(data_splits['X_val']) + len(data_splits['X_test'])
        assert total_samples == len(self.sample_data)

        # Check that test set is approximately 20%
        test_ratio = len(data_splits['X_test']) / len(self.sample_data)
        assert 0.15 <= test_ratio <= 0.25

    @patch('app.ml.training_pipeline.FeatureEngineeringPipeline')
    def test_temporal_split(self, mock_feature_pipeline):
        """Test temporal data splitting."""
        # Add proper date column for temporal splitting
        temporal_data = self.sample_data.copy()
        temporal_data['date_recorded'] = pd.date_range(
            start='2020-01-01', periods=len(temporal_data), freq='D'
        )

        # Mock feature engineering
        mock_pipeline_instance = Mock()
        mock_pipeline_instance.process_features.return_value = {
            'processed_data': temporal_data,
            'selected_features': ['batting_avg', 'on_base_pct'],
            'feature_engineering_results': {}
        }
        mock_feature_pipeline.return_value = mock_pipeline_instance

        data_splits = self.pipeline.prepare_training_data(
            temporal_data, 'mlb_success', temporal_split=True
        )

        # With temporal split, training data should be older than test data
        train_dates = temporal_data.loc[data_splits['X_train'].index, 'date_recorded']
        test_dates = temporal_data.loc[data_splits['X_test'].index, 'date_recorded']

        assert train_dates.max() <= test_dates.min()

    def test_train_model_no_tuning(self):
        """Test model training without hyperparameter tuning."""
        # Create simple data splits
        n_train, n_val, n_test = 200, 50, 50
        n_features = 5

        data_splits = {
            'X_train': pd.DataFrame(np.random.randn(n_train, n_features),
                                  columns=[f'feature_{i}' for i in range(n_features)]),
            'X_val': pd.DataFrame(np.random.randn(n_val, n_features),
                                columns=[f'feature_{i}' for i in range(n_features)]),
            'X_test': pd.DataFrame(np.random.randn(n_test, n_features),
                                 columns=[f'feature_{i}' for i in range(n_features)]),
            'y_train': pd.Series(np.random.choice([0, 1], n_train)),
            'y_val': pd.Series(np.random.choice([0, 1], n_val)),
            'y_test': pd.Series(np.random.choice([0, 1], n_test)),
            'feature_names': [f'feature_{i}' for i in range(n_features)]
        }

        results = self.pipeline.train_model(data_splits, hyperparameter_tuning='none')

        # Check results structure
        assert 'tuning_results' in results
        assert 'test_results' in results
        assert 'data_info' in results
        assert 'target_accuracy_achieved' in results
        assert 'training_timestamp' in results

        # Check that model was trained
        model = self.pipeline.get_model()
        assert model.model is not None

    @patch('app.ml.training_pipeline.XGBoostModelTrainer')
    def test_train_model_with_grid_search(self, mock_trainer_class):
        """Test model training with grid search tuning."""
        # Mock trainer
        mock_trainer = Mock()
        mock_trainer.tune_hyperparameters_grid_search.return_value = {
            'best_params': {'n_estimators': 500},
            'best_cv_score': 0.75,
            'tuning_method': 'grid_search'
        }
        mock_trainer._evaluate_model.return_value = {
            'accuracy': 0.70, 'precision': 0.68, 'recall': 0.72, 'f1': 0.70, 'roc_auc': 0.75
        }
        mock_trainer_class.return_value = mock_trainer

        # Simple data splits
        data_splits = {
            'X_train': pd.DataFrame([[1, 2], [3, 4]]),
            'X_val': pd.DataFrame([[5, 6]]),
            'X_test': pd.DataFrame([[7, 8]]),
            'y_train': pd.Series([0, 1]),
            'y_val': pd.Series([1]),
            'y_test': pd.Series([0]),
            'feature_names': ['f1', 'f2']
        }

        results = self.pipeline.train_model(data_splits, hyperparameter_tuning='grid_search')

        # Check that grid search was called
        mock_trainer.tune_hyperparameters_grid_search.assert_called_once()

        # Check results
        assert results['tuning_results']['tuning_method'] == 'grid_search'
        assert results['test_results']['accuracy'] == 0.70

    @patch('app.ml.training_pipeline.XGBoostModelTrainer')
    def test_train_model_with_optuna(self, mock_trainer_class):
        """Test model training with Optuna tuning."""
        # Mock trainer
        mock_trainer = Mock()
        mock_trainer.tune_hyperparameters_optuna.return_value = {
            'best_params': {'n_estimators': 800},
            'best_cv_score': 0.78,
            'tuning_method': 'optuna'
        }
        mock_trainer._evaluate_model.return_value = {
            'accuracy': 0.72, 'precision': 0.70, 'recall': 0.74, 'f1': 0.72, 'roc_auc': 0.77
        }
        mock_trainer_class.return_value = mock_trainer

        # Simple data splits
        data_splits = {
            'X_train': pd.DataFrame([[1, 2], [3, 4]]),
            'X_val': pd.DataFrame([[5, 6]]),
            'X_test': pd.DataFrame([[7, 8]]),
            'y_train': pd.Series([0, 1]),
            'y_val': pd.Series([1]),
            'y_test': pd.Series([0]),
            'feature_names': ['f1', 'f2']
        }

        results = self.pipeline.train_model(
            data_splits, hyperparameter_tuning='optuna', tuning_trials=10
        )

        # Check that Optuna was called with correct parameters
        mock_trainer.tune_hyperparameters_optuna.assert_called_once_with(
            data_splits['X_train'], data_splits['y_train'], n_trials=10, cv_folds=5
        )

        assert results['tuning_results']['tuning_method'] == 'optuna'

    def test_target_accuracy_achievement(self):
        """Test target accuracy achievement detection."""
        # Create data splits
        data_splits = {
            'X_train': pd.DataFrame(np.random.randn(100, 3)),
            'X_val': pd.DataFrame(np.random.randn(25, 3)),
            'X_test': pd.DataFrame(np.random.randn(25, 3)),
            'y_train': pd.Series(np.random.choice([0, 1], 100)),
            'y_val': pd.Series(np.random.choice([0, 1], 25)),
            'y_test': pd.Series(np.random.choice([0, 1], 25)),
            'feature_names': ['f1', 'f2', 'f3']
        }

        results = self.pipeline.train_model(data_splits)

        # Check that target_accuracy_achieved is boolean
        assert isinstance(results['target_accuracy_achieved'], bool)

        # Should be True if test accuracy >= 0.65
        expected_achievement = results['test_results']['accuracy'] >= 0.65
        assert results['target_accuracy_achieved'] == expected_achievement

    def test_get_model(self):
        """Test getting trained model."""
        model = self.pipeline.get_model()
        assert hasattr(model, 'model')  # Should be XGBoostModelTrainer instance


# Integration tests
class TestTrainingPipelineIntegration:
    """Integration tests for training pipeline."""

    def test_end_to_end_training(self):
        """Test complete end-to-end training process."""
        # Create realistic training data
        np.random.seed(42)
        n_samples = 500

        training_data = pd.DataFrame({
            'mlb_id': np.repeat(range(125), 4),
            'age': np.random.randint(18, 28, n_samples),
            'level': np.random.choice(['Low-A', 'High-A', 'Double-A', 'Triple-A'], n_samples),
            'date_recorded': pd.date_range('2020-01-01', periods=n_samples, freq='D'),
            'batting_avg': np.random.uniform(0.200, 0.400, n_samples),
            'on_base_pct': np.random.uniform(0.250, 0.500, n_samples),
            'slugging_pct': np.random.uniform(0.300, 0.650, n_samples),
            'hits': np.random.randint(30, 180, n_samples),
            'at_bats': np.random.randint(200, 600, n_samples),
            'walks': np.random.randint(10, 100, n_samples),
            'strikeouts': np.random.randint(30, 200, n_samples),
            'games_played': np.random.randint(50, 150, n_samples),
            'mlb_success': np.random.choice([0, 1], n_samples, p=[0.75, 0.25])
        })

        pipeline = ModelTrainingPipeline(random_state=42)

        # Prepare training data
        data_splits = pipeline.prepare_training_data(
            training_data, 'mlb_success', temporal_split=True
        )

        # Train model
        results = pipeline.train_model(data_splits, hyperparameter_tuning='none')

        # Verify complete pipeline execution
        assert 'tuning_results' in results
        assert 'test_results' in results
        assert results['test_results']['accuracy'] > 0.4  # Should be better than random

        # Verify model can make predictions
        model = pipeline.get_model()
        assert model.model is not None

        # Test prediction on validation set
        predictions, probabilities = model.predict(data_splits['X_test'])
        assert len(predictions) == len(data_splits['X_test'])
        assert len(probabilities) == len(data_splits['X_test'])

    def test_training_with_small_dataset(self):
        """Test training behavior with small dataset."""
        # Create very small dataset
        small_data = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [10, 20, 30, 40, 50],
            'target': [0, 1, 0, 1, 0]
        })

        pipeline = ModelTrainingPipeline(random_state=42)

        # Should handle small dataset gracefully
        data_splits = pipeline.prepare_training_data(small_data, 'target', test_size=0.2)

        # Training should complete without errors
        results = pipeline.train_model(data_splits)
        assert 'test_results' in results

    def test_training_with_imbalanced_data(self):
        """Test training with highly imbalanced target variable."""
        np.random.seed(42)
        n_samples = 200

        # Create highly imbalanced dataset (95% class 0, 5% class 1)
        imbalanced_data = pd.DataFrame({
            'feature1': np.random.randn(n_samples),
            'feature2': np.random.randn(n_samples),
            'feature3': np.random.randn(n_samples),
            'target': np.random.choice([0, 1], n_samples, p=[0.95, 0.05])
        })

        pipeline = ModelTrainingPipeline(random_state=42)

        data_splits = pipeline.prepare_training_data(imbalanced_data, 'target')
        results = pipeline.train_model(data_splits)

        # Should complete training even with imbalanced data
        assert 'test_results' in results
        # Accuracy might be high due to class imbalance, but should be reasonable
        assert 0.5 <= results['test_results']['accuracy'] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__])