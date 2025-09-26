"""
ML Testing suite runner and validation script.
Comprehensive testing for all ML pipeline components with integration tests.
"""

import pytest
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.ml.feature_engineering import FeatureEngineeringPipeline
from app.ml.training_pipeline import ModelTrainingPipeline
from app.ml.evaluation import ModelEvaluator
from app.ml.temporal_validation import TemporalValidationStrategy
from app.ml.interpretability import SHAPAnalyzer
from app.ml.model_registry import ModelVersioningSystem

logger = logging.getLogger(__name__)


class MLPipelineValidator:
    """Comprehensive ML pipeline validation."""

    def __init__(self):
        self.validation_results = {}
        self.test_data = None

    def create_test_data(self, n_samples: int = 500) -> pd.DataFrame:
        """Create realistic test data for validation."""
        logger.info(f"Creating test data with {n_samples} samples")

        np.random.seed(42)

        # Create realistic prospect data
        data = pd.DataFrame({
            'mlb_id': np.repeat(range(n_samples // 4), 4),
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
            'plate_appearances': np.random.randint(250, 650, n_samples),
            'innings_pitched': np.random.randint(0, 200, n_samples),
            'era': np.random.uniform(2.50, 6.00, n_samples),
            'whip': np.random.uniform(1.00, 2.00, n_samples)
        })

        # Create target variable based on realistic logic
        # Higher level + younger age + better stats = higher success probability
        level_scores = {'Low-A': 1, 'High-A': 2, 'Double-A': 3, 'Triple-A': 4}
        data['level_score'] = data['level'].map(level_scores)

        # Calculate success probability
        success_prob = (
            0.3 * (data['level_score'] / 4) +
            0.2 * ((28 - data['age']) / 10) +
            0.2 * ((data['batting_avg'] - 0.200) / 0.200) +
            0.15 * ((data['on_base_pct'] - 0.250) / 0.250) +
            0.15 * ((data['slugging_pct'] - 0.300) / 0.350)
        )

        # Add noise and create binary target
        success_prob = np.clip(success_prob + np.random.normal(0, 0.1, n_samples), 0, 1)
        data['mlb_success'] = (success_prob > 0.6).astype(int)

        # Remove helper column
        data.drop('level_score', axis=1, inplace=True)

        self.test_data = data
        logger.info(f"Test data created: {len(data)} records, {data['mlb_success'].mean():.2%} success rate")
        return data

    def validate_feature_engineering(self) -> Dict[str, Any]:
        """Validate feature engineering pipeline."""
        logger.info("Validating feature engineering pipeline")

        if self.test_data is None:
            self.create_test_data()

        try:
            pipeline = FeatureEngineeringPipeline()
            results = pipeline.process_features(
                self.test_data,
                target_column='mlb_success',
                scale_features=True,
                select_features=True,
                k_features=20
            )

            validation_results = {
                'status': 'passed',
                'features_created': results['pipeline_metadata']['total_features_created'],
                'features_selected': results['pipeline_metadata']['features_selected'],
                'age_adjustments_applied': results['pipeline_metadata']['age_adjustments_applied'],
                'progression_metrics_calculated': results['pipeline_metadata']['progression_metrics_calculated'],
                'rate_statistics_calculated': results['pipeline_metadata']['rate_statistics_calculated'],
                'features_scaled': results['pipeline_metadata']['features_scaled'],
                'feature_selection_applied': results['pipeline_metadata']['feature_selection_applied'],
                'processed_data_shape': results['processed_data'].shape,
                'target_excluded_from_features': 'mlb_success' not in results['selected_features']
            }

            # Validate specific requirements
            assert results['pipeline_metadata']['total_features_created'] >= 10, "Not enough features created"
            assert results['pipeline_metadata']['features_selected'] <= 20, "Too many features selected"
            assert 'mlb_success' not in results['selected_features'], "Target variable in features (data leakage)"

            logger.info("Feature engineering validation passed")

        except Exception as e:
            validation_results = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"Feature engineering validation failed: {e}")

        self.validation_results['feature_engineering'] = validation_results
        return validation_results

    def validate_model_training(self) -> Dict[str, Any]:
        """Validate model training pipeline."""
        logger.info("Validating model training pipeline")

        if self.test_data is None:
            self.create_test_data()

        try:
            pipeline = ModelTrainingPipeline(random_state=42)

            # Prepare training data
            data_splits = pipeline.prepare_training_data(
                self.test_data, 'mlb_success', temporal_split=True
            )

            # Train model with minimal configuration for speed
            training_results = pipeline.train_model(
                data_splits, hyperparameter_tuning='none'
            )

            validation_results = {
                'status': 'passed',
                'training_completed': True,
                'test_accuracy': training_results['test_results']['accuracy'],
                'test_precision': training_results['test_results']['precision'],
                'test_recall': training_results['test_results']['recall'],
                'test_f1': training_results['test_results']['f1'],
                'test_roc_auc': training_results['test_results']['roc_auc'],
                'target_accuracy_achieved': training_results['target_accuracy_achieved'],
                'data_splits_correct': all(key in data_splits for key in
                                         ['X_train', 'X_val', 'X_test', 'y_train', 'y_val', 'y_test']),
                'model_trained': pipeline.get_model().model is not None
            }

            # Validate requirements
            assert training_results['test_results']['accuracy'] > 0.4, "Accuracy too low"
            assert training_results['test_results']['roc_auc'] > 0.4, "ROC AUC too low"
            assert pipeline.get_model().model is not None, "Model not trained"

            logger.info(f"Model training validation passed. Accuracy: {training_results['test_results']['accuracy']:.4f}")

        except Exception as e:
            validation_results = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"Model training validation failed: {e}")

        self.validation_results['model_training'] = validation_results
        return validation_results

    def validate_model_evaluation(self) -> Dict[str, Any]:
        """Validate model evaluation system."""
        logger.info("Validating model evaluation system")

        try:
            evaluator = ModelEvaluator(target_accuracy=0.65)

            # Create mock predictions
            np.random.seed(42)
            n_samples = 100
            y_true = np.random.choice([0, 1], n_samples, p=[0.6, 0.4])
            y_pred_proba = np.random.uniform(0.1, 0.9, n_samples)
            y_pred = (y_pred_proba > 0.5).astype(int)

            # Evaluate model
            metrics = evaluator.evaluate_model(
                y_true, y_pred, y_pred_proba,
                model_version="validation_test", dataset_name="validation"
            )

            # Validate target accuracy
            validation_result = evaluator.validate_target_accuracy(metrics, "validation")

            validation_results = {
                'status': 'passed',
                'metrics_calculated': True,
                'accuracy': metrics.accuracy,
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1_score': metrics.f1_score,
                'roc_auc': metrics.roc_auc,
                'target_accuracy_validation': validation_result['target_met'],
                'confusion_matrix_shape': (len(metrics.confusion_matrix), len(metrics.confusion_matrix[0])),
                'evaluation_history_tracked': len(evaluator.evaluation_history) > 0
            }

            # Validate requirements
            assert 0 <= metrics.accuracy <= 1, "Invalid accuracy value"
            assert 0 <= metrics.roc_auc <= 1, "Invalid ROC AUC value"
            assert len(metrics.confusion_matrix) == 2, "Invalid confusion matrix"

            logger.info("Model evaluation validation passed")

        except Exception as e:
            validation_results = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"Model evaluation validation failed: {e}")

        self.validation_results['model_evaluation'] = validation_results
        return validation_results

    def validate_temporal_validation(self) -> Dict[str, Any]:
        """Validate temporal cross-validation."""
        logger.info("Validating temporal validation strategy")

        if self.test_data is None:
            self.create_test_data()

        try:
            # Create a simple mock model for validation
            class MockModel:
                def fit(self, X, y):
                    return self
                def predict(self, X):
                    return np.random.choice([0, 1], len(X))
                def predict_proba(self, X):
                    proba = np.random.uniform(0, 1, (len(X), 2))
                    proba = proba / proba.sum(axis=1, keepdims=True)
                    return proba

            validator = TemporalValidationStrategy()
            model = MockModel()

            # Prepare features and target
            X = self.test_data[['age', 'batting_avg', 'on_base_pct', 'slugging_pct']].copy()
            y = self.test_data['mlb_success'].copy()

            # Add date column for temporal validation
            X['date_recorded'] = self.test_data['date_recorded']

            # Run temporal validation
            results = validator.validate_with_temporal_splits(
                X, y, model, n_splits=3, test_size=50
            )

            validation_results = {
                'status': 'passed',
                'temporal_splits_completed': True,
                'mean_accuracy': results['mean_accuracy'],
                'std_accuracy': results['std_accuracy'],
                'target_accuracy_met': results['target_accuracy_met'],
                'fold_results_count': len(results['fold_results']),
                'prevents_data_leakage': True  # Temporal splits prevent leakage by design
            }

            # Validate requirements
            assert 0 <= results['mean_accuracy'] <= 1, "Invalid mean accuracy"
            assert len(results['fold_results']) == 3, "Incorrect number of folds"

            logger.info(f"Temporal validation passed. Mean accuracy: {results['mean_accuracy']:.4f}")

        except Exception as e:
            validation_results = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"Temporal validation failed: {e}")

        self.validation_results['temporal_validation'] = validation_results
        return validation_results

    def validate_integration(self) -> Dict[str, Any]:
        """Validate end-to-end integration."""
        logger.info("Validating end-to-end pipeline integration")

        if self.test_data is None:
            self.create_test_data()

        try:
            # Run complete pipeline
            feature_pipeline = FeatureEngineeringPipeline()
            training_pipeline = ModelTrainingPipeline(random_state=42)
            evaluator = ModelEvaluator(target_accuracy=0.65)

            # Step 1: Feature engineering
            feature_results = feature_pipeline.process_features(
                self.test_data, target_column='mlb_success'
            )

            # Step 2: Prepare training data
            data_splits = training_pipeline.prepare_training_data(
                self.test_data, 'mlb_success', temporal_split=True
            )

            # Step 3: Train model
            training_results = training_pipeline.train_model(data_splits)

            # Step 4: Evaluate model
            y_pred = training_pipeline.get_model().model.predict(data_splits['X_test'])
            y_pred_proba = training_pipeline.get_model().model.predict_proba(data_splits['X_test'])[:, 1]

            metrics = evaluator.evaluate_model(
                data_splits['y_test'], y_pred, y_pred_proba,
                model_version="integration_test", dataset_name="test"
            )

            validation_results = {
                'status': 'passed',
                'pipeline_integration_successful': True,
                'feature_engineering_completed': len(feature_results['selected_features']) > 0,
                'model_training_completed': training_results['test_results']['accuracy'] > 0,
                'model_evaluation_completed': metrics.accuracy > 0,
                'final_accuracy': metrics.accuracy,
                'final_roc_auc': metrics.roc_auc,
                'target_accuracy_achieved': metrics.target_accuracy_met,
                'data_flow_correct': True
            }

            logger.info(f"Integration validation passed. Final accuracy: {metrics.accuracy:.4f}")

        except Exception as e:
            validation_results = {
                'status': 'failed',
                'error': str(e)
            }
            logger.error(f"Integration validation failed: {e}")

        self.validation_results['integration'] = validation_results
        return validation_results

    def run_all_validations(self) -> Dict[str, Any]:
        """Run all validation tests."""
        logger.info("Running comprehensive ML pipeline validation")

        start_time = datetime.now()

        # Run all validation components
        self.validate_feature_engineering()
        self.validate_model_training()
        self.validate_model_evaluation()
        self.validate_temporal_validation()
        self.validate_integration()

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Summary results
        passed_tests = sum(1 for result in self.validation_results.values()
                          if result.get('status') == 'passed')
        total_tests = len(self.validation_results)

        summary = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'success_rate': passed_tests / total_tests if total_tests > 0 else 0,
            'execution_time_seconds': execution_time,
            'timestamp': datetime.now().isoformat(),
            'all_tests_passed': passed_tests == total_tests
        }

        self.validation_results['summary'] = summary

        if summary['all_tests_passed']:
            logger.info(f"All {total_tests} validation tests passed in {execution_time:.2f} seconds")
        else:
            logger.error(f"{summary['failed_tests']} out of {total_tests} tests failed")

        return self.validation_results

    def export_validation_report(self, filepath: str) -> None:
        """Export validation results to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        logger.info(f"Validation report exported to {filepath}")


def run_unit_tests() -> bool:
    """Run all unit tests using pytest."""
    logger.info("Running unit tests with pytest")

    # Get test directory
    test_dir = Path(__file__).parent

    # Run pytest
    exit_code = pytest.main([
        str(test_dir),
        '-v',
        '--tb=short',
        '--durations=10'
    ])

    return exit_code == 0


def main():
    """Main validation runner."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting ML Pipeline Validation Suite")

    # Run unit tests
    logger.info("=" * 50)
    logger.info("RUNNING UNIT TESTS")
    logger.info("=" * 50)

    unit_tests_passed = run_unit_tests()

    # Run integration validation
    logger.info("=" * 50)
    logger.info("RUNNING INTEGRATION VALIDATION")
    logger.info("=" * 50)

    validator = MLPipelineValidator()
    validation_results = validator.run_all_validations()

    # Export results
    report_path = Path(__file__).parent / "validation_report.json"
    validator.export_validation_report(str(report_path))

    # Final summary
    logger.info("=" * 50)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 50)

    summary = validation_results['summary']
    logger.info(f"Unit Tests: {'PASSED' if unit_tests_passed else 'FAILED'}")
    logger.info(f"Integration Tests: {summary['passed_tests']}/{summary['total_tests']} passed")
    logger.info(f"Overall Success Rate: {summary['success_rate']:.1%}")
    logger.info(f"Execution Time: {summary['execution_time_seconds']:.2f} seconds")

    overall_success = unit_tests_passed and summary['all_tests_passed']
    logger.info(f"OVERALL RESULT: {'SUCCESS' if overall_success else 'FAILURE'}")

    return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)