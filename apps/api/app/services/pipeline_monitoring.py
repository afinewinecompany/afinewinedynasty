"""
Pipeline monitoring and alerting service.
Tracks data quality, performance metrics, and pipeline health.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
from sqlalchemy import create_engine, text
import psutil
import time

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PipelineStatus(Enum):
    """Pipeline execution status."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    STALLED = "stalled"


class DataSource(Enum):
    """Data source identifiers."""
    MLB_API = "mlb_api"
    FANGRAPHS = "fangraphs"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class AlertManager:
    """Manage and send alerts for pipeline issues."""

    def __init__(self):
        self.alert_history = []
        self.email_enabled = False  # Set via config
        self.slack_enabled = False  # Set via config

    async def send_alert(self, level: AlertLevel, message: str):
        """Send alert through configured channels."""
        alert = {
            'level': level.value,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }

        self.alert_history.append(alert)

        # Log the alert
        if level == AlertLevel.CRITICAL:
            logger.critical(f"ALERT: {message}")
        elif level == AlertLevel.ERROR:
            logger.error(f"ALERT: {message}")
        elif level == AlertLevel.WARNING:
            logger.warning(f"ALERT: {message}")
        else:
            logger.info(f"ALERT: {message}")

        # Send email if configured
        if self.email_enabled and level in [AlertLevel.CRITICAL, AlertLevel.ERROR]:
            await self._send_email_alert(alert)

        # Send Slack notification if configured
        if self.slack_enabled:
            await self._send_slack_alert(alert)

    async def _send_email_alert(self, alert: Dict):
        """Send email alert (placeholder for implementation)."""
        # Email implementation would go here
        pass

    async def _send_slack_alert(self, alert: Dict):
        """Send Slack alert (placeholder for implementation)."""
        # Slack implementation would go here
        pass


