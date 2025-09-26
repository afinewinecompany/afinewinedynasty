"""
A/B Testing Framework for model version comparison.
Implements traffic splitting, statistical significance testing, and champion/challenger selection.
"""

import logging
import hashlib
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import chi2_contingency, mannwhitneyu, ttest_ind
import matplotlib.pyplot as plt
import seaborn as sns

from app.ml.model_registry import ModelVersioningSystem
from app.ml.evaluation import ModelEvaluator

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """A/B test status enumeration."""
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"


class SplitStrategy(Enum):
    """Traffic splitting strategy enumeration."""
    RANDOM = "random"
    HASH_BASED = "hash_based"
    GEOGRAPHIC = "geographic"
    TEMPORAL = "temporal"


@dataclass
class ABTestConfig:
    """A/B test configuration."""
    test_name: str
    description: str
    champion_model: str
    challenger_model: str
    traffic_split_ratio: float  # Percentage for challenger (0.0 to 1.0)
    split_strategy: SplitStrategy
    minimum_sample_size: int
    minimum_test_duration_days: int
    maximum_test_duration_days: int
    significance_level: float
    power: float
    early_stopping_enabled: bool
    success_metrics: List[str]
    guardrail_metrics: Dict[str, Dict[str, float]]  # metric -> {threshold, direction}


@dataclass
class ABTestResult:
    """A/B test result data."""
    test_name: str
    start_time: str
    end_time: Optional[str]
    status: TestStatus
    total_samples: int
    champion_samples: int
    challenger_samples: int
    champion_metrics: Dict[str, float]
    challenger_metrics: Dict[str, float]
    statistical_results: Dict[str, Any]
    confidence_intervals: Dict[str, Dict[str, float]]
    recommendation: str
    winner: Optional[str]


class TrafficSplitter:
    """Traffic splitting logic for A/B tests."""

    def __init__(self, test_config: ABTestConfig):
        self.config = test_config
        random.seed(42)  # For reproducible splits

    def assign_variant(self, user_id: str, request_context: Dict[str, Any]) -> str:
        """
        Assign a user to champion or challenger variant.

        Args:
            user_id: Unique identifier for the user/request
            request_context: Additional context for assignment

        Returns:
            'champion' or 'challenger'
        """
        if self.config.split_strategy == SplitStrategy.HASH_BASED:
            return self._hash_based_assignment(user_id)
        elif self.config.split_strategy == SplitStrategy.RANDOM:
            return self._random_assignment()
        elif self.config.split_strategy == SplitStrategy.GEOGRAPHIC:
            return self._geographic_assignment(request_context)
        elif self.config.split_strategy == SplitStrategy.TEMPORAL:
            return self._temporal_assignment()
        else:
            return self._hash_based_assignment(user_id)

    def _hash_based_assignment(self, user_id: str) -> str:
        """Hash-based consistent assignment."""
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        threshold = self.config.traffic_split_ratio * (2 ** 32)
        return "challenger" if (hash_value % (2 ** 32)) < threshold else "champion"

    def _random_assignment(self) -> str:
        """Random assignment (not consistent across requests)."""
        return "challenger" if random.random() < self.config.traffic_split_ratio else "champion"

    def _geographic_assignment(self, context: Dict[str, Any]) -> str:
        """Geographic-based assignment."""
        # Example: assign based on geographic region
        region = context.get('region', 'unknown')
        challenger_regions = ['west', 'northeast']  # Example regions for challenger
        return "challenger" if region in challenger_regions else "champion"

    def _temporal_assignment(self) -> str:
        """Time-based assignment."""
        # Example: alternate by hour
        current_hour = datetime.now().hour
        return "challenger" if current_hour % 2 == 0 else "champion"


