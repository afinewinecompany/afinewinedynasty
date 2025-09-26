"""
Temporal cross-validation strategy for time-series ML data.
Prevents data leakage by respecting temporal ordering.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Iterator, Any
from datetime import datetime, timedelta
from sklearn.model_selection import BaseCrossValidator
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


class TemporalSplit(BaseCrossValidator):
    """Custom temporal cross-validation split that respects time ordering."""

    def __init__(self, n_splits: int = 5, max_train_size: Optional[int] = None,
                 test_size: Optional[int] = None, gap: int = 0):
        """
        Initialize temporal cross-validation splitter.

        Args:
            n_splits: Number of splits
            max_train_size: Maximum training set size per split
            test_size: Test set size per split
            gap: Gap between train and test sets (number of samples)
        """
        self.n_splits = n_splits
        self.max_train_size = max_train_size
        self.test_size = test_size
        self.gap = gap

    def split(self, X: pd.DataFrame, y: Optional[pd.Series] = None,
              groups: Optional[pd.Series] = None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate indices for temporal splits.

        Args:
            X: Feature DataFrame with temporal index/column
            y: Target variable (optional)
            groups: Group labels (not used in temporal split)

        Yields:
            Tuple of (train_indices, test_indices)
        """
        n_samples = len(X)

        # Determine test size
        if self.test_size is None:
            test_size = n_samples // (self.n_splits + 1)
        else:
            test_size = self.test_size

        # Generate splits
        for i in range(self.n_splits):
            # Test set end index
            test_end = n_samples - i * test_size
            test_start = test_end - test_size

            if test_start <= 0:
                break

            # Training set end (with gap)
            train_end = test_start - self.gap

            if train_end <= 0:
                break

            # Training set start
            if self.max_train_size is None:
                train_start = 0
            else:
                train_start = max(0, train_end - self.max_train_size)

            # Generate indices
            train_indices = np.arange(train_start, train_end)
            test_indices = np.arange(test_start, test_end)

            yield train_indices, test_indices

    def get_n_splits(self, X: Optional[pd.DataFrame] = None,
                     y: Optional[pd.Series] = None,
                     groups: Optional[pd.Series] = None) -> int:
        """Return number of splits."""
        return self.n_splits