class DataQualityMonitor:
    """Monitor data quality metrics and issues."""

    def __init__(self):
        self.quality_thresholds = {
            'completeness': 0.95,  # 95% of fields should be non-null
            'freshness_hours': 24,  # Data should be updated within 24 hours
            'duplicate_rate': 0.01,  # Less than 1% duplicates
            'outlier_rate': 0.05,  # Less than 5% outliers
        }
        self.alerts = []

    def check_data_completeness(self) -> Dict[str, Any]:
        """Check for missing data in critical fields."""
        db = next(get_db())
        results = {}

        try:
            # Check prospects table completeness
            query = text("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(mlb_id) as has_mlb_id,
                    COUNT(name) as has_name,
                    COUNT(position) as has_position,
                    COUNT(organization) as has_organization,
                    COUNT(level) as has_level
                FROM prospects
                WHERE date_recorded >= NOW() - INTERVAL '1 day'
            """)

            result = db.execute(query).fetchone()

            if result and result['total_records'] > 0:
                completeness = {
                    'mlb_id': result['has_mlb_id'] / result['total_records'],
                    'name': result['has_name'] / result['total_records'],
                    'position': result['has_position'] / result['total_records'],
                    'organization': result['has_organization'] / result['total_records'],
                    'level': result['has_level'] / result['total_records']
                }

                # Check if any field is below threshold
                for field, rate in completeness.items():
                    if rate < self.quality_thresholds['completeness']:
                        self.create_alert(
                            AlertLevel.WARNING,
                            f"Data completeness below threshold for {field}: {rate:.2%}"
                        )

                results['completeness'] = completeness
                results['total_records'] = result['total_records']

            return results

        except Exception as e:
            logger.error(f"Error checking data completeness: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()

    def check_data_freshness(self) -> Dict[str, Any]:
        """Check if data is being updated regularly."""
        db = next(get_db())
        results = {}

        try:
            query = text("""
                SELECT
                    MAX(date_recorded) as latest_update,
                    MIN(date_recorded) as oldest_update,
                    COUNT(DISTINCT DATE(date_recorded)) as unique_days
                FROM prospects
                WHERE date_recorded >= NOW() - INTERVAL '7 days'
            """)

            result = db.execute(query).fetchone()

            if result and result['latest_update']:
                hours_since_update = (
                    datetime.utcnow() - result['latest_update']
                ).total_seconds() / 3600

                if hours_since_update > self.quality_thresholds['freshness_hours']:
                    self.create_alert(
                        AlertLevel.WARNING,
                        f"Data not updated for {hours_since_update:.1f} hours"
                    )

                results['latest_update'] = result['latest_update'].isoformat()
                results['hours_since_update'] = hours_since_update
                results['unique_days'] = result['unique_days']

            return results

        except Exception as e:
            logger.error(f"Error checking data freshness: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()

    def check_duplicate_rate(self) -> Dict[str, Any]:
        """Check for duplicate records."""
        db = next(get_db())
        results = {}

        try:
            query = text("""
                WITH duplicates AS (
                    SELECT mlb_id, COUNT(*) as count
                    FROM prospects
                    WHERE date_recorded >= NOW() - INTERVAL '1 day'
                    GROUP BY mlb_id
                    HAVING COUNT(*) > 1
                )
                SELECT
                    COUNT(*) as duplicate_groups,
                    SUM(count - 1) as duplicate_records
                FROM duplicates
            """)

            result = db.execute(query).fetchone()

            total_query = text("""
                SELECT COUNT(*) as total
                FROM prospects
                WHERE date_recorded >= NOW() - INTERVAL '1 day'
            """)
            total_result = db.execute(total_query).fetchone()

            if total_result and total_result['total'] > 0:
                duplicate_rate = (result['duplicate_records'] or 0) / total_result['total']

                if duplicate_rate > self.quality_thresholds['duplicate_rate']:
                    self.create_alert(
                        AlertLevel.WARNING,
                        f"Duplicate rate above threshold: {duplicate_rate:.2%}"
                    )

                results['duplicate_rate'] = duplicate_rate
                results['duplicate_records'] = result['duplicate_records'] or 0
                results['total_records'] = total_result['total']

            return results

        except Exception as e:
            logger.error(f"Error checking duplicate rate: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()

    def check_outliers(self) -> Dict[str, Any]:
        """Check for statistical outliers in numeric fields."""
        db = next(get_db())
        results = {'outliers': []}

        try:
            # Check batting average outliers
            query = text("""
                WITH stats AS (
                    SELECT
                        prospect_id,
                        batting_avg,
                        AVG(batting_avg) OVER () as mean_avg,
                        STDDEV(batting_avg) OVER () as stddev_avg
                    FROM prospect_stats
                    WHERE date_recorded >= NOW() - INTERVAL '1 day'
                    AND batting_avg IS NOT NULL
                )
                SELECT
                    prospect_id,
                    batting_avg,
                    ABS(batting_avg - mean_avg) / NULLIF(stddev_avg, 0) as z_score
                FROM stats
                WHERE ABS(batting_avg - mean_avg) > 3 * stddev_avg
            """)

            outliers = db.execute(query).fetchall()

            for outlier in outliers:
                results['outliers'].append({
                    'prospect_id': outlier['prospect_id'],
                    'metric': 'batting_avg',
                    'value': float(outlier['batting_avg']),
                    'z_score': float(outlier['z_score'])
                })

            outlier_rate = len(outliers) / max(1, len(outliers) + 100)  # Approximate

            if outlier_rate > self.quality_thresholds['outlier_rate']:
                self.create_alert(
                    AlertLevel.WARNING,
                    f"Outlier rate above threshold: {outlier_rate:.2%}"
                )

            results['outlier_rate'] = outlier_rate
            results['outlier_count'] = len(outliers)

            return results

        except Exception as e:
            logger.error(f"Error checking outliers: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()

    def create_alert(self, level: AlertLevel, message: str):
        """Create a data quality alert."""
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.value,
            'message': message,
            'component': 'DataQualityMonitor'
        }
        self.alerts.append(alert)
        logger.log(
            logging.WARNING if level == AlertLevel.WARNING else logging.ERROR,
            message
        )

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all data quality checks."""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'completeness': self.check_data_completeness(),
            'freshness': self.check_data_freshness(),
            'duplicates': self.check_duplicate_rate(),
            'outliers': self.check_outliers(),
            'alerts': self.alerts
        }

        # Clear alerts after reporting
        self.alerts = []

        return results


