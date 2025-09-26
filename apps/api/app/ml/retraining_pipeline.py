"""
Automated model retraining pipeline with scheduling and monitoring.
Implements weekly retraining during active seasons with performance tracking.
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.ml.training_pipeline import ModelTrainingPipeline
from app.ml.evaluation import ModelEvaluator
from app.ml.model_registry import ModelVersioningSystem
from app.ml.temporal_validation import TemporalValidationStrategy
from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class RetrainingConfig:
    """Configuration for automated retraining."""
    model_name: str
    schedule_type: str  # 'weekly', 'monthly', 'custom'
    active_season_months: List[int]  # Months when active (e.g., [3, 4, 5, 6, 7, 8, 9, 10])
    min_training_data_size: int
    performance_threshold: float
    max_training_time_hours: int
    hyperparameter_tuning: str  # 'none', 'grid_search', 'optuna'
    notification_endpoints: List[str]
    auto_promote_threshold: float


@dataclass
class RetrainingResult:
    """Result of a retraining run."""
    start_time: str
    end_time: str
    status: str  # 'success', 'failed', 'skipped'
    model_version: Optional[str]
    previous_model_version: Optional[str]
    performance_metrics: Dict[str, float]
    improvement_metrics: Dict[str, float]
    training_data_size: int
    error_message: Optional[str]
    promoted_to_production: bool


class SeasonalScheduler:
    """Seasonal scheduling logic for model retraining."""

    def __init__(self, active_season_months: List[int]):
        """
        Initialize seasonal scheduler.

        Args:
            active_season_months: List of months (1-12) when retraining is active
        """
        self.active_season_months = active_season_months

    def is_active_season(self, date: Optional[datetime] = None) -> bool:
        """Check if current date is in active season."""
        if date is None:
            date = datetime.now()
        return date.month in self.active_season_months

    def next_retraining_date(self, last_training_date: Optional[datetime] = None,
                           schedule_type: str = 'weekly') -> datetime:
        """
        Calculate next retraining date.

        Args:
            last_training_date: Date of last training
            schedule_type: Scheduling frequency ('weekly', 'monthly')

        Returns:
            Next scheduled retraining date
        """
        if last_training_date is None:
            last_training_date = datetime.now()

        if schedule_type == 'weekly':
            next_date = last_training_date + timedelta(days=7)
        elif schedule_type == 'monthly':
            next_date = last_training_date + timedelta(days=30)
        else:
            next_date = last_training_date + timedelta(days=7)  # Default weekly

        # If next date is not in active season, find next active season
        if not self.is_active_season(next_date):
            next_date = self._find_next_active_season_start(next_date)

        return next_date

    def _find_next_active_season_start(self, from_date: datetime) -> datetime:
        """Find the start of the next active season."""
        current_date = from_date
        while not self.is_active_season(current_date):
            current_date += timedelta(days=1)
            # Prevent infinite loop
            if (current_date - from_date).days > 365:
                break
        return current_date

    def days_until_next_training(self, last_training_date: Optional[datetime] = None,
                                schedule_type: str = 'weekly') -> int:
        """Calculate days until next training."""
        next_date = self.next_retraining_date(last_training_date, schedule_type)
        return (next_date - datetime.now()).days


class DataFreshnessChecker:
    """Check data freshness and quality for retraining."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def check_data_freshness(self, min_data_size: int = 1000) -> Dict[str, Any]:
        """
        Check if training data is fresh and sufficient.

        Args:
            min_data_size: Minimum required data size

        Returns:
            Dictionary with data freshness information
        """
        logger.info("Checking data freshness for retraining")

        try:
            # Query recent data
            recent_data_query = text("""
                SELECT COUNT(*) as total_records,
                       MAX(date_recorded) as latest_date,
                       MIN(date_recorded) as earliest_date
                FROM prospects
                WHERE date_recorded > NOW() - INTERVAL 90 DAY
            """)

            result = self.db_session.execute(recent_data_query).fetchone()

            freshness_info = {
                'total_recent_records': result.total_records if result else 0,
                'latest_date': result.latest_date.isoformat() if result and result.latest_date else None,
                'earliest_date': result.earliest_date.isoformat() if result and result.earliest_date else None,
                'meets_minimum_size': (result.total_records if result else 0) >= min_data_size,
                'data_age_days': (datetime.now() - result.latest_date).days if result and result.latest_date else None,
                'check_timestamp': datetime.now().isoformat()
            }

            logger.info(f"Data freshness check: {freshness_info['total_recent_records']} records, "
                       f"latest: {freshness_info['latest_date']}")

            return freshness_info

        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return {
                'total_recent_records': 0,
                'meets_minimum_size': False,
                'error': str(e),
                'check_timestamp': datetime.now().isoformat()
            }

    def get_training_data(self) -> pd.DataFrame:
        """Fetch fresh training data from database."""
        logger.info("Fetching training data for retraining")

        try:
            # Query to get comprehensive training data
            training_data_query = text("""
                SELECT p.*, ps.*, sg.*
                FROM prospects p
                LEFT JOIN prospect_stats ps ON p.mlb_id = ps.mlb_id
                LEFT JOIN scouting_grades sg ON p.mlb_id = sg.mlb_id
                WHERE p.date_recorded > NOW() - INTERVAL 365 DAY
                ORDER BY p.date_recorded DESC
            """)

            df = pd.read_sql(training_data_query, self.db_session.bind)

            logger.info(f"Retrieved {len(df)} records for training")
            return df

        except Exception as e:
            logger.error(f"Error fetching training data: {e}")
            raise