class StatisticalAnalyzer:
    """Statistical analysis for A/B test results."""

    def __init__(self, significance_level: float = 0.05):
        self.significance_level = significance_level

    def analyze_test_results(self, champion_data: pd.DataFrame,
                           challenger_data: pd.DataFrame,
                           metrics: List[str]) -> Dict[str, Any]:
        """
        Perform comprehensive statistical analysis of A/B test results.

        Args:
            champion_data: DataFrame with champion model results
            challenger_data: DataFrame with challenger model results
            metrics: List of metrics to analyze

        Returns:
            Dictionary with statistical analysis results
        """
        logger.info("Performing statistical analysis of A/B test results")

        results = {
            'sample_sizes': {
                'champion': len(champion_data),
                'challenger': len(challenger_data)
            },
            'metric_analysis': {},
            'overall_significance': False,
            'power_analysis': {},
            'effect_sizes': {}
        }

        for metric in metrics:
            if metric not in champion_data.columns or metric not in challenger_data.columns:
                logger.warning(f"Metric {metric} not found in data")
                continue

            metric_results = self._analyze_metric(
                champion_data[metric].dropna(),
                challenger_data[metric].dropna(),
                metric
            )
            results['metric_analysis'][metric] = metric_results

        # Determine overall significance
        significant_metrics = [
            metric for metric, analysis in results['metric_analysis'].items()
            if analysis.get('is_significant', False)
        ]
        results['overall_significance'] = len(significant_metrics) > 0
        results['significant_metrics'] = significant_metrics

        return results

    def _analyze_metric(self, champion_values: pd.Series,
                       challenger_values: pd.Series,
                       metric_name: str) -> Dict[str, Any]:
        """Analyze a specific metric."""

        # Basic statistics
        champion_stats = {
            'mean': float(champion_values.mean()),
            'std': float(champion_values.std()),
            'count': len(champion_values),
            'median': float(champion_values.median())
        }

        challenger_stats = {
            'mean': float(challenger_values.mean()),
            'std': float(challenger_values.std()),
            'count': len(challenger_values),
            'median': float(challenger_values.median())
        }

        # Effect size (Cohen's d for continuous metrics)
        pooled_std = np.sqrt(((len(champion_values) - 1) * champion_stats['std'] ** 2 +
                             (len(challenger_values) - 1) * challenger_stats['std'] ** 2) /
                            (len(champion_values) + len(challenger_values) - 2))

        cohens_d = (challenger_stats['mean'] - champion_stats['mean']) / pooled_std if pooled_std > 0 else 0

        # Statistical test
        if self._is_binary_metric(champion_values, challenger_values):
            # Chi-square test for binary metrics
            test_result = self._chi_square_test(champion_values, challenger_values)
        else:
            # T-test for continuous metrics
            test_result = self._t_test(champion_values, challenger_values)

        # Confidence interval
        confidence_interval = self._calculate_confidence_interval(
            champion_values, challenger_values
        )

        return {
            'champion_stats': champion_stats,
            'challenger_stats': challenger_stats,
            'effect_size_cohens_d': float(cohens_d),
            'statistical_test': test_result,
            'confidence_interval': confidence_interval,
            'is_significant': test_result['p_value'] < self.significance_level,
            'improvement': float(challenger_stats['mean'] - champion_stats['mean']),
            'improvement_pct': float((challenger_stats['mean'] - champion_stats['mean']) /
                                   champion_stats['mean'] * 100) if champion_stats['mean'] != 0 else 0
        }

    def _is_binary_metric(self, series1: pd.Series, series2: pd.Series) -> bool:
        """Check if metric is binary (only 0s and 1s)."""
        combined = pd.concat([series1, series2])
        unique_values = set(combined.dropna().unique())
        return unique_values.issubset({0, 1, 0.0, 1.0})

    def _chi_square_test(self, champion_values: pd.Series,
                        challenger_values: pd.Series) -> Dict[str, Any]:
        """Perform chi-square test for binary metrics."""
        # Create contingency table
        champion_success = (champion_values == 1).sum()
        champion_total = len(champion_values)
        challenger_success = (challenger_values == 1).sum()
        challenger_total = len(challenger_values)

        contingency_table = np.array([
            [champion_success, champion_total - champion_success],
            [challenger_success, challenger_total - challenger_success]
        ])

        chi2, p_value, dof, expected = chi2_contingency(contingency_table)

        return {
            'test_type': 'chi_square',
            'chi2_statistic': float(chi2),
            'p_value': float(p_value),
            'degrees_of_freedom': dof,
            'contingency_table': contingency_table.tolist()
        }

    def _t_test(self, champion_values: pd.Series,
               challenger_values: pd.Series) -> Dict[str, Any]:
        """Perform t-test for continuous metrics."""
        # Welch's t-test (unequal variances)
        t_stat, p_value = ttest_ind(challenger_values, champion_values, equal_var=False)

        return {
            'test_type': 't_test',
            't_statistic': float(t_stat),
            'p_value': float(p_value)
        }

    def _calculate_confidence_interval(self, champion_values: pd.Series,
                                     challenger_values: pd.Series,
                                     confidence_level: float = 0.95) -> Dict[str, float]:
        """Calculate confidence interval for the difference in means."""
        alpha = 1 - confidence_level

        champion_mean = champion_values.mean()
        challenger_mean = challenger_values.mean()
        champion_std = champion_values.std()
        challenger_std = challenger_values.std()
        champion_n = len(champion_values)
        challenger_n = len(challenger_values)

        # Standard error of difference
        se_diff = np.sqrt((champion_std ** 2 / champion_n) + (challenger_std ** 2 / challenger_n))

        # Degrees of freedom (Welch's formula)
        df = ((champion_std ** 2 / champion_n) + (challenger_std ** 2 / challenger_n)) ** 2 / \
             (((champion_std ** 2 / champion_n) ** 2 / (champion_n - 1)) +
              ((challenger_std ** 2 / challenger_n) ** 2 / (challenger_n - 1)))

        # Critical value
        t_critical = stats.t.ppf(1 - alpha / 2, df)

        # Difference and margin of error
        diff = challenger_mean - champion_mean
        margin_of_error = t_critical * se_diff

        return {
            'difference': float(diff),
            'lower_bound': float(diff - margin_of_error),
            'upper_bound': float(diff + margin_of_error),
            'confidence_level': confidence_level
        }

    def calculate_required_sample_size(self, effect_size: float,
                                     power: float = 0.8,
                                     significance_level: float = 0.05) -> int:
        """
        Calculate required sample size for detecting an effect.

        Args:
            effect_size: Expected effect size (Cohen's d)
            power: Statistical power (1 - β)
            significance_level: Type I error rate (α)

        Returns:
            Required sample size per group
        """
        # Using Cohen's formula for sample size calculation
        z_alpha = stats.norm.ppf(1 - significance_level / 2)
        z_beta = stats.norm.ppf(power)

        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2

        return int(np.ceil(n))