class PipelinePerformanceMonitor:
    """Monitor pipeline performance metrics."""

    def __init__(self):
        self.metrics = {
            'execution_times': [],
            'memory_usage': [],
            'cpu_usage': [],
            'records_processed': [],
            'error_count': 0
        }
        self.start_time = None

    def start_monitoring(self):
        """Start monitoring pipeline execution."""
        self.start_time = time.time()
        self.metrics['start_time'] = datetime.utcnow().isoformat()

        # Record initial resource usage
        self.metrics['initial_memory'] = psutil.virtual_memory().percent
        self.metrics['initial_cpu'] = psutil.cpu_percent(interval=1)

    def record_checkpoint(self, checkpoint_name: str, records_processed: int = 0):
        """Record a pipeline checkpoint."""
        if not self.start_time:
            self.start_monitoring()

        elapsed_time = time.time() - self.start_time

        checkpoint = {
            'name': checkpoint_name,
            'timestamp': datetime.utcnow().isoformat(),
            'elapsed_time': elapsed_time,
            'memory_usage': psutil.virtual_memory().percent,
            'cpu_usage': psutil.cpu_percent(interval=0.1),
            'records_processed': records_processed
        }

        self.metrics['execution_times'].append(checkpoint)
        self.metrics['memory_usage'].append(checkpoint['memory_usage'])
        self.metrics['cpu_usage'].append(checkpoint['cpu_usage'])

        if records_processed > 0:
            self.metrics['records_processed'].append(records_processed)

        logger.info(f"Checkpoint '{checkpoint_name}': {elapsed_time:.2f}s, {records_processed} records")

    def record_error(self, error: str, context: Optional[Dict] = None):
        """Record a pipeline error."""
        self.metrics['error_count'] += 1

        error_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'error': error,
            'context': context or {}
        }

        if 'errors' not in self.metrics:
            self.metrics['errors'] = []

        self.metrics['errors'].append(error_record)
        logger.error(f"Pipeline error: {error}")

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.start_time:
            return {'status': 'not_started'}

        total_time = time.time() - self.start_time
        total_records = sum(self.metrics['records_processed'])

        summary = {
            'total_execution_time': total_time,
            'total_records_processed': total_records,
            'throughput': total_records / total_time if total_time > 0 else 0,
            'avg_memory_usage': sum(self.metrics['memory_usage']) / len(self.metrics['memory_usage'])
            if self.metrics['memory_usage'] else 0,
            'max_memory_usage': max(self.metrics['memory_usage']) if self.metrics['memory_usage'] else 0,
            'avg_cpu_usage': sum(self.metrics['cpu_usage']) / len(self.metrics['cpu_usage'])
            if self.metrics['cpu_usage'] else 0,
            'max_cpu_usage': max(self.metrics['cpu_usage']) if self.metrics['cpu_usage'] else 0,
            'error_count': self.metrics['error_count'],
            'checkpoints': len(self.metrics['execution_times'])
        }

        return summary

    async def log_batch_prediction_metrics(
        self,
        batch_id: str,
        total_requested: int,
        successful_predictions: int,
        failed_predictions: int,
        processing_time: float
    ):
        """Log batch prediction processing metrics."""
        try:
            metrics = {
                "batch_id": batch_id,
                "total_requested": total_requested,
                "successful_predictions": successful_predictions,
                "failed_predictions": failed_predictions,
                "processing_time": processing_time,
                "success_rate": successful_predictions / total_requested if total_requested > 0 else 0,
                "throughput": total_requested / processing_time if processing_time > 0 else 0,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Batch {batch_id} metrics: {successful_predictions}/{total_requested} successful, "
                       f"{processing_time:.2f}s, {metrics['throughput']:.2f} predictions/sec")

        except Exception as e:
            logger.error(f"Failed to log batch metrics: {e}")