class PerformanceMonitor:
    """Monitor model performance and detect degradation."""

    def __init__(self, performance_threshold: float = 0.05):
        """
        Initialize performance monitor.

        Args:
            performance_threshold: Threshold for performance degradation detection
        """
        self.performance_threshold = performance_threshold

    def compare_model_performance(self, current_metrics: Dict[str, float],
                                 previous_metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        Compare current model performance with previous version.

        Args:
            current_metrics: Current model performance metrics
            previous_metrics: Previous model performance metrics

        Returns:
            Dictionary with performance comparison results
        """
        logger.info("Comparing model performance")

        improvements = {}
        degradations = {}

        for metric in current_metrics:
            if metric in previous_metrics:
                current_value = current_metrics[metric]
                previous_value = previous_metrics[metric]
                change = current_value - previous_value
                change_pct = (change / previous_value) * 100 if previous_value != 0 else 0

                if change > 0:
                    improvements[metric] = {
                        'current': current_value,
                        'previous': previous_value,
                        'change': change,
                        'change_pct': change_pct
                    }
                elif abs(change) > self.performance_threshold:
                    degradations[metric] = {
                        'current': current_value,
                        'previous': previous_value,
                        'change': change,
                        'change_pct': change_pct
                    }

        comparison_result = {
            'improvements': improvements,
            'degradations': degradations,
            'overall_improvement': len(improvements) > len(degradations),
            'significant_degradation': any(
                abs(d['change']) > self.performance_threshold
                for d in degradations.values()
            ),
            'comparison_timestamp': datetime.now().isoformat()
        }

        logger.info(f"Performance comparison: {len(improvements)} improvements, "
                   f"{len(degradations)} degradations")

        return comparison_result

    def should_promote_model(self, performance_comparison: Dict[str, Any],
                           auto_promote_threshold: float = 0.02) -> bool:
        """
        Determine if new model should be promoted to production.

        Args:
            performance_comparison: Performance comparison results
            auto_promote_threshold: Minimum improvement for auto-promotion

        Returns:
            True if model should be promoted
        """
        if not performance_comparison['overall_improvement']:
            return False

        if performance_comparison['significant_degradation']:
            return False

        # Check if accuracy improvement meets threshold
        accuracy_improvement = performance_comparison['improvements'].get('accuracy', {})
        if accuracy_improvement and accuracy_improvement['change'] >= auto_promote_threshold:
            return True

        return False


class AutomatedRetrainingPipeline:
    """Complete automated retraining pipeline with scheduling and monitoring."""

    def __init__(self, config: RetrainingConfig,
                 db_session: Session,
                 versioning_system: ModelVersioningSystem):
        """
        Initialize automated retraining pipeline.

        Args:
            config: Retraining configuration
            db_session: Database session
            versioning_system: Model versioning system
        """
        self.config = config
        self.db_session = db_session
        self.versioning_system = versioning_system

        # Initialize components
        self.scheduler = SeasonalScheduler(config.active_season_months)
        self.data_checker = DataFreshnessChecker(db_session)
        self.performance_monitor = PerformanceMonitor(config.performance_threshold)
        self.training_pipeline = ModelTrainingPipeline()
        self.evaluator = ModelEvaluator(target_accuracy=0.65)

        # State tracking
        self.retraining_history: List[RetrainingResult] = []
        self.is_running = False

        logger.info(f"Automated retraining pipeline initialized for model: {config.model_name}")

    async def run_scheduled_retraining(self) -> RetrainingResult:
        """
        Run a scheduled retraining cycle.

        Returns:
            RetrainingResult with details of the retraining run
        """
        start_time = datetime.now()
        logger.info(f"Starting scheduled retraining for {self.config.model_name}")

        try:
            self.is_running = True

            # Check if retraining should run
            should_run, skip_reason = self._should_run_retraining()
            if not should_run:
                result = RetrainingResult(
                    start_time=start_time.isoformat(),
                    end_time=datetime.now().isoformat(),
                    status='skipped',
                    model_version=None,
                    previous_model_version=None,
                    performance_metrics={},
                    improvement_metrics={},
                    training_data_size=0,
                    error_message=skip_reason,
                    promoted_to_production=False
                )
                self.retraining_history.append(result)
                return result

            # Get current production model metrics for comparison
            previous_metrics = await self._get_production_model_metrics()

            # Fetch fresh training data
            training_data = self.data_checker.get_training_data()

            # Create target variable (example: MLB success prediction)
            training_data['mlb_success'] = self._create_target_variable(training_data)

            # Prepare training data
            data_splits = self.training_pipeline.prepare_training_data(
                training_data, 'mlb_success', temporal_split=True
            )

            # Train new model
            training_results = self.training_pipeline.train_model(
                data_splits,
                hyperparameter_tuning=self.config.hyperparameter_tuning,
                tuning_trials=50
            )

            # Register new model version
            model = self.training_pipeline.get_model()
            run_id = self.versioning_system.register_model_version(
                self.config.model_name,
                model.model,
                training_results,
                data_splits['feature_names'],
                model.best_params or model.get_default_params(),
                tags={'retraining': 'automated', 'season': str(datetime.now().year)}
            )

            # Get new model version
            new_version = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Compare performance
            current_metrics = training_results['test_results']
            performance_comparison = self.performance_monitor.compare_model_performance(
                current_metrics, previous_metrics
            )

            # Decide on promotion
            should_promote = self.performance_monitor.should_promote_model(
                performance_comparison, self.config.auto_promote_threshold
            )

            promoted = False
            if should_promote:
                self.versioning_system.promote_to_production(self.config.model_name, new_version)
                promoted = True
                logger.info(f"Model {self.config.model_name} v{new_version} promoted to production")

            # Create result
            result = RetrainingResult(
                start_time=start_time.isoformat(),
                end_time=datetime.now().isoformat(),
                status='success',
                model_version=new_version,
                previous_model_version=self._get_previous_version(),
                performance_metrics=current_metrics,
                improvement_metrics=performance_comparison,
                training_data_size=len(training_data),
                error_message=None,
                promoted_to_production=promoted
            )

            self.retraining_history.append(result)

            # Send notifications
            await self._send_notifications(result)

            logger.info(f"Retraining completed successfully for {self.config.model_name}")
            return result

        except Exception as e:
            logger.error(f"Retraining failed: {e}")

            error_result = RetrainingResult(
                start_time=start_time.isoformat(),
                end_time=datetime.now().isoformat(),
                status='failed',
                model_version=None,
                previous_model_version=self._get_previous_version(),
                performance_metrics={},
                improvement_metrics={},
                training_data_size=0,
                error_message=str(e),
                promoted_to_production=False
            )

            self.retraining_history.append(error_result)
            await self._send_failure_notifications(error_result)
            return error_result

        finally:
            self.is_running = False

    def _should_run_retraining(self) -> Tuple[bool, Optional[str]]:
        """Check if retraining should run."""

        # Check if already running
        if self.is_running:
            return False, "Retraining already in progress"

        # Check active season
        if not self.scheduler.is_active_season():
            return False, "Not in active season"

        # Check data freshness
        freshness_info = self.data_checker.check_data_freshness(
            self.config.min_training_data_size
        )
        if not freshness_info['meets_minimum_size']:
            return False, f"Insufficient training data: {freshness_info['total_recent_records']}"

        return True, None

    def _create_target_variable(self, df: pd.DataFrame) -> pd.Series:
        """Create target variable for MLB success prediction."""
        # Example implementation - adjust based on your data structure
        # MLB success: players who reached MLB and had >500 PA or >100 IP within 4 years

        # This is a simplified version - you would implement based on your actual data
        target = pd.Series(0, index=df.index)

        # Example logic (adjust to your data structure)
        if 'level' in df.columns and 'age' in df.columns:
            # Simplified target: prospects who reached high levels at young age
            target = ((df['level'] == 'MLB') |
                     ((df['level'] == 'Triple-A') & (df['age'] <= 24)) |
                     ((df['level'] == 'Double-A') & (df['age'] <= 22))).astype(int)

        return target

    async def _get_production_model_metrics(self) -> Dict[str, float]:
        """Get metrics from current production model."""
        try:
            # Get current production model info
            production_info = self.versioning_system.mlflow_registry.get_model_version(
                self.config.model_name, "production"
            )

            # Get run metrics
            run = self.versioning_system.mlflow_registry.client.get_run(production_info['run_id'])
            return run.data.metrics

        except Exception as e:
            logger.warning(f"Could not get production model metrics: {e}")
            return {}

    def _get_previous_version(self) -> Optional[str]:
        """Get previous model version."""
        try:
            production_info = self.versioning_system.mlflow_registry.get_model_version(
                self.config.model_name, "production"
            )
            return production_info['version']
        except Exception:
            return None

    async def _send_notifications(self, result: RetrainingResult) -> None:
        """Send notifications about retraining results."""
        if not self.config.notification_endpoints:
            return

        notification_data = {
            'model_name': self.config.model_name,
            'result': asdict(result),
            'timestamp': datetime.now().isoformat()
        }

        # Implementation would depend on notification system (email, Slack, webhooks, etc.)
        logger.info(f"Sending retraining notifications: {notification_data}")

    async def _send_failure_notifications(self, result: RetrainingResult) -> None:
        """Send failure notifications."""
        if not self.config.notification_endpoints:
            return

        # Implementation for failure-specific notifications
        logger.error(f"Sending failure notifications for {self.config.model_name}")

    def schedule_next_retraining(self) -> datetime:
        """Schedule next retraining run."""
        last_training = None
        if self.retraining_history:
            last_successful = [r for r in self.retraining_history if r.status == 'success']
            if last_successful:
                last_training = datetime.fromisoformat(last_successful[-1].start_time)

        return self.scheduler.next_retraining_date(last_training, self.config.schedule_type)

    def get_retraining_status(self) -> Dict[str, Any]:
        """Get current retraining pipeline status."""
        next_training = self.schedule_next_retraining()
        days_until_next = (next_training - datetime.now()).days

        status = {
            'model_name': self.config.model_name,
            'is_running': self.is_running,
            'is_active_season': self.scheduler.is_active_season(),
            'next_retraining_date': next_training.isoformat(),
            'days_until_next_training': days_until_next,
            'total_retraining_runs': len(self.retraining_history),
            'successful_runs': len([r for r in self.retraining_history if r.status == 'success']),
            'failed_runs': len([r for r in self.retraining_history if r.status == 'failed']),
            'last_run': self.retraining_history[-1] if self.retraining_history else None,
            'config': asdict(self.config)
        }

        return status

    def export_retraining_history(self, filepath: str) -> None:
        """Export retraining history to JSON file."""
        history_data = {
            'model_name': self.config.model_name,
            'config': asdict(self.config),
            'retraining_history': [asdict(result) for result in self.retraining_history],
            'export_timestamp': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(history_data, f, indent=2, default=str)

        logger.info(f"Retraining history exported to {filepath}")


class RetrainingOrchestrator:
    """Orchestrator for managing multiple automated retraining pipelines."""

    def __init__(self, db_session: Session, versioning_system: ModelVersioningSystem):
        self.db_session = db_session
        self.versioning_system = versioning_system
        self.pipelines: Dict[str, AutomatedRetrainingPipeline] = {}

    def add_pipeline(self, config: RetrainingConfig) -> None:
        """Add a new retraining pipeline."""
        pipeline = AutomatedRetrainingPipeline(
            config, self.db_session, self.versioning_system
        )
        self.pipelines[config.model_name] = pipeline
        logger.info(f"Added retraining pipeline for {config.model_name}")

    async def run_all_scheduled_retraining(self) -> Dict[str, RetrainingResult]:
        """Run all scheduled retraining pipelines."""
        results = {}

        for model_name, pipeline in self.pipelines.items():
            try:
                result = await pipeline.run_scheduled_retraining()
                results[model_name] = result
            except Exception as e:
                logger.error(f"Error running retraining for {model_name}: {e}")

        return results

    def get_all_pipeline_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all retraining pipelines."""
        return {
            model_name: pipeline.get_retraining_status()
            for model_name, pipeline in self.pipelines.items()
        }