class GuardrailMonitor:
    """Monitor guardrail metrics during A/B tests."""

    def __init__(self, guardrail_config: Dict[str, Dict[str, float]]):
        """
        Initialize guardrail monitor.

        Args:
            guardrail_config: Dictionary with guardrail thresholds
                             {metric: {'threshold': value, 'direction': 'increase'/'decrease'}}
        """
        self.guardrail_config = guardrail_config

    def check_guardrails(self, challenger_metrics: Dict[str, float],
                        champion_metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        Check if challenger violates any guardrail metrics.

        Args:
            challenger_metrics: Challenger model metrics
            champion_metrics: Champion model metrics

        Returns:
            Dictionary with guardrail check results
        """
        violations = []
        passed_checks = []

        for metric, config in self.guardrail_config.items():
            if metric not in challenger_metrics or metric not in champion_metrics:
                continue

            challenger_value = challenger_metrics[metric]
            champion_value = champion_metrics[metric]
            threshold = config['threshold']
            direction = config['direction']

            # Calculate relative change
            relative_change = (challenger_value - champion_value) / champion_value if champion_value != 0 else 0

            # Check violation based on direction
            is_violation = False
            if direction == 'decrease' and relative_change < -threshold:
                is_violation = True
            elif direction == 'increase' and relative_change > threshold:
                is_violation = True

            check_result = {
                'metric': metric,
                'champion_value': champion_value,
                'challenger_value': challenger_value,
                'relative_change': relative_change,
                'threshold': threshold,
                'direction': direction,
                'is_violation': is_violation
            }

            if is_violation:
                violations.append(check_result)
            else:
                passed_checks.append(check_result)

        return {
            'has_violations': len(violations) > 0,
            'violations': violations,
            'passed_checks': passed_checks,
            'total_checks': len(violations) + len(passed_checks)
        }


class ABTestManager:
    """A/B test management and execution."""

    def __init__(self, versioning_system: ModelVersioningSystem):
        self.versioning_system = versioning_system
        self.active_tests: Dict[str, ABTestConfig] = {}
        self.test_results: Dict[str, ABTestResult] = {}
        self.test_data: Dict[str, Dict[str, pd.DataFrame]] = {}  # {test_name: {variant: data}}

    def create_test(self, config: ABTestConfig) -> str:
        """
        Create a new A/B test.

        Args:
            config: A/B test configuration

        Returns:
            Test ID
        """
        logger.info(f"Creating A/B test: {config.test_name}")

        # Validate models exist
        try:
            self.versioning_system.mlflow_registry.get_model_version(config.champion_model)
            self.versioning_system.mlflow_registry.get_model_version(config.challenger_model)
        except Exception as e:
            raise ValueError(f"Model validation failed: {e}")

        # Store test configuration
        self.active_tests[config.test_name] = config
        self.test_data[config.test_name] = {'champion': pd.DataFrame(), 'challenger': pd.DataFrame()}

        logger.info(f"A/B test {config.test_name} created successfully")
        return config.test_name

    def assign_and_predict(self, test_name: str, user_id: str,
                          features: pd.DataFrame,
                          request_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Assign user to variant and make prediction.

        Args:
            test_name: Name of the A/B test
            user_id: User identifier
            features: Input features for prediction
            request_context: Additional context

        Returns:
            Dictionary with variant assignment and prediction
        """
        if test_name not in self.active_tests:
            raise ValueError(f"Test {test_name} not found")

        config = self.active_tests[test_name]
        splitter = TrafficSplitter(config)

        # Assign variant
        variant = splitter.assign_variant(user_id, request_context or {})

        # Get appropriate model
        model_name = config.champion_model if variant == 'champion' else config.challenger_model

        try:
            # Load model and make prediction
            model = self.versioning_system.mlflow_registry.load_model(model_name)
            prediction = model.predict(features)
            prediction_proba = model.predict_proba(features) if hasattr(model, 'predict_proba') else None

            return {
                'test_name': test_name,
                'user_id': user_id,
                'variant': variant,
                'model_name': model_name,
                'prediction': prediction.tolist() if hasattr(prediction, 'tolist') else prediction,
                'prediction_proba': prediction_proba.tolist() if prediction_proba is not None else None,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Prediction failed for test {test_name}, variant {variant}: {e}")
            raise

    def record_outcome(self, test_name: str, user_id: str, variant: str,
                      outcome_metrics: Dict[str, float]) -> None:
        """
        Record outcome metrics for a test user.

        Args:
            test_name: Name of the A/B test
            user_id: User identifier
            variant: Assigned variant
            outcome_metrics: Observed outcome metrics
        """
        if test_name not in self.test_data:
            raise ValueError(f"Test {test_name} not found")

        # Create outcome record
        outcome_record = {
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            **outcome_metrics
        }

        # Add to appropriate variant data
        variant_df = self.test_data[test_name][variant]
        new_row = pd.DataFrame([outcome_record])
        self.test_data[test_name][variant] = pd.concat([variant_df, new_row], ignore_index=True)

        logger.debug(f"Recorded outcome for test {test_name}, variant {variant}, user {user_id}")

    def analyze_test(self, test_name: str) -> ABTestResult:
        """
        Analyze A/B test results and generate recommendations.

        Args:
            test_name: Name of the A/B test

        Returns:
            ABTestResult with analysis
        """
        if test_name not in self.active_tests:
            raise ValueError(f"Test {test_name} not found")

        config = self.active_tests[test_name]
        champion_data = self.test_data[test_name]['champion']
        challenger_data = self.test_data[test_name]['challenger']

        logger.info(f"Analyzing A/B test {test_name}")

        # Perform statistical analysis
        analyzer = StatisticalAnalyzer(config.significance_level)
        statistical_results = analyzer.analyze_test_results(
            champion_data, challenger_data, config.success_metrics
        )

        # Calculate aggregate metrics
        champion_metrics = self._calculate_aggregate_metrics(champion_data, config.success_metrics)
        challenger_metrics = self._calculate_aggregate_metrics(challenger_data, config.success_metrics)

        # Check guardrails
        guardrail_monitor = GuardrailMonitor(config.guardrail_metrics)
        guardrail_results = guardrail_monitor.check_guardrails(challenger_metrics, champion_metrics)

        # Generate recommendation
        recommendation, winner = self._generate_recommendation(
            statistical_results, guardrail_results, config
        )

        # Create test result
        result = ABTestResult(
            test_name=test_name,
            start_time=datetime.now().isoformat(),  # Should track actual start time
            end_time=None,
            status=TestStatus.RUNNING,
            total_samples=len(champion_data) + len(challenger_data),
            champion_samples=len(champion_data),
            challenger_samples=len(challenger_data),
            champion_metrics=champion_metrics,
            challenger_metrics=challenger_metrics,
            statistical_results=statistical_results,
            confidence_intervals={},  # Would be filled from statistical_results
            recommendation=recommendation,
            winner=winner
        )

        self.test_results[test_name] = result
        return result

    def _calculate_aggregate_metrics(self, data: pd.DataFrame, metrics: List[str]) -> Dict[str, float]:
        """Calculate aggregate metrics for a variant."""
        aggregate_metrics = {}

        for metric in metrics:
            if metric in data.columns:
                aggregate_metrics[metric] = float(data[metric].mean())

        return aggregate_metrics

    def _generate_recommendation(self, statistical_results: Dict[str, Any],
                               guardrail_results: Dict[str, Any],
                               config: ABTestConfig) -> Tuple[str, Optional[str]]:
        """Generate recommendation based on analysis."""

        # Check for guardrail violations
        if guardrail_results['has_violations']:
            return "Stop test - Guardrail violations detected", "champion"

        # Check sample size
        total_samples = statistical_results['sample_sizes']['champion'] + \
                       statistical_results['sample_sizes']['challenger']
        if total_samples < config.minimum_sample_size:
            return "Continue test - Insufficient sample size", None

        # Check for statistical significance
        if not statistical_results['overall_significance']:
            return "Continue test - No significant difference detected", None

        # Determine winner based on primary success metrics
        significant_improvements = 0
        for metric in config.success_metrics:
            if metric in statistical_results['metric_analysis']:
                analysis = statistical_results['metric_analysis'][metric]
                if analysis['is_significant'] and analysis['improvement'] > 0:
                    significant_improvements += 1

        if significant_improvements > 0:
            return "Promote challenger - Significant improvement detected", "challenger"
        else:
            return "Promote champion - Challenger shows no improvement", "champion"

    def stop_test(self, test_name: str, reason: str = "Manual stop") -> ABTestResult:
        """
        Stop an A/B test and finalize results.

        Args:
            test_name: Name of the test to stop
            reason: Reason for stopping

        Returns:
            Final test result
        """
        if test_name not in self.active_tests:
            raise ValueError(f"Test {test_name} not found")

        # Perform final analysis
        result = self.analyze_test(test_name)
        result.status = TestStatus.COMPLETED
        result.end_time = datetime.now().isoformat()

        # Remove from active tests
        del self.active_tests[test_name]

        logger.info(f"A/B test {test_name} stopped. Reason: {reason}")
        return result

    def get_test_status(self, test_name: str) -> Dict[str, Any]:
        """Get current status of an A/B test."""
        if test_name not in self.active_tests:
            return {'error': f'Test {test_name} not found'}

        config = self.active_tests[test_name]
        champion_samples = len(self.test_data[test_name]['champion'])
        challenger_samples = len(self.test_data[test_name]['challenger'])

        return {
            'test_name': test_name,
            'status': 'running',
            'champion_model': config.champion_model,
            'challenger_model': config.challenger_model,
            'traffic_split_ratio': config.traffic_split_ratio,
            'champion_samples': champion_samples,
            'challenger_samples': challenger_samples,
            'total_samples': champion_samples + challenger_samples,
            'minimum_sample_size': config.minimum_sample_size,
            'sample_size_progress': (champion_samples + challenger_samples) / config.minimum_sample_size,
            'config': asdict(config)
        }

    def list_active_tests(self) -> List[Dict[str, Any]]:
        """List all active A/B tests."""
        return [self.get_test_status(test_name) for test_name in self.active_tests.keys()]

    def export_test_results(self, test_name: str, filepath: str) -> None:
        """Export test results to JSON file."""
        if test_name not in self.test_results:
            raise ValueError(f"No results found for test {test_name}")

        result = self.test_results[test_name]
        export_data = {
            'result': asdict(result),
            'champion_data': self.test_data[test_name]['champion'].to_dict('records'),
            'challenger_data': self.test_data[test_name]['challenger'].to_dict('records'),
            'export_timestamp': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Test results exported to {filepath}")

    def create_visualization(self, test_name: str, save_path: Optional[str] = None) -> plt.Figure:
        """
        Create visualization of A/B test results.

        Args:
            test_name: Name of the test
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        if test_name not in self.test_results:
            raise ValueError(f"No results found for test {test_name}")

        result = self.test_results[test_name]
        config = self.active_tests.get(test_name)

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'A/B Test Results: {test_name}', fontsize=16)

        # Plot 1: Sample sizes
        variants = ['Champion', 'Challenger']
        sample_sizes = [result.champion_samples, result.challenger_samples]
        axes[0, 0].bar(variants, sample_sizes, color=['blue', 'orange'])
        axes[0, 0].set_title('Sample Sizes')
        axes[0, 0].set_ylabel('Number of Samples')

        # Plot 2: Metric comparison
        if config and config.success_metrics:
            metric = config.success_metrics[0]  # Use first success metric
            champion_value = result.champion_metrics.get(metric, 0)
            challenger_value = result.challenger_metrics.get(metric, 0)

            axes[0, 1].bar(variants, [champion_value, challenger_value], color=['blue', 'orange'])
            axes[0, 1].set_title(f'Metric Comparison: {metric}')
            axes[0, 1].set_ylabel(metric)

        # Plot 3: Statistical significance
        significant_metrics = result.statistical_results.get('significant_metrics', [])
        total_metrics = len(config.success_metrics) if config else 1

        axes[1, 0].pie([len(significant_metrics), total_metrics - len(significant_metrics)],
                      labels=['Significant', 'Not Significant'],
                      colors=['green', 'red'],
                      autopct='%1.1f%%')
        axes[1, 0].set_title('Statistical Significance')

        # Plot 4: Recommendation
        axes[1, 1].text(0.5, 0.5, f"Recommendation:\n{result.recommendation}",
                       ha='center', va='center', fontsize=12,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='lightblue'))
        axes[1, 1].set_xlim(0, 1)
        axes[1, 1].set_ylim(0, 1)
        axes[1, 1].axis('off')
        axes[1, 1].set_title('Recommendation')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"A/B test visualization saved to {save_path}")

        return fig