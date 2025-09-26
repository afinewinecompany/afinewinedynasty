"""
Unit tests for model evaluation and metrics tracking.
Tests comprehensive performance evaluation and 65%+ accuracy validation.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
import json

from app.ml.evaluation import (
    ModelMetrics,
    ModelEvaluator
)


class TestModelMetrics:
    """Test ModelMetrics data class."""

    def test_model_metrics_creation(self):
        """Test ModelMetrics creation with required fields."""
        metrics = ModelMetrics(
            accuracy=0.75,
            precision=0.73,
            recall=0.77,
            f1_score=0.75,
            roc_auc=0.82,
            average_precision=0.79,
            matthews_corr=0.48,
            log_loss=0.55,
            confusion_matrix=[[45, 5], [8, 42]],
            classification_report={'0': {'precision': 0.85}, '1': {'precision': 0.89}},
            timestamp="2024-01-01T12:00:00"
        )

        assert metrics.accuracy == 0.75
        assert metrics.target_accuracy_met is True  # 0.75 >= 0.65
        assert metrics.confusion_matrix == [[45, 5], [8, 42]]

    def test_target_accuracy_met_calculation(self):
        """Test automatic target accuracy calculation."""
        # Test accuracy above threshold
        high_metrics = ModelMetrics(
            accuracy=0.70, precision=0.7, recall=0.7, f1_score=0.7,
            roc_auc=0.7, average_precision=0.7, matthews_corr=0.4,
            log_loss=0.6, confusion_matrix=[[10, 2], [3, 15]],
            classification_report={}, timestamp=datetime.now().isoformat()
        )
        assert high_metrics.target_accuracy_met is True

        # Test accuracy below threshold
        low_metrics = ModelMetrics(
            accuracy=0.60, precision=0.6, recall=0.6, f1_score=0.6,
            roc_auc=0.6, average_precision=0.6, matthews_corr=0.2,
            log_loss=0.8, confusion_matrix=[[10, 5], [7, 8]],
            classification_report={}, timestamp=datetime.now().isoformat()
        )
        assert low_metrics.target_accuracy_met is False

    def test_to_dict_conversion(self):
        """Test conversion to dictionary."""
        metrics = ModelMetrics(
            accuracy=0.75, precision=0.73, recall=0.77, f1_score=0.75,
            roc_auc=0.82, average_precision=0.79, matthews_corr=0.48,
            log_loss=0.55, confusion_matrix=[[45, 5], [8, 42]],
            classification_report={}, timestamp=datetime.now().isoformat(),
            model_version="v1.0", dataset_size=100
        )

        metrics_dict = metrics.to_dict()

        assert isinstance(metrics_dict, dict)
        assert metrics_dict['accuracy'] == 0.75
        assert metrics_dict['model_version'] == "v1.0"
        assert metrics_dict['target_accuracy_met'] is True


class TestModelEvaluator:
    """Test ModelEvaluator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.evaluator = ModelEvaluator(target_accuracy=0.65)

        # Create sample prediction data
        np.random.seed(42)
        n_samples = 100

        # Create realistic predictions with some correct/incorrect predictions
        self.y_true = np.random.choice([0, 1], n_samples, p=[0.6, 0.4])

        # Create predictions that are somewhat correlated with true labels
        noise = np.random.normal(0, 0.3, n_samples)
        probabilities = np.clip(self.y_true + noise, 0, 1)
        self.y_pred_proba = probabilities
        self.y_pred = (probabilities > 0.5).astype(int)

    def test_evaluate_model_basic(self):
        """Test basic model evaluation."""
        metrics = self.evaluator.evaluate_model(
            self.y_true, self.y_pred, self.y_pred_proba,
            model_version="test_v1", dataset_name="test_dataset"
        )

        # Check that metrics object is returned
        assert isinstance(metrics, ModelMetrics)

        # Check that all required metrics are calculated
        assert 0 <= metrics.accuracy <= 1
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1
        assert 0 <= metrics.f1_score <= 1
        assert 0 <= metrics.roc_auc <= 1

        # Check metadata
        assert metrics.model_version == "test_v1"
        assert metrics.dataset_size == len(self.y_true)
        assert metrics.timestamp is not None

    def test_evaluate_model_without_probabilities(self):
        """Test evaluation without probability predictions."""
        metrics = self.evaluator.evaluate_model(
            self.y_true, self.y_pred, y_pred_proba=None
        )

        # Should still calculate most metrics
        assert isinstance(metrics, ModelMetrics)
        assert 0 <= metrics.accuracy <= 1
        assert 0 <= metrics.roc_auc <= 1  # Should use binary predictions

        # log_loss should be NaN when no probabilities provided
        assert np.isnan(metrics.log_loss)

    def test_evaluation_history_tracking(self):
        """Test that evaluation history is tracked."""
        # Perform multiple evaluations
        self.evaluator.evaluate_model(self.y_true, self.y_pred, dataset_name="dataset1")
        self.evaluator.evaluate_model(self.y_true, self.y_pred, dataset_name="dataset2")

        # Check that history is maintained
        assert len(self.evaluator.evaluation_history) == 2
        assert self.evaluator.evaluation_history[0]['dataset'] == "dataset1"
        assert self.evaluator.evaluation_history[1]['dataset'] == "dataset2"

    def test_validate_target_accuracy_met(self):
        """Test target accuracy validation when target is met."""
        # Create metrics that meet target accuracy
        metrics = ModelMetrics(
            accuracy=0.70, precision=0.7, recall=0.7, f1_score=0.7,
            roc_auc=0.7, average_precision=0.7, matthews_corr=0.4,
            log_loss=0.6, confusion_matrix=[[10, 2], [3, 15]],
            classification_report={}, timestamp=datetime.now().isoformat()
        )

        validation_result = self.evaluator.validate_target_accuracy(metrics, "test_dataset")

        assert validation_result['target_met'] is True
        assert validation_result['target_accuracy'] == 0.65
        assert validation_result['actual_accuracy'] == 0.70
        assert validation_result['accuracy_gap'] == 0.05

    def test_validate_target_accuracy_not_met(self):
        """Test target accuracy validation when target is not met."""
        # Create metrics that don't meet target accuracy
        metrics = ModelMetrics(
            accuracy=0.60, precision=0.6, recall=0.6, f1_score=0.6,
            roc_auc=0.6, average_precision=0.6, matthews_corr=0.2,
            log_loss=0.8, confusion_matrix=[[10, 5], [7, 8]],
            classification_report={}, timestamp=datetime.now().isoformat()
        )

        validation_result = self.evaluator.validate_target_accuracy(metrics, "test_dataset")

        assert validation_result['target_met'] is False
        assert validation_result['accuracy_gap'] == -0.05

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_create_confusion_matrix_plot(self, mock_subplots, mock_savefig):
        """Test confusion matrix plot creation."""
        # Mock matplotlib
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        metrics = ModelMetrics(
            accuracy=0.75, precision=0.73, recall=0.77, f1_score=0.75,
            roc_auc=0.82, average_precision=0.79, matthews_corr=0.48,
            log_loss=0.55, confusion_matrix=[[45, 5], [8, 42]],
            classification_report={}, timestamp=datetime.now().isoformat()
        )

        # Test plot creation
        fig = self.evaluator.create_confusion_matrix_plot(metrics, save_path="test.png")

        # Check that matplotlib functions were called
        mock_subplots.assert_called_once()
        mock_savefig.assert_called_once_with("test.png", dpi=300, bbox_inches='tight')

        assert fig == mock_fig

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_create_roc_curve_plot(self, mock_subplots, mock_savefig):
        """Test ROC curve plot creation."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        fig = self.evaluator.create_roc_curve_plot(
            self.y_true, self.y_pred_proba, model_name="TestModel", save_path="roc.png"
        )

        mock_subplots.assert_called_once()
        mock_savefig.assert_called_once_with("roc.png", dpi=300, bbox_inches='tight')

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_create_precision_recall_curve_plot(self, mock_subplots, mock_savefig):
        """Test Precision-Recall curve plot creation."""
        mock_fig = Mock()
        mock_ax = Mock()
        mock_subplots.return_value = (mock_fig, mock_ax)

        fig = self.evaluator.create_precision_recall_curve_plot(
            self.y_true, self.y_pred_proba, model_name="TestModel", save_path="pr.png"
        )

        mock_subplots.assert_called_once()
        mock_savefig.assert_called_once_with("pr.png", dpi=300, bbox_inches='tight')

    def test_track_performance_over_time(self):
        """Test performance tracking over time."""
        metrics1 = ModelMetrics(
            accuracy=0.70, precision=0.68, recall=0.72, f1_score=0.70,
            roc_auc=0.75, average_precision=0.73, matthews_corr=0.40,
            log_loss=0.65, confusion_matrix=[[40, 10], [8, 42]],
            classification_report={}, timestamp="2024-01-01T12:00:00"
        )

        metrics2 = ModelMetrics(
            accuracy=0.75, precision=0.73, recall=0.77, f1_score=0.75,
            roc_auc=0.82, average_precision=0.79, matthews_corr=0.48,
            log_loss=0.55, confusion_matrix=[[45, 5], [8, 42]],
            classification_report={}, timestamp="2024-01-02T12:00:00"
        )

        # Track performance
        self.evaluator.track_performance_over_time(metrics1, "v1.0", "test_dataset")
        self.evaluator.track_performance_over_time(metrics2, "v1.0", "test_dataset")

        # Check that trends are tracked
        key = "v1.0_test_dataset"
        assert key in self.evaluator.performance_trends
        assert len(self.evaluator.performance_trends[key]) == 2

        # Check trend data
        trend_data = self.evaluator.performance_trends[key]
        assert trend_data[0]['accuracy'] == 0.70
        assert trend_data[1]['accuracy'] == 0.75

    def test_analyze_performance_trends(self):
        """Test performance trend analysis."""
        # Add some trend data
        metrics_list = [
            (0.65, "2024-01-01T12:00:00"),
            (0.70, "2024-01-02T12:00:00"),
            (0.68, "2024-01-03T12:00:00"),
            (0.75, "2024-01-04T12:00:00")
        ]

        for accuracy, timestamp in metrics_list:
            metrics = ModelMetrics(
                accuracy=accuracy, precision=accuracy-0.02, recall=accuracy+0.02,
                f1_score=accuracy, roc_auc=accuracy+0.05, average_precision=accuracy+0.03,
                matthews_corr=accuracy-0.25, log_loss=1.0-accuracy,
                confusion_matrix=[[40, 10], [8, 42]], classification_report={},
                timestamp=timestamp
            )
            self.evaluator.track_performance_over_time(metrics, "v1.0", "test_dataset")

        # Analyze trends
        analysis = self.evaluator.analyze_performance_trends("v1.0", "test_dataset")

        assert analysis['total_evaluations'] == 4
        assert analysis['latest_accuracy'] == 0.75
        assert analysis['best_accuracy'] == 0.75
        assert analysis['worst_accuracy'] == 0.65
        assert analysis['accuracy_trend'] == 'improving'  # 0.75 > 0.65

        # Check target achievement rate
        target_hits = sum(1 for acc, _ in metrics_list if acc >= 0.65)
        expected_rate = target_hits / len(metrics_list)
        assert analysis['target_achievement_rate'] == expected_rate

    def test_analyze_trends_no_data(self):
        """Test trend analysis with no data."""
        analysis = self.evaluator.analyze_performance_trends("nonexistent", "dataset")
        assert analysis == {}

    def test_consecutive_hits_counting(self):
        """Test consecutive target hits counting."""
        # Test internal method
        hit_sequence = [True, True, False, True, True, True]
        consecutive_hits = self.evaluator._count_consecutive_hits(hit_sequence)
        assert consecutive_hits == 3  # Last 3 are True

        # Test all misses
        miss_sequence = [False, False, False]
        consecutive_hits = self.evaluator._count_consecutive_hits(miss_sequence)
        assert consecutive_hits == 0

        # Test all hits
        all_hits = [True, True, True]
        consecutive_hits = self.evaluator._count_consecutive_hits(all_hits)
        assert consecutive_hits == 3

    def test_generate_performance_report(self):
        """Test comprehensive performance report generation."""
        # Add some evaluation history
        metrics1 = self.evaluator.evaluate_model(self.y_true, self.y_pred, model_version="v1.0")
        metrics2 = self.evaluator.evaluate_model(self.y_true, self.y_pred, model_version="v1.0")

        report = self.evaluator.generate_performance_report(model_version="v1.0")

        # Check report structure
        assert 'summary' in report
        assert 'latest_performance' in report
        assert 'aggregate_stats' in report
        assert 'recommendations' in report

        # Check summary
        assert report['summary']['total_evaluations'] == 2
        assert report['summary']['model_version'] == "v1.0"
        assert report['summary']['target_accuracy'] == 0.65

        # Check aggregate stats
        agg_stats = report['aggregate_stats']
        assert 'mean_accuracy' in agg_stats
        assert 'std_accuracy' in agg_stats
        assert 'max_accuracy' in agg_stats
        assert 'min_accuracy' in agg_stats
        assert 'target_achievement_rate' in agg_stats

    def test_generate_report_no_data(self):
        """Test report generation with no evaluation data."""
        report = self.evaluator.generate_performance_report()
        assert report == {}

    def test_performance_recommendations(self):
        """Test performance recommendation generation."""
        # Create scenario with low accuracy
        low_accuracy_metrics = ModelMetrics(
            accuracy=0.55, precision=0.53, recall=0.57, f1_score=0.55,
            roc_auc=0.60, average_precision=0.58, matthews_corr=0.10,
            log_loss=0.85, confusion_matrix=[[30, 20], [15, 35]],
            classification_report={}, timestamp=datetime.now().isoformat()
        )

        self.evaluator.evaluation_history = [
            {'dataset': 'test', 'metrics': low_accuracy_metrics, 'timestamp': datetime.now().isoformat()}
        ]

        report = self.evaluator.generate_performance_report()
        recommendations = report['recommendations']

        # Should recommend improvement since accuracy < target
        assert len(recommendations) > 0
        assert any('below target' in rec for rec in recommendations)

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_export_metrics_to_json(self, mock_json_dump, mock_file):
        """Test exporting metrics to JSON."""
        # Add evaluation data
        self.evaluator.evaluate_model(self.y_true, self.y_pred, model_version="v1.0")

        # Export metrics
        self.evaluator.export_metrics_to_json("test_metrics.json", model_version="v1.0")

        # Check that file was opened and JSON was written
        mock_file.assert_called_once_with("test_metrics.json", 'w')
        mock_json_dump.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data='{"test": "data"}')
    @patch('json.load')
    def test_load_metrics_from_json(self, mock_json_load, mock_file):
        """Test loading metrics from JSON."""
        mock_json_load.return_value = {"test": "data"}

        loaded_data = self.evaluator.load_metrics_from_json("test_metrics.json")

        mock_file.assert_called_once_with("test_metrics.json", 'r')
        mock_json_load.assert_called_once()
        assert loaded_data == {"test": "data"}


# Integration tests
class TestModelEvaluatorIntegration:
    """Integration tests for model evaluator."""

    def test_end_to_end_evaluation_workflow(self):
        """Test complete evaluation workflow."""
        evaluator = ModelEvaluator(target_accuracy=0.65)

        # Create realistic prediction data
        np.random.seed(42)
        n_samples = 200

        # Create ground truth
        y_true = np.random.choice([0, 1], n_samples, p=[0.7, 0.3])

        # Create predictions with some accuracy
        base_proba = y_true.copy().astype(float)
        noise = np.random.normal(0, 0.2, n_samples)
        y_pred_proba = np.clip(base_proba + noise, 0.01, 0.99)
        y_pred = (y_pred_proba > 0.5).astype(int)

        # Evaluate model
        metrics = evaluator.evaluate_model(
            y_true, y_pred, y_pred_proba,
            model_version="integration_test_v1",
            dataset_name="integration_test"
        )

        # Validate target accuracy
        validation_result = evaluator.validate_target_accuracy(metrics, "integration_test")

        # Track performance
        evaluator.track_performance_over_time(metrics, "integration_test_v1", "integration_test")

        # Generate report
        report = evaluator.generate_performance_report("integration_test_v1")

        # Verify complete workflow
        assert isinstance(metrics, ModelMetrics)
        assert isinstance(validation_result, dict)
        assert 'target_met' in validation_result
        assert len(report) > 0
        assert 'summary' in report

        # Check that accuracy is reasonable
        assert 0.5 <= metrics.accuracy <= 1.0

    def test_evaluation_with_perfect_predictions(self):
        """Test evaluation with perfect predictions."""
        evaluator = ModelEvaluator()

        # Create perfect predictions
        y_true = np.array([0, 0, 1, 1, 0, 1, 1, 0])
        y_pred = y_true.copy()
        y_pred_proba = y_true.astype(float)

        metrics = evaluator.evaluate_model(y_true, y_pred, y_pred_proba)

        # Should achieve perfect scores
        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.roc_auc == 1.0
        assert metrics.target_accuracy_met is True

    def test_evaluation_with_random_predictions(self):
        """Test evaluation with random predictions."""
        evaluator = ModelEvaluator()

        np.random.seed(42)
        n_samples = 1000

        # Create random predictions
        y_true = np.random.choice([0, 1], n_samples, p=[0.5, 0.5])
        y_pred = np.random.choice([0, 1], n_samples, p=[0.5, 0.5])
        y_pred_proba = np.random.uniform(0, 1, n_samples)

        metrics = evaluator.evaluate_model(y_true, y_pred, y_pred_proba)

        # Random predictions should be around 50% accuracy
        assert 0.4 <= metrics.accuracy <= 0.6
        assert 0.4 <= metrics.roc_auc <= 0.6

    def test_evaluation_with_imbalanced_data(self):
        """Test evaluation with highly imbalanced data."""
        evaluator = ModelEvaluator()

        # Create imbalanced dataset (90% class 0, 10% class 1)
        n_samples = 1000
        y_true = np.random.choice([0, 1], n_samples, p=[0.9, 0.1])

        # Create predictions that are biased toward majority class
        y_pred_proba = np.random.beta(2, 8, n_samples)  # Skewed toward 0
        y_pred = (y_pred_proba > 0.5).astype(int)

        metrics = evaluator.evaluate_model(y_true, y_pred, y_pred_proba)

        # Should handle imbalanced data without errors
        assert 0 <= metrics.accuracy <= 1
        assert 0 <= metrics.precision <= 1
        assert 0 <= metrics.recall <= 1

        # Check confusion matrix dimensions
        assert len(metrics.confusion_matrix) == 2
        assert len(metrics.confusion_matrix[0]) == 2


if __name__ == "__main__":
    pytest.main([__file__])