class PipelineMonitor:
    """Monitor ML pipeline performance and batch processing metrics."""

    def __init__(self):
        self.metrics_store = {}
        self.data_freshness_tracking = {}
        self.ingestion_history = {}
        self.alert_manager = AlertManager()

    async def start_pipeline_run(self, pipeline_name: str):
        """Start tracking a pipeline run."""
        run_id = f"{pipeline_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self.ingestion_history[run_id] = {
            'pipeline': pipeline_name,
            'start_time': datetime.utcnow(),
            'status': 'running'
        }
        return run_id

    async def record_successful_fetch(self, source: str, details: str):
        """Record a successful data fetch from a source."""
        timestamp = datetime.utcnow()
        if source not in self.data_freshness_tracking:
            self.data_freshness_tracking[source] = {}

        self.data_freshness_tracking[source]['last_successful_fetch'] = timestamp
        self.data_freshness_tracking[source]['last_details'] = details
        self.data_freshness_tracking[source]['consecutive_failures'] = 0

        logger.info(f"Successful fetch from {source}: {details}")

    async def record_fetch_error(self, source: str, url: str, error: str):
        """Record a failed data fetch attempt."""
        if source not in self.data_freshness_tracking:
            self.data_freshness_tracking[source] = {'consecutive_failures': 0}

        self.data_freshness_tracking[source]['consecutive_failures'] += 1
        self.data_freshness_tracking[source]['last_error'] = {
            'url': url,
            'error': error,
            'timestamp': datetime.utcnow()
        }

        # Alert on consecutive failures
        if self.data_freshness_tracking[source]['consecutive_failures'] >= 3:
            await self.send_alert(
                level='error',
                message=f"{source} has failed {self.data_freshness_tracking[source]['consecutive_failures']} consecutive times: {error}"
            )

        logger.error(f"Fetch error from {source} ({url}): {error}")

    async def record_rate_limit_hit(self, source: str):
        """Record when rate limit is hit for a source."""
        timestamp = datetime.utcnow()
        if source not in self.data_freshness_tracking:
            self.data_freshness_tracking[source] = {}

        if 'rate_limit_hits' not in self.data_freshness_tracking[source]:
            self.data_freshness_tracking[source]['rate_limit_hits'] = []

        self.data_freshness_tracking[source]['rate_limit_hits'].append(timestamp)

        # Alert if too many rate limits in short period
        recent_hits = [
            hit for hit in self.data_freshness_tracking[source]['rate_limit_hits']
            if (timestamp - hit).total_seconds() < 3600  # Within last hour
        ]

        if len(recent_hits) >= 5:
            await self.send_alert(
                level='warning',
                message=f"{source} hit rate limit {len(recent_hits)} times in the last hour"
            )

    async def record_processing_error(self, source: str, record_id: str, error: str):
        """Record a processing error for a specific record."""
        logger.error(f"Processing error for {source} record {record_id}: {error}")

    async def record_batch_progress(self, source: str, processed: int, total: int):
        """Record batch processing progress."""
        progress = processed / total if total > 0 else 0
        logger.info(f"{source} batch progress: {processed}/{total} ({progress:.1%})")

    async def record_data_merge(self, source1: str, source2: str, source1_count: int,
                               source2_count: int, matched_count: int, total_merged: int):
        """Record data merge statistics."""
        merge_stats = {
            'timestamp': datetime.utcnow(),
            'sources': [source1, source2],
            'source1_count': source1_count,
            'source2_count': source2_count,
            'matched_count': matched_count,
            'total_merged': total_merged,
            'match_rate': matched_count / min(source1_count, source2_count) if min(source1_count, source2_count) > 0 else 0
        }

        logger.info(f"Data merge: {matched_count} matches from {source1_count} {source1} and {source2_count} {source2} records")

        # Alert if match rate is low
        if merge_stats['match_rate'] < 0.5 and min(source1_count, source2_count) > 10:
            await self.send_alert(
                level='warning',
                message=f"Low match rate between {source1} and {source2}: {merge_stats['match_rate']:.1%}"
            )

    async def record_conflict_resolution(self, prospect_name: str, conflicts: List[Dict],
                                        resolution_method: str, precedence_order: List[str]):
        """Record conflict resolution for audit trail."""
        logger.info(f"Resolved {len(conflicts)} conflicts for {prospect_name} using {resolution_method}")

    async def record_validation_results(self, total_records: int, valid_count: int, invalid_count: int):
        """Record data validation results."""
        validation_rate = valid_count / total_records if total_records > 0 else 0
        logger.info(f"Validation: {valid_count}/{total_records} valid ({validation_rate:.1%})")

        if validation_rate < 0.95:
            await self.send_alert(
                level='warning',
                message=f"Data validation rate below threshold: {validation_rate:.1%}"
            )

    async def check_data_freshness(self, source: str, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Check if data from a source is fresh.

        Returns:
            Dict with freshness status and details
        """
        if source not in self.data_freshness_tracking:
            return {
                'is_fresh': False,
                'reason': 'No data recorded for source',
                'age_hours': None
            }

        last_fetch = self.data_freshness_tracking[source].get('last_successful_fetch')

        if not last_fetch:
            return {
                'is_fresh': False,
                'reason': 'No successful fetch recorded',
                'age_hours': None
            }

        age = datetime.utcnow() - last_fetch
        age_hours = age.total_seconds() / 3600

        is_fresh = age_hours <= max_age_hours

        return {
            'is_fresh': is_fresh,
            'last_fetch': last_fetch.isoformat(),
            'age_hours': age_hours,
            'threshold_hours': max_age_hours
        }

    async def send_alert(self, level: str, message: str):
        """Send an alert through the alert manager."""
        await self.alert_manager.send_alert(AlertLevel[level.upper()], message)

    async def log_batch_prediction_metrics(
        self,
        batch_id: str,
        total_requested: int,
        successful_predictions: int,
        failed_predictions: int,
        processing_time: float
    ):
        """Log batch prediction processing metrics."""
        try:
            metrics = {
                "batch_id": batch_id,
                "total_requested": total_requested,
                "successful_predictions": successful_predictions,
                "failed_predictions": failed_predictions,
                "processing_time": processing_time,
                "success_rate": successful_predictions / total_requested if total_requested > 0 else 0,
                "throughput": total_requested / processing_time if processing_time > 0 else 0,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Store metrics
            self.metrics_store[batch_id] = metrics

            logger.info(f"Batch {batch_id} metrics: {successful_predictions}/{total_requested} successful, "
                       f"{processing_time:.2f}s, {metrics['throughput']:.2f} predictions/sec")

        except Exception as e:
            logger.error(f"Failed to log batch metrics: {e}")


class PipelineOrchestrator:
    """Orchestrate and monitor pipeline execution."""

    def __init__(self):
        self.quality_monitor = DataQualityMonitor()
        self.performance_monitor = PipelinePerformanceMonitor()
        self.status = PipelineStatus.RUNNING
        self.run_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    def pre_execution_checks(self) -> bool:
        """Run pre-execution validation checks."""
        logger.info("Running pre-execution checks")

        # Check database connectivity
        try:
            db = next(get_db())
            db.execute(text("SELECT 1"))
            db.close()
        except Exception as e:
            logger.error(f"Database connectivity check failed: {str(e)}")
            return False

        # Check disk space
        disk_usage = psutil.disk_usage('/')
        if disk_usage.percent > 90:
            logger.error(f"Insufficient disk space: {disk_usage.percent}% used")
            return False

        # Check memory availability
        memory = psutil.virtual_memory()
        if memory.available < 1024 * 1024 * 1024:  # Less than 1GB
            logger.error(f"Insufficient memory: {memory.available / (1024**3):.2f} GB available")
            return False

        return True

    def post_execution_checks(self) -> Dict[str, Any]:
        """Run post-execution validation and quality checks."""
        logger.info("Running post-execution checks")

        # Run data quality checks
        quality_results = self.quality_monitor.run_all_checks()

        # Get performance summary
        performance_summary = self.performance_monitor.get_summary()

        # Determine overall status
        if self.performance_monitor.metrics['error_count'] > 0:
            self.status = PipelineStatus.PARTIAL
        else:
            self.status = PipelineStatus.COMPLETED

        results = {
            'run_id': self.run_id,
            'status': self.status.value,
            'quality': quality_results,
            'performance': performance_summary,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Save results to file
        self.save_monitoring_results(results)

        # Send alerts if needed
        if quality_results.get('alerts'):
            self.send_alerts(quality_results['alerts'])

        return results

    def save_monitoring_results(self, results: Dict[str, Any]):
        """Save monitoring results to file."""
        filename = f"pipeline_monitoring_{self.run_id}.json"
        filepath = f"logs/{filename}"

        try:
            # Create logs directory if it doesn't exist
            import os
            os.makedirs('logs', exist_ok=True)

            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)

            logger.info(f"Monitoring results saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving monitoring results: {str(e)}")

    def send_alerts(self, alerts: List[Dict[str, Any]]):
        """Send alerts via configured channels."""
        # For now, just log the alerts
        # In production, this would send emails, Slack messages, etc.

        critical_alerts = [a for a in alerts if a['level'] == AlertLevel.CRITICAL.value]
        error_alerts = [a for a in alerts if a['level'] == AlertLevel.ERROR.value]
        warning_alerts = [a for a in alerts if a['level'] == AlertLevel.WARNING.value]

        if critical_alerts:
            logger.critical(f"CRITICAL ALERTS: {len(critical_alerts)} issues require immediate attention")
            for alert in critical_alerts:
                logger.critical(f"  - {alert['message']}")

        if error_alerts:
            logger.error(f"ERROR ALERTS: {len(error_alerts)} errors detected")
            for alert in error_alerts:
                logger.error(f"  - {alert['message']}")

        if warning_alerts:
            logger.warning(f"WARNING ALERTS: {len(warning_alerts)} warnings")
            for alert in warning_alerts:
                logger.warning(f"  - {alert['message']}")


class DataLineageTracker:
    """Track data lineage and versioning."""

    def __init__(self):
        self.lineage = {
            'sources': [],
            'transformations': [],
            'outputs': [],
            'version': None
        }

    def track_source(self, source_name: str, metadata: Dict[str, Any]):
        """Track a data source."""
        source_record = {
            'name': source_name,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': metadata
        }
        self.lineage['sources'].append(source_record)

    def track_transformation(self, transform_name: str, input_count: int, output_count: int):
        """Track a data transformation."""
        transform_record = {
            'name': transform_name,
            'timestamp': datetime.utcnow().isoformat(),
            'input_records': input_count,
            'output_records': output_count,
            'ratio': output_count / input_count if input_count > 0 else 0
        }
        self.lineage['transformations'].append(transform_record)

    def track_output(self, output_name: str, record_count: int, location: str):
        """Track a data output."""
        output_record = {
            'name': output_name,
            'timestamp': datetime.utcnow().isoformat(),
            'record_count': record_count,
            'location': location
        }
        self.lineage['outputs'].append(output_record)

    def create_version(self) -> str:
        """Create a version identifier for the data."""
        import hashlib

        # Create version based on sources and timestamp
        version_string = f"{datetime.utcnow().isoformat()}"
        for source in self.lineage['sources']:
            version_string += f"_{source['name']}"

        version_hash = hashlib.sha256(version_string.encode()).hexdigest()[:8]
        self.lineage['version'] = f"v_{datetime.utcnow().strftime('%Y%m%d')}_{version_hash}"

        return self.lineage['version']

    def save_lineage(self, filepath: Optional[str] = None):
        """Save lineage information."""
        if not filepath:
            filepath = f"data_lineage_{self.lineage.get('version', 'unknown')}.json"

        try:
            with open(filepath, 'w') as f:
                json.dump(self.lineage, f, indent=2, default=str)

            logger.info(f"Data lineage saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving lineage: {str(e)}")


# Dashboard metrics aggregator
def create_monitoring_dashboard() -> Dict[str, Any]:
    """Create a monitoring dashboard with key metrics."""
    db = next(get_db())
    dashboard = {}

    try:
        # Pipeline status
        status_query = text("""
            SELECT
                COUNT(DISTINCT DATE(date_recorded)) as days_with_data,
                COUNT(DISTINCT mlb_id) as unique_prospects,
                COUNT(*) as total_records,
                MAX(date_recorded) as last_update
            FROM prospects
            WHERE date_recorded >= NOW() - INTERVAL '7 days'
        """)

        status = db.execute(status_query).fetchone()
        dashboard['pipeline_status'] = {
            'days_with_data': status['days_with_data'],
            'unique_prospects': status['unique_prospects'],
            'total_records': status['total_records'],
            'last_update': status['last_update'].isoformat() if status['last_update'] else None
        }

        # Data quality metrics
        quality_query = text("""
            SELECT
                AVG(CASE WHEN name IS NOT NULL THEN 1 ELSE 0 END) as name_completeness,
                AVG(CASE WHEN position IS NOT NULL THEN 1 ELSE 0 END) as position_completeness,
                AVG(CASE WHEN organization IS NOT NULL THEN 1 ELSE 0 END) as org_completeness
            FROM prospects
            WHERE date_recorded >= NOW() - INTERVAL '1 day'
        """)

        quality = db.execute(quality_query).fetchone()
        dashboard['data_quality'] = {
            'name_completeness': float(quality['name_completeness'] or 0),
            'position_completeness': float(quality['position_completeness'] or 0),
            'organization_completeness': float(quality['org_completeness'] or 0)
        }

        # Processing metrics
        processing_query = text("""
            SELECT
                COUNT(DISTINCT p.id) as prospects_with_stats,
                COUNT(DISTINCT sg.prospect_id) as prospects_with_grades,
                AVG(ps.batting_avg) as avg_batting_avg,
                AVG(sg.overall_grade) as avg_scouting_grade
            FROM prospects p
            LEFT JOIN prospect_stats ps ON p.id = ps.prospect_id
            LEFT JOIN scouting_grades sg ON p.id = sg.prospect_id
            WHERE p.date_recorded >= NOW() - INTERVAL '1 day'
        """)

        processing = db.execute(processing_query).fetchone()
        dashboard['processing_metrics'] = {
            'prospects_with_stats': processing['prospects_with_stats'],
            'prospects_with_grades': processing['prospects_with_grades'],
            'avg_batting_avg': float(processing['avg_batting_avg'] or 0),
            'avg_scouting_grade': float(processing['avg_scouting_grade'] or 0)
        }

        # System performance metrics
        dashboard['system_performance'] = get_system_performance_metrics()

        # Circuit breaker status
        dashboard['circuit_breakers'] = get_circuit_breaker_metrics()

        dashboard['timestamp'] = datetime.utcnow().isoformat()

        return dashboard

    except Exception as e:
        logger.error(f"Error creating monitoring dashboard: {str(e)}")
        return {'error': str(e)}
    finally:
        db.close()


def get_system_performance_metrics() -> Dict[str, Any]:
    """Get system performance metrics."""
    try:
        # CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Network I/O (if available)
        network = psutil.net_io_counters()

        return {
            'cpu': {
                'usage_percent': cpu_percent,
                'count': psutil.cpu_count(),
                'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            },
            'memory': {
                'total_gb': memory.total / (1024**3),
                'available_gb': memory.available / (1024**3),
                'used_percent': memory.percent,
                'cached_gb': memory.cached / (1024**3) if hasattr(memory, 'cached') else None
            },
            'disk': {
                'total_gb': disk.total / (1024**3),
                'free_gb': disk.free / (1024**3),
                'used_percent': disk.percent
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            } if network else None
        }

    except Exception as e:
        logger.error(f"Error getting system performance metrics: {str(e)}")
        return {'error': str(e)}


def get_circuit_breaker_metrics() -> Dict[str, Any]:
    """Get circuit breaker status for all registered breakers."""
    try:
        from app.core.circuit_breaker import circuit_breaker_registry
        return circuit_breaker_registry.get_all_metrics()
    except Exception as e:
        logger.error(f"Error getting circuit breaker metrics: {str(e)}")
        return {'error': str(e)}


class PerformanceDashboard:
    """Enhanced performance monitoring dashboard."""

    def __init__(self):
        self.metrics_history = []
        self.alert_thresholds = {
            'cpu_percent': 80,
            'memory_percent': 85,
            'disk_percent': 90,
            'response_time_ms': 5000,
            'error_rate': 0.05
        }

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive performance metrics."""
        timestamp = datetime.utcnow()

        metrics = {
            'timestamp': timestamp.isoformat(),
            'system': get_system_performance_metrics(),
            'database': await self._get_database_metrics(),
            'pipeline': await self._get_pipeline_metrics(),
            'api': await self._get_api_metrics(),
            'circuit_breakers': get_circuit_breaker_metrics()
        }

        # Store in history (keep last 100 records)
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]

        # Check for alerts
        await self._check_performance_alerts(metrics)

        return metrics

    async def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics."""
        try:
            db = next(get_db())

            # Connection pool stats
            pool_query = text("""
                SELECT
                    numbackends as active_connections,
                    xact_commit as commits,
                    xact_rollback as rollbacks,
                    blks_read as blocks_read,
                    blks_hit as blocks_hit
                FROM pg_stat_database
                WHERE datname = current_database()
            """)

            result = db.execute(pool_query).fetchone()

            if result:
                hit_ratio = result['blocks_hit'] / (result['blocks_hit'] + result['blocks_read']) if (result['blocks_hit'] + result['blocks_read']) > 0 else 0

                return {
                    'active_connections': result['active_connections'],
                    'commits': result['commits'],
                    'rollbacks': result['rollbacks'],
                    'cache_hit_ratio': hit_ratio,
                    'blocks_read': result['blocks_read'],
                    'blocks_hit': result['blocks_hit']
                }

            return {'error': 'No database stats available'}

        except Exception as e:
            logger.error(f"Error getting database metrics: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()

    async def _get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get pipeline-specific metrics."""
        return {
            'fangraphs_service': await self._get_fangraphs_metrics(),
            'data_processing': await self._get_data_processing_metrics()
        }

    async def _get_fangraphs_metrics(self) -> Dict[str, Any]:
        """Get FanGraphs service metrics."""
        try:
            # This would integrate with the FanGraphs service
            return {
                'requests_made': 0,  # Placeholder
                'successful_requests': 0,
                'failed_requests': 0,
                'avg_response_time': 0,
                'rate_limit_hits': 0
            }
        except Exception as e:
            return {'error': str(e)}

    async def _get_data_processing_metrics(self) -> Dict[str, Any]:
        """Get data processing pipeline metrics."""
        try:
            db = next(get_db())

            # Recent processing stats
            query = text("""
                SELECT
                    COUNT(*) as records_processed_today,
                    COUNT(DISTINCT mlb_id) as unique_prospects_today
                FROM prospects
                WHERE date_recorded >= CURRENT_DATE
            """)

            result = db.execute(query).fetchone()

            return {
                'records_processed_today': result['records_processed_today'],
                'unique_prospects_today': result['unique_prospects_today'],
                'processing_rate': result['records_processed_today'] / 24 if result['records_processed_today'] else 0  # per hour
            }

        except Exception as e:
            logger.error(f"Error getting data processing metrics: {str(e)}")
            return {'error': str(e)}
        finally:
            db.close()

    async def _get_api_metrics(self) -> Dict[str, Any]:
        """Get API performance metrics."""
        # This would integrate with API monitoring
        return {
            'requests_per_minute': 0,  # Placeholder
            'avg_response_time': 0,
            'error_rate': 0,
            'active_sessions': 0
        }

    async def _check_performance_alerts(self, metrics: Dict[str, Any]):
        """Check metrics against thresholds and send alerts."""
        alerts = []

        # Check system metrics
        system = metrics.get('system', {})
        if system.get('cpu', {}).get('usage_percent', 0) > self.alert_thresholds['cpu_percent']:
            alerts.append(f"High CPU usage: {system['cpu']['usage_percent']:.1f}%")

        if system.get('memory', {}).get('used_percent', 0) > self.alert_thresholds['memory_percent']:
            alerts.append(f"High memory usage: {system['memory']['used_percent']:.1f}%")

        if system.get('disk', {}).get('used_percent', 0) > self.alert_thresholds['disk_percent']:
            alerts.append(f"High disk usage: {system['disk']['used_percent']:.1f}%")

        # Check circuit breaker states
        circuit_breakers = metrics.get('circuit_breakers', {})
        for name, cb_metrics in circuit_breakers.items():
            if cb_metrics.get('state') == 'open':
                alerts.append(f"Circuit breaker {name} is OPEN")
            elif cb_metrics.get('failure_rate', 0) > 0.1:  # 10% failure rate
                alerts.append(f"High failure rate for {name}: {cb_metrics['failure_rate']:.1%}")

        # Send alerts if any
        if alerts:
            monitor = PipelineMonitor()
            for alert in alerts:
                await monitor.send_alert('warning', f"Performance alert: {alert}")

    def get_dashboard_data(self, time_range_minutes: int = 60) -> Dict[str, Any]:
        """Get dashboard data for specified time range."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_range_minutes)

        recent_metrics = [
            m for m in self.metrics_history
            if datetime.fromisoformat(m['timestamp']) >= cutoff_time
        ]

        if not recent_metrics:
            return {'error': 'No metrics available for time range'}

        return {
            'time_range_minutes': time_range_minutes,
            'metrics_count': len(recent_metrics),
            'latest_metrics': recent_metrics[-1] if recent_metrics else None,
            'trends': self._calculate_trends(recent_metrics),
            'summary': self._generate_summary(recent_metrics)
        }

    def _calculate_trends(self, metrics_list: List[Dict]) -> Dict[str, Any]:
        """Calculate trends from metrics history."""
        if len(metrics_list) < 2:
            return {}

        first_metrics = metrics_list[0]
        last_metrics = metrics_list[-1]

        trends = {}

        # CPU trend
        first_cpu = first_metrics.get('system', {}).get('cpu', {}).get('usage_percent')
        last_cpu = last_metrics.get('system', {}).get('cpu', {}).get('usage_percent')
        if first_cpu is not None and last_cpu is not None:
            trends['cpu_trend'] = last_cpu - first_cpu

        # Memory trend
        first_mem = first_metrics.get('system', {}).get('memory', {}).get('used_percent')
        last_mem = last_metrics.get('system', {}).get('memory', {}).get('used_percent')
        if first_mem is not None and last_mem is not None:
            trends['memory_trend'] = last_mem - first_mem

        return trends

    def _generate_summary(self, metrics_list: List[Dict]) -> Dict[str, Any]:
        """Generate summary statistics from metrics."""
        if not metrics_list:
            return {}

        # Calculate averages
        cpu_values = [m.get('system', {}).get('cpu', {}).get('usage_percent') for m in metrics_list]
        cpu_values = [v for v in cpu_values if v is not None]

        memory_values = [m.get('system', {}).get('memory', {}).get('used_percent') for m in metrics_list]
        memory_values = [v for v in memory_values if v is not None]

        return {
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            'avg_memory_percent': sum(memory_values) / len(memory_values) if memory_values else 0,
            'max_cpu_percent': max(cpu_values) if cpu_values else 0,
            'max_memory_percent': max(memory_values) if memory_values else 0,
            'metrics_collected': len(metrics_list)
        }