"""
Model evaluation and metrics tracking system.
Implements comprehensive performance tracking with 65%+ accuracy validation.
"""

import logging
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    roc_curve, precision_recall_curve, confusion_matrix, classification_report,
    average_precision_score, matthews_corrcoef, log_loss
)
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Data class for storing model performance metrics."""

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    average_precision: float
    matthews_corr: float
    log_loss: float
    confusion_matrix: List[List[int]]
    classification_report: Dict[str, Any]
    timestamp: str
    model_version: Optional[str] = None
    dataset_size: Optional[int] = None
    target_accuracy_met: Optional[bool] = None

    def __post_init__(self):
        """Post-initialization to set derived fields."""
        if self.target_accuracy_met is None:
            self.target_accuracy_met = self.accuracy >= 0.65

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ModelEvaluator:
    """Comprehensive model evaluation system."""

    def __init__(self, target_accuracy: float = 0.65):
        self.target_accuracy = target_accuracy
        self.evaluation_history = []
        self.performance_trends = {}

    def evaluate_model(self, y_true: np.ndarray, y_pred: np.ndarray,
                      y_pred_proba: Optional[np.ndarray] = None,
                      model_version: Optional[str] = None,
                      dataset_name: str = "default") -> ModelMetrics:
        """
        Comprehensive model evaluation.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_pred_proba: Predicted probabilities (optional)
            model_version: Model version identifier
            dataset_name: Name of the dataset being evaluated

        Returns:
            ModelMetrics object with all evaluation results
        """
        logger.info(f"Evaluating model performance on {dataset_name} dataset")

        # Basic classification metrics
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average='binary', zero_division=0)
        recall = recall_score(y_true, y_pred, average='binary', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='binary', zero_division=0)

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred).tolist()

        # Classification report
        class_report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)

        # Probability-based metrics (if probabilities available)
        if y_pred_proba is not None:
            roc_auc = roc_auc_score(y_true, y_pred_proba)
            avg_precision = average_precision_score(y_true, y_pred_proba)
            logloss = log_loss(y_true, y_pred_proba)
        else:
            roc_auc = roc_auc_score(y_true, y_pred)
            avg_precision = average_precision_score(y_true, y_pred)
            logloss = float('nan')

        # Matthews correlation coefficient
        mcc = matthews_corrcoef(y_true, y_pred)

        # Create metrics object
        metrics = ModelMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            roc_auc=roc_auc,
            average_precision=avg_precision,
            matthews_corr=mcc,
            log_loss=logloss,
            confusion_matrix=cm,
            classification_report=class_report,
            timestamp=datetime.now().isoformat(),
            model_version=model_version,
            dataset_size=len(y_true)
        )

        # Store in history
        self.evaluation_history.append({
            'dataset': dataset_name,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        })

        # Log key metrics
        logger.info(f"Evaluation results for {dataset_name}:")
        logger.info(f"  Accuracy: {accuracy:.4f} (Target: {self.target_accuracy:.2f})")
        logger.info(f"  Precision: {precision:.4f}")
        logger.info(f"  Recall: {recall:.4f}")
        logger.info(f"  F1-Score: {f1:.4f}")
        logger.info(f"  ROC AUC: {roc_auc:.4f}")
        logger.info(f"  Target accuracy met: {metrics.target_accuracy_met}")

        return metrics

    def validate_target_accuracy(self, metrics: ModelMetrics,
                                dataset_name: str = "default") -> Dict[str, Any]:
        """
        Validate that model meets target accuracy requirements.

        Args:
            metrics: ModelMetrics object
            dataset_name: Name of the dataset

        Returns:
            Dictionary with validation results
        """
        target_met = metrics.accuracy >= self.target_accuracy
        accuracy_gap = metrics.accuracy - self.target_accuracy

        validation_result = {
            'target_accuracy': self.target_accuracy,
            'actual_accuracy': metrics.accuracy,
            'target_met': target_met,
            'accuracy_gap': accuracy_gap,
            'dataset': dataset_name,
            'timestamp': datetime.now().isoformat()
        }

        if target_met:
            logger.info(f"✓ Target accuracy achieved: {metrics.accuracy:.4f} >= {self.target_accuracy:.2f}")
        else:
            logger.warning(f"✗ Target accuracy not met: {metrics.accuracy:.4f} < {self.target_accuracy:.2f} "
                         f"(gap: {-accuracy_gap:.4f})")

        return validation_result

    def create_confusion_matrix_plot(self, metrics: ModelMetrics,
                                   class_names: Optional[List[str]] = None,
                                   save_path: Optional[str] = None) -> plt.Figure:
        """
        Create confusion matrix visualization.

        Args:
            metrics: ModelMetrics object
            class_names: Custom class names for display
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        if class_names is None:
            class_names = ['Not MLB Success', 'MLB Success']

        fig, ax = plt.subplots(figsize=(8, 6))

        # Create heatmap
        cm_array = np.array(metrics.confusion_matrix)
        sns.heatmap(cm_array, annot=True, fmt='d', cmap='Blues',
                   xticklabels=class_names, yticklabels=class_names, ax=ax)

        ax.set_title(f'Confusion Matrix\nAccuracy: {metrics.accuracy:.4f}')
        ax.set_xlabel('Predicted Label')
        ax.set_ylabel('True Label')

        # Add target accuracy indicator
        target_text = "✓ Target Met" if metrics.target_accuracy_met else "✗ Target Not Met"
        ax.text(0.02, 0.98, target_text, transform=ax.transAxes,
               bbox=dict(boxstyle="round,pad=0.3",
                        facecolor='green' if metrics.target_accuracy_met else 'red',
                        alpha=0.7),
               verticalalignment='top')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Confusion matrix plot saved to {save_path}")

        return fig

    def create_roc_curve_plot(self, y_true: np.ndarray, y_pred_proba: np.ndarray,
                             model_name: str = "Model",
                             save_path: Optional[str] = None) -> plt.Figure:
        """
        Create ROC curve visualization.

        Args:
            y_true: True labels
            y_pred_proba: Predicted probabilities
            model_name: Name for the model in the plot
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        # Calculate ROC curve
        fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba)
        auc_score = roc_auc_score(y_true, y_pred_proba)

        fig, ax = plt.subplots(figsize=(8, 6))

        # Plot ROC curve
        ax.plot(fpr, tpr, color='darkorange', lw=2,
               label=f'{model_name} (AUC = {auc_score:.4f})')

        # Plot diagonal reference line
        ax.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', alpha=0.8)

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        ax.set_title('Receiver Operating Characteristic (ROC) Curve')
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"ROC curve plot saved to {save_path}")

        return fig

    def create_precision_recall_curve_plot(self, y_true: np.ndarray, y_pred_proba: np.ndarray,
                                          model_name: str = "Model",
                                          save_path: Optional[str] = None) -> plt.Figure:
        """
        Create Precision-Recall curve visualization.

        Args:
            y_true: True labels
            y_pred_proba: Predicted probabilities
            model_name: Name for the model in the plot
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        # Calculate Precision-Recall curve
        precision, recall, thresholds = precision_recall_curve(y_true, y_pred_proba)
        avg_precision = average_precision_score(y_true, y_pred_proba)

        fig, ax = plt.subplots(figsize=(8, 6))

        # Plot PR curve
        ax.plot(recall, precision, color='blue', lw=2,
               label=f'{model_name} (AP = {avg_precision:.4f})')

        # Plot baseline
        baseline = np.sum(y_true) / len(y_true)
        ax.axhline(y=baseline, color='red', linestyle='--', alpha=0.8,
                  label=f'Baseline (AP = {baseline:.4f})')

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('Recall')
        ax.set_ylabel('Precision')
        ax.set_title('Precision-Recall Curve')
        ax.legend(loc="lower left")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Precision-Recall curve plot saved to {save_path}")

        return fig

    def track_performance_over_time(self, metrics: ModelMetrics,
                                   model_version: str,
                                   dataset_name: str = "default") -> None:
        """
        Track model performance trends over time.

        Args:
            metrics: ModelMetrics object
            model_version: Model version identifier
            dataset_name: Name of the dataset
        """
        key = f"{model_version}_{dataset_name}"

        if key not in self.performance_trends:
            self.performance_trends[key] = []

        trend_entry = {
            'timestamp': metrics.timestamp,
            'accuracy': metrics.accuracy,
            'precision': metrics.precision,
            'recall': metrics.recall,
            'f1_score': metrics.f1_score,
            'roc_auc': metrics.roc_auc,
            'target_met': metrics.target_accuracy_met
        }

        self.performance_trends[key].append(trend_entry)

        logger.info(f"Performance tracked for {key}: Accuracy={metrics.accuracy:.4f}")

    def analyze_performance_trends(self, model_version: str,
                                 dataset_name: str = "default") -> Dict[str, Any]:
        """
        Analyze performance trends for a specific model and dataset.

        Args:
            model_version: Model version identifier
            dataset_name: Name of the dataset

        Returns:
            Dictionary with trend analysis results
        """
        key = f"{model_version}_{dataset_name}"

        if key not in self.performance_trends or not self.performance_trends[key]:
            logger.warning(f"No performance trends found for {key}")
            return {}

        trends = self.performance_trends[key]
        df = pd.DataFrame(trends)

        # Calculate trend statistics
        analysis = {
            'total_evaluations': len(trends),
            'latest_accuracy': df['accuracy'].iloc[-1],
            'best_accuracy': df['accuracy'].max(),
            'worst_accuracy': df['accuracy'].min(),
            'accuracy_trend': 'improving' if df['accuracy'].iloc[-1] > df['accuracy'].iloc[0] else 'declining',
            'target_achievement_rate': df['target_met'].mean(),
            'consecutive_target_hits': self._count_consecutive_hits(df['target_met'].tolist()),
            'performance_stability': df['accuracy'].std(),
            'first_evaluation': df['timestamp'].iloc[0],
            'latest_evaluation': df['timestamp'].iloc[-1]
        }

        logger.info(f"Trend analysis for {key}: "
                   f"Latest={analysis['latest_accuracy']:.4f}, "
                   f"Best={analysis['best_accuracy']:.4f}, "
                   f"Trend={analysis['accuracy_trend']}")

        return analysis

    def _count_consecutive_hits(self, target_hits: List[bool]) -> int:
        """Count consecutive target accuracy hits from the end."""
        count = 0
        for hit in reversed(target_hits):
            if hit:
                count += 1
            else:
                break
        return count

    def generate_performance_report(self, model_version: Optional[str] = None,
                                  include_plots: bool = True) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.

        Args:
            model_version: Specific model version to report on (None for all)
            include_plots: Whether to include plot data

        Returns:
            Dictionary with comprehensive performance report
        """
        logger.info("Generating comprehensive performance report")

        # Filter evaluations by model version if specified
        evaluations = self.evaluation_history
        if model_version:
            evaluations = [e for e in evaluations if
                         e['metrics'].model_version == model_version]

        if not evaluations:
            logger.warning("No evaluations found for report generation")
            return {}

        # Aggregate metrics
        latest_eval = evaluations[-1]
        all_metrics = [e['metrics'] for e in evaluations]

        report = {
            'summary': {
                'total_evaluations': len(evaluations),
                'model_version': model_version or 'all_versions',
                'target_accuracy': self.target_accuracy,
                'report_timestamp': datetime.now().isoformat()
            },
            'latest_performance': latest_eval['metrics'].to_dict(),
            'aggregate_stats': {
                'mean_accuracy': np.mean([m.accuracy for m in all_metrics]),
                'std_accuracy': np.std([m.accuracy for m in all_metrics]),
                'max_accuracy': max([m.accuracy for m in all_metrics]),
                'min_accuracy': min([m.accuracy for m in all_metrics]),
                'target_achievement_rate': np.mean([m.target_accuracy_met for m in all_metrics])
            },
            'performance_trends': self.performance_trends
        }

        # Add recommendations
        report['recommendations'] = self._generate_performance_recommendations(report)

        logger.info(f"Performance report generated with {len(evaluations)} evaluations")
        return report

    def _generate_performance_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on performance analysis."""
        recommendations = []

        latest_accuracy = report['latest_performance']['accuracy']
        target_rate = report['aggregate_stats']['target_achievement_rate']
        accuracy_std = report['aggregate_stats']['std_accuracy']

        # Target accuracy recommendations
        if latest_accuracy < self.target_accuracy:
            gap = self.target_accuracy - latest_accuracy
            recommendations.append(
                f"Current accuracy ({latest_accuracy:.4f}) is below target ({self.target_accuracy:.2f}). "
                f"Gap: {gap:.4f}. Consider hyperparameter tuning or feature engineering."
            )

        # Consistency recommendations
        if accuracy_std > 0.05:
            recommendations.append(
                f"High performance variability (std: {accuracy_std:.4f}). "
                "Consider stabilizing the model with regularization or more data."
            )

        # Achievement rate recommendations
        if target_rate < 0.8:
            recommendations.append(
                f"Target achievement rate is low ({target_rate:.2%}). "
                "Consider model architecture changes or data quality improvements."
            )

        # Success recommendations
        if latest_accuracy >= self.target_accuracy and target_rate >= 0.8:
            recommendations.append(
                "Model performance is meeting targets consistently. "
                "Consider deploying to production or A/B testing."
            )

        return recommendations

    def export_metrics_to_json(self, filepath: str,
                              model_version: Optional[str] = None) -> None:
        """
        Export metrics to JSON file.

        Args:
            filepath: Path to save JSON file
            model_version: Specific model version to export (None for all)
        """
        report = self.generate_performance_report(model_version, include_plots=False)

        # Convert numpy types to Python types for JSON serialization
        def convert_numpy(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        # Process the report recursively
        def process_dict(d):
            if isinstance(d, dict):
                return {k: process_dict(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [process_dict(item) for item in d]
            else:
                return convert_numpy(d)

        processed_report = process_dict(report)

        with open(filepath, 'w') as f:
            json.dump(processed_report, f, indent=2)

        logger.info(f"Metrics exported to {filepath}")

    def load_metrics_from_json(self, filepath: str) -> Dict[str, Any]:
        """
        Load metrics from JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            Dictionary with loaded metrics
        """
        with open(filepath, 'r') as f:
            metrics_data = json.load(f)

        logger.info(f"Metrics loaded from {filepath}")
        return metrics_data