class RollingWindowValidator:
    """Rolling window cross-validation for temporal data."""

    def __init__(self, window_size: int, step_size: int = 1,
                 min_train_size: int = 100):
        """
        Initialize rolling window validator.

        Args:
            window_size: Size of each training window
            step_size: Step size between windows
            min_train_size: Minimum training set size
        """
        self.window_size = window_size
        self.step_size = step_size
        self.min_train_size = min_train_size

    def split(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate rolling window splits.

        Args:
            X: Feature DataFrame
            y: Target variable (optional)

        Yields:
            Tuple of (train_indices, test_indices)
        """
        n_samples = len(X)

        # Start with minimum training size
        start_idx = self.min_train_size

        while start_idx < n_samples:
            # Training window
            train_start = max(0, start_idx - self.window_size)
            train_end = start_idx

            # Test window (next step_size samples)
            test_start = start_idx
            test_end = min(n_samples, start_idx + self.step_size)

            if test_end <= test_start:
                break

            train_indices = np.arange(train_start, train_end)
            test_indices = np.arange(test_start, test_end)

            yield train_indices, test_indices

            start_idx += self.step_size


class TemporalValidationStrategy:
    """Complete temporal validation strategy with multiple approaches."""

    def __init__(self):
        self.validation_results = {}
        self.split_performance = []

    def validate_with_temporal_splits(self, X: pd.DataFrame, y: pd.Series,
                                     model, n_splits: int = 5,
                                     test_size: Optional[int] = None,
                                     gap: int = 0) -> Dict[str, Any]:
        """
        Validate model using temporal splits.

        Args:
            X: Feature DataFrame
            y: Target variable
            model: Model to validate (must have fit/predict methods)
            n_splits: Number of temporal splits
            test_size: Test set size per split
            gap: Gap between train and test sets

        Returns:
            Dictionary with validation results
        """
        logger.info(f"Running temporal cross-validation with {n_splits} splits")

        # Sort data by temporal column if available
        if 'date_recorded' in X.columns:
            sort_indices = X.sort_values('date_recorded').index
            X_sorted = X.loc[sort_indices]
            y_sorted = y.loc[sort_indices]
        else:
            X_sorted = X
            y_sorted = y

        # Initialize temporal splitter
        ts_cv = TemporalSplit(n_splits=n_splits, test_size=test_size, gap=gap)

        # Store results for each split
        fold_results = []
        feature_importances = []

        for fold, (train_idx, test_idx) in enumerate(ts_cv.split(X_sorted)):
            logger.info(f"Processing temporal fold {fold + 1}/{n_splits}")

            # Split data
            X_train_fold = X_sorted.iloc[train_idx]
            X_test_fold = X_sorted.iloc[test_idx]
            y_train_fold = y_sorted.iloc[train_idx]
            y_test_fold = y_sorted.iloc[test_idx]

            # Train model
            model_copy = self._clone_model(model)
            model_copy.fit(X_train_fold, y_train_fold)

            # Predict
            y_pred = model_copy.predict(X_test_fold)
            y_pred_proba = model_copy.predict_proba(X_test_fold)[:, 1]

            # Calculate metrics
            fold_metrics = {
                'fold': fold + 1,
                'train_size': len(train_idx),
                'test_size': len(test_idx),
                'accuracy': accuracy_score(y_test_fold, y_pred),
                'precision': precision_score(y_test_fold, y_pred, average='binary'),
                'recall': recall_score(y_test_fold, y_pred, average='binary'),
                'f1': f1_score(y_test_fold, y_pred, average='binary'),
                'roc_auc': roc_auc_score(y_test_fold, y_pred_proba)
            }

            # Store feature importance if available
            if hasattr(model_copy, 'feature_importances_'):
                feature_importances.append(model_copy.feature_importances_)

            fold_results.append(fold_metrics)

        # Aggregate results
        metrics_df = pd.DataFrame(fold_results)

        aggregated_results = {
            'mean_accuracy': metrics_df['accuracy'].mean(),
            'std_accuracy': metrics_df['accuracy'].std(),
            'mean_precision': metrics_df['precision'].mean(),
            'std_precision': metrics_df['precision'].std(),
            'mean_recall': metrics_df['recall'].mean(),
            'std_recall': metrics_df['recall'].std(),
            'mean_f1': metrics_df['f1'].mean(),
            'std_f1': metrics_df['f1'].std(),
            'mean_roc_auc': metrics_df['roc_auc'].mean(),
            'std_roc_auc': metrics_df['roc_auc'].std(),
            'fold_results': fold_results,
            'target_accuracy_met': metrics_df['accuracy'].mean() >= 0.65
        }

        # Feature importance analysis
        if feature_importances:
            mean_importance = np.mean(feature_importances, axis=0)
            aggregated_results['feature_importance'] = dict(zip(
                X_sorted.columns, mean_importance
            ))

        self.validation_results['temporal_splits'] = aggregated_results

        logger.info(f"Temporal validation completed. Mean accuracy: {aggregated_results['mean_accuracy']:.4f} "
                   f"(±{aggregated_results['std_accuracy']:.4f})")

        return aggregated_results

    def validate_with_rolling_window(self, X: pd.DataFrame, y: pd.Series,
                                    model, window_size: int = 1000,
                                    step_size: int = 100) -> Dict[str, Any]:
        """
        Validate model using rolling window approach.

        Args:
            X: Feature DataFrame
            y: Target variable
            model: Model to validate
            window_size: Size of training window
            step_size: Step size between windows

        Returns:
            Dictionary with validation results
        """
        logger.info(f"Running rolling window validation (window={window_size}, step={step_size})")

        # Sort data by temporal column if available
        if 'date_recorded' in X.columns:
            sort_indices = X.sort_values('date_recorded').index
            X_sorted = X.loc[sort_indices]
            y_sorted = y.loc[sort_indices]
        else:
            X_sorted = X
            y_sorted = y

        # Initialize rolling window validator
        rw_validator = RollingWindowValidator(
            window_size=window_size,
            step_size=step_size,
            min_train_size=min(500, len(X_sorted) // 4)
        )

        # Store results for each window
        window_results = []

        for window, (train_idx, test_idx) in enumerate(rw_validator.split(X_sorted)):
            logger.info(f"Processing rolling window {window + 1}")

            # Split data
            X_train_window = X_sorted.iloc[train_idx]
            X_test_window = X_sorted.iloc[test_idx]
            y_train_window = y_sorted.iloc[train_idx]
            y_test_window = y_sorted.iloc[test_idx]

            # Train model
            model_copy = self._clone_model(model)
            model_copy.fit(X_train_window, y_train_window)

            # Predict
            y_pred = model_copy.predict(X_test_window)
            y_pred_proba = model_copy.predict_proba(X_test_window)[:, 1]

            # Calculate metrics
            window_metrics = {
                'window': window + 1,
                'train_size': len(train_idx),
                'test_size': len(test_idx),
                'accuracy': accuracy_score(y_test_window, y_pred),
                'precision': precision_score(y_test_window, y_pred, average='binary'),
                'recall': recall_score(y_test_window, y_pred, average='binary'),
                'f1': f1_score(y_test_window, y_pred, average='binary'),
                'roc_auc': roc_auc_score(y_test_window, y_pred_proba)
            }

            window_results.append(window_metrics)

        # Aggregate results
        metrics_df = pd.DataFrame(window_results)

        aggregated_results = {
            'mean_accuracy': metrics_df['accuracy'].mean(),
            'std_accuracy': metrics_df['accuracy'].std(),
            'mean_precision': metrics_df['precision'].mean(),
            'std_precision': metrics_df['precision'].std(),
            'mean_recall': metrics_df['recall'].mean(),
            'std_recall': metrics_df['recall'].std(),
            'mean_f1': metrics_df['f1'].mean(),
            'std_f1': metrics_df['f1'].std(),
            'mean_roc_auc': metrics_df['roc_auc'].mean(),
            'std_roc_auc': metrics_df['roc_auc'].std(),
            'window_results': window_results,
            'target_accuracy_met': metrics_df['accuracy'].mean() >= 0.65,
            'total_windows': len(window_results)
        }

        self.validation_results['rolling_window'] = aggregated_results

        logger.info(f"Rolling window validation completed. Mean accuracy: {aggregated_results['mean_accuracy']:.4f} "
                   f"(±{aggregated_results['std_accuracy']:.4f})")

        return aggregated_results

    def compare_validation_strategies(self, X: pd.DataFrame, y: pd.Series,
                                     model) -> Dict[str, Any]:
        """
        Compare different validation strategies.

        Args:
            X: Feature DataFrame
            y: Target variable
            model: Model to validate

        Returns:
            Dictionary with comparison results
        """
        logger.info("Comparing temporal validation strategies")

        results = {}

        # Temporal splits validation
        temporal_results = self.validate_with_temporal_splits(
            X, y, model, n_splits=5
        )
        results['temporal_splits'] = temporal_results

        # Rolling window validation
        rolling_results = self.validate_with_rolling_window(
            X, y, model, window_size=min(1000, len(X) // 3)
        )
        results['rolling_window'] = rolling_results

        # Comparison summary
        comparison = {
            'temporal_splits_accuracy': temporal_results['mean_accuracy'],
            'rolling_window_accuracy': rolling_results['mean_accuracy'],
            'temporal_splits_std': temporal_results['std_accuracy'],
            'rolling_window_std': rolling_results['std_accuracy'],
            'best_strategy': 'temporal_splits' if temporal_results['mean_accuracy'] > rolling_results['mean_accuracy'] else 'rolling_window'
        }

        results['comparison'] = comparison

        self.validation_results['comparison'] = results

        logger.info(f"Validation strategy comparison completed. "
                   f"Best strategy: {comparison['best_strategy']}")

        return results

    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""

        if not self.validation_results:
            raise ValueError("No validation results available. Run validation first.")

        report = {
            'summary': {
                'total_validations_run': len(self.validation_results),
                'validation_methods': list(self.validation_results.keys()),
                'timestamp': datetime.now().isoformat()
            },
            'results': self.validation_results,
            'recommendations': self._generate_recommendations()
        }

        return report

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        if 'comparison' in self.validation_results:
            comparison = self.validation_results['comparison']['comparison']
            best_strategy = comparison['best_strategy']
            best_accuracy = comparison[f'{best_strategy}_accuracy']

            recommendations.append(
                f"Use {best_strategy.replace('_', ' ')} strategy for final model validation "
                f"(accuracy: {best_accuracy:.4f})"
            )

            if best_accuracy < 0.65:
                recommendations.append(
                    "Target accuracy of 65% not achieved. Consider:"
                    "\n- Feature engineering improvements"
                    "\n- Hyperparameter tuning"
                    "\n- Different model architectures"
                    "\n- More training data"
                )

        return recommendations

    def _clone_model(self, model):
        """Create a copy of the model for cross-validation."""
        from sklearn.base import clone
        try:
            return clone(model)
        except Exception:
            # Fallback for non-sklearn models
            from copy import deepcopy
            return deepcopy(model)

    def create_validation_dashboard(self, save_path: Optional[str] = None) -> None:
        """
        Create validation performance dashboard.

        Args:
            save_path: Path to save the dashboard plot
        """
        if not self.validation_results:
            logger.warning("No validation results to plot")
            return

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Temporal Validation Results Dashboard', fontsize=16)

        # Plot 1: Temporal splits performance over folds
        if 'temporal_splits' in self.validation_results:
            fold_results = pd.DataFrame(
                self.validation_results['temporal_splits']['fold_results']
            )

            axes[0, 0].plot(fold_results['fold'], fold_results['accuracy'], 'o-', label='Accuracy')
            axes[0, 0].plot(fold_results['fold'], fold_results['roc_auc'], 's-', label='ROC AUC')
            axes[0, 0].axhline(y=0.65, color='red', linestyle='--', label='Target (65%)')
            axes[0, 0].set_xlabel('Fold')
            axes[0, 0].set_ylabel('Score')
            axes[0, 0].set_title('Temporal Splits Performance')
            axes[0, 0].legend()
            axes[0, 0].grid(True)

        # Plot 2: Rolling window performance
        if 'rolling_window' in self.validation_results:
            window_results = pd.DataFrame(
                self.validation_results['rolling_window']['window_results']
            )

            axes[0, 1].plot(window_results['window'], window_results['accuracy'], 'o-', label='Accuracy')
            axes[0, 1].plot(window_results['window'], window_results['roc_auc'], 's-', label='ROC AUC')
            axes[0, 1].axhline(y=0.65, color='red', linestyle='--', label='Target (65%)')
            axes[0, 1].set_xlabel('Window')
            axes[0, 1].set_ylabel('Score')
            axes[0, 1].set_title('Rolling Window Performance')
            axes[0, 1].legend()
            axes[0, 1].grid(True)

        # Plot 3: Strategy comparison
        if 'comparison' in self.validation_results:
            strategies = ['temporal_splits', 'rolling_window']
            accuracies = [
                self.validation_results['temporal_splits']['mean_accuracy'],
                self.validation_results['rolling_window']['mean_accuracy']
            ]
            stds = [
                self.validation_results['temporal_splits']['std_accuracy'],
                self.validation_results['rolling_window']['std_accuracy']
            ]

            x_pos = np.arange(len(strategies))
            axes[1, 0].bar(x_pos, accuracies, yerr=stds, capsize=5)
            axes[1, 0].axhline(y=0.65, color='red', linestyle='--', label='Target (65%)')
            axes[1, 0].set_xlabel('Validation Strategy')
            axes[1, 0].set_ylabel('Mean Accuracy')
            axes[1, 0].set_title('Strategy Comparison')
            axes[1, 0].set_xticks(x_pos)
            axes[1, 0].set_xticklabels([s.replace('_', ' ').title() for s in strategies])
            axes[1, 0].legend()
            axes[1, 0].grid(True)

        # Plot 4: Performance metrics comparison
        if 'temporal_splits' in self.validation_results:
            metrics = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']
            values = [
                self.validation_results['temporal_splits'][f'mean_{metric}']
                for metric in metrics
            ]

            axes[1, 1].bar(metrics, values)
            axes[1, 1].axhline(y=0.65, color='red', linestyle='--', label='Target (65%)')
            axes[1, 1].set_xlabel('Metric')
            axes[1, 1].set_ylabel('Score')
            axes[1, 1].set_title('Performance Metrics')
            axes[1, 1].tick_params(axis='x', rotation=45)
            axes[1, 1].legend()
            axes[1, 1].grid(True)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Validation dashboard saved to {save_path}")

        return fig