"""
Test suite for pipeline monitoring and alerting.
Tests data quality monitoring, performance tracking, and alerting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import psutil

from app.services.pipeline_monitoring import (
    AlertLevel,
    PipelineStatus,
    DataQualityMonitor,
    PipelinePerformanceMonitor,
    PipelineOrchestrator,
    DataLineageTracker,
    create_monitoring_dashboard
)


class TestDataQualityMonitor:
    """Test data quality monitoring functionality."""

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_data_completeness_all_complete(self, mock_get_db):
        """Test completeness check when all fields are complete."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.__getitem__ = lambda self, key: {
            'total_records': 100,
            'has_mlb_id': 100,
            'has_name': 100,
            'has_position': 100,
            'has_organization': 100,
            'has_level': 100
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_result
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_data_completeness()

        assert 'completeness' in results
        assert results['total_records'] == 100
        assert results['completeness']['name'] == 1.0
        assert len(monitor.alerts) == 0

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_data_completeness_below_threshold(self, mock_get_db):
        """Test completeness check when fields are below threshold."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.__getitem__ = lambda self, key: {
            'total_records': 100,
            'has_mlb_id': 100,
            'has_name': 100,
            'has_position': 90,  # Below 95% threshold
            'has_organization': 100,
            'has_level': 100
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_result
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_data_completeness()

        assert results['completeness']['position'] == 0.9
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]['level'] == AlertLevel.WARNING.value

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_data_freshness_recent_update(self, mock_get_db):
        """Test freshness check with recent update."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        recent_time = datetime.utcnow() - timedelta(hours=2)
        mock_result.__getitem__ = lambda self, key: {
            'latest_update': recent_time,
            'oldest_update': recent_time - timedelta(days=1),
            'unique_days': 2
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_result
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_data_freshness()

        assert 'hours_since_update' in results
        assert results['hours_since_update'] < 3
        assert len(monitor.alerts) == 0

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_data_freshness_stale_data(self, mock_get_db):
        """Test freshness check with stale data."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        old_time = datetime.utcnow() - timedelta(hours=48)
        mock_result.__getitem__ = lambda self, key: {
            'latest_update': old_time,
            'oldest_update': old_time - timedelta(days=7),
            'unique_days': 1
        }[key]
        mock_db.execute.return_value.fetchone.return_value = mock_result
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_data_freshness()

        assert results['hours_since_update'] > 24
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]['level'] == AlertLevel.WARNING.value

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_duplicate_rate_no_duplicates(self, mock_get_db):
        """Test duplicate rate check with no duplicates."""
        mock_db = MagicMock()

        # Mock duplicate query result
        mock_dup_result = MagicMock()
        mock_dup_result.__getitem__ = lambda self, key: {
            'duplicate_groups': 0,
            'duplicate_records': 0
        }[key]

        # Mock total query result
        mock_total_result = MagicMock()
        mock_total_result.__getitem__ = lambda self, key: {'total': 100}[key]

        mock_db.execute.return_value.fetchone.side_effect = [
            mock_dup_result, mock_total_result
        ]
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_duplicate_rate()

        assert results['duplicate_rate'] == 0
        assert results['duplicate_records'] == 0
        assert len(monitor.alerts) == 0

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_duplicate_rate_above_threshold(self, mock_get_db):
        """Test duplicate rate check above threshold."""
        mock_db = MagicMock()

        # Mock duplicate query result
        mock_dup_result = MagicMock()
        mock_dup_result.__getitem__ = lambda self, key: {
            'duplicate_groups': 5,
            'duplicate_records': 10  # 10% duplicate rate
        }[key]

        # Mock total query result
        mock_total_result = MagicMock()
        mock_total_result.__getitem__ = lambda self, key: {'total': 100}[key]

        mock_db.execute.return_value.fetchone.side_effect = [
            mock_dup_result, mock_total_result
        ]
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_duplicate_rate()

        assert results['duplicate_rate'] == 0.1
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]['level'] == AlertLevel.WARNING.value

    @patch('app.services.pipeline_monitoring.get_db')
    def test_check_outliers_detected(self, mock_get_db):
        """Test outlier detection."""
        mock_db = MagicMock()

        # Mock outlier query result
        mock_outliers = [
            {'prospect_id': 1, 'batting_avg': 0.999, 'z_score': 4.5},
            {'prospect_id': 2, 'batting_avg': 0.001, 'z_score': -4.2}
        ]
        mock_db.execute.return_value.fetchall.return_value = mock_outliers
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.check_outliers()

        assert results['outlier_count'] == 2
        assert len(results['outliers']) == 2
        # Note: Alert may or may not be triggered depending on outlier_rate calculation

    def test_create_alert(self):
        """Test alert creation."""
        monitor = DataQualityMonitor()

        monitor.create_alert(AlertLevel.ERROR, "Test error message")

        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]['level'] == AlertLevel.ERROR.value
        assert monitor.alerts[0]['message'] == "Test error message"
        assert 'timestamp' in monitor.alerts[0]

    @patch('app.services.pipeline_monitoring.get_db')
    def test_run_all_checks(self, mock_get_db):
        """Test running all quality checks."""
        # Mock database for all checks
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.run_all_checks()

        assert 'completeness' in results
        assert 'freshness' in results
        assert 'duplicates' in results
        assert 'outliers' in results
        assert 'alerts' in results
        assert 'timestamp' in results


class TestPipelinePerformanceMonitor:
    """Test pipeline performance monitoring."""

    def test_start_monitoring(self):
        """Test starting performance monitoring."""
        monitor = PipelinePerformanceMonitor()
        monitor.start_monitoring()

        assert monitor.start_time is not None
        assert 'start_time' in monitor.metrics
        assert 'initial_memory' in monitor.metrics
        assert 'initial_cpu' in monitor.metrics

    def test_record_checkpoint(self):
        """Test recording a checkpoint."""
        monitor = PipelinePerformanceMonitor()
        monitor.start_monitoring()

        monitor.record_checkpoint('test_checkpoint', records_processed=100)

        assert len(monitor.metrics['execution_times']) == 1
        assert monitor.metrics['execution_times'][0]['name'] == 'test_checkpoint'
        assert monitor.metrics['execution_times'][0]['records_processed'] == 100
        assert len(monitor.metrics['records_processed']) == 1

    def test_record_error(self):
        """Test recording an error."""
        monitor = PipelinePerformanceMonitor()

        monitor.record_error("Test error", context={'step': 'extraction'})

        assert monitor.metrics['error_count'] == 1
        assert len(monitor.metrics['errors']) == 1
        assert monitor.metrics['errors'][0]['error'] == "Test error"
        assert monitor.metrics['errors'][0]['context']['step'] == 'extraction'

    def test_get_summary(self):
        """Test getting performance summary."""
        monitor = PipelinePerformanceMonitor()
        monitor.start_monitoring()

        # Record some checkpoints
        monitor.record_checkpoint('checkpoint1', 50)
        monitor.record_checkpoint('checkpoint2', 100)

        summary = monitor.get_summary()

        assert 'total_execution_time' in summary
        assert summary['total_records_processed'] == 150
        assert summary['throughput'] > 0
        assert summary['checkpoints'] == 2
        assert summary['error_count'] == 0

    def test_get_summary_not_started(self):
        """Test getting summary when monitoring hasn't started."""
        monitor = PipelinePerformanceMonitor()

        summary = monitor.get_summary()

        assert summary == {'status': 'not_started'}


class TestPipelineOrchestrator:
    """Test pipeline orchestration."""

    @patch('app.services.pipeline_monitoring.get_db')
    @patch('psutil.disk_usage')
    @patch('psutil.virtual_memory')
    def test_pre_execution_checks_success(self, mock_memory, mock_disk, mock_get_db):
        """Test successful pre-execution checks."""
        # Mock database connectivity
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock disk usage
        mock_disk.return_value = MagicMock(percent=50)

        # Mock memory
        mock_memory.return_value = MagicMock(available=2 * 1024 * 1024 * 1024)  # 2GB

        orchestrator = PipelineOrchestrator()
        result = orchestrator.pre_execution_checks()

        assert result is True

    @patch('app.services.pipeline_monitoring.get_db')
    def test_pre_execution_checks_database_failure(self, mock_get_db):
        """Test pre-execution checks with database failure."""
        mock_get_db.side_effect = Exception("Database connection failed")

        orchestrator = PipelineOrchestrator()
        result = orchestrator.pre_execution_checks()

        assert result is False

    @patch('app.services.pipeline_monitoring.get_db')
    @patch('psutil.disk_usage')
    def test_pre_execution_checks_insufficient_disk(self, mock_disk, mock_get_db):
        """Test pre-execution checks with insufficient disk space."""
        # Mock database connectivity
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock disk usage above 90%
        mock_disk.return_value = MagicMock(percent=95)

        orchestrator = PipelineOrchestrator()
        result = orchestrator.pre_execution_checks()

        assert result is False

    @patch.object(DataQualityMonitor, 'run_all_checks')
    @patch.object(PipelinePerformanceMonitor, 'get_summary')
    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_post_execution_checks(self, mock_open, mock_makedirs,
                                  mock_perf_summary, mock_quality_checks):
        """Test post-execution checks."""
        # Mock quality checks
        mock_quality_checks.return_value = {
            'alerts': [],
            'completeness': {'name': 1.0},
            'freshness': {'hours_since_update': 2}
        }

        # Mock performance summary
        mock_perf_summary.return_value = {
            'total_execution_time': 100,
            'total_records_processed': 1000,
            'error_count': 0
        }

        orchestrator = PipelineOrchestrator()
        orchestrator.performance_monitor.metrics['error_count'] = 0

        results = orchestrator.post_execution_checks()

        assert results['status'] == PipelineStatus.COMPLETED.value
        assert 'quality' in results
        assert 'performance' in results
        assert mock_open.called

    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_save_monitoring_results(self, mock_open, mock_makedirs):
        """Test saving monitoring results."""
        orchestrator = PipelineOrchestrator()
        results = {'test': 'data', 'timestamp': datetime.utcnow()}

        orchestrator.save_monitoring_results(results)

        mock_makedirs.assert_called_once_with('logs', exist_ok=True)
        mock_open.assert_called_once()

    def test_send_alerts_logging(self):
        """Test alert sending (logging version)."""
        orchestrator = PipelineOrchestrator()

        alerts = [
            {'level': AlertLevel.CRITICAL.value, 'message': 'Critical issue'},
            {'level': AlertLevel.ERROR.value, 'message': 'Error occurred'},
            {'level': AlertLevel.WARNING.value, 'message': 'Warning message'}
        ]

        # Should not raise any exceptions
        orchestrator.send_alerts(alerts)


class TestDataLineageTracker:
    """Test data lineage tracking."""

    def test_track_source(self):
        """Test tracking a data source."""
        tracker = DataLineageTracker()

        tracker.track_source('MLB API', {'endpoint': '/players', 'year': 2024})

        assert len(tracker.lineage['sources']) == 1
        assert tracker.lineage['sources'][0]['name'] == 'MLB API'
        assert tracker.lineage['sources'][0]['metadata']['year'] == 2024

    def test_track_transformation(self):
        """Test tracking a transformation."""
        tracker = DataLineageTracker()

        tracker.track_transformation('clean_data', input_count=100, output_count=95)

        assert len(tracker.lineage['transformations']) == 1
        assert tracker.lineage['transformations'][0]['name'] == 'clean_data'
        assert tracker.lineage['transformations'][0]['input_records'] == 100
        assert tracker.lineage['transformations'][0]['output_records'] == 95
        assert tracker.lineage['transformations'][0]['ratio'] == 0.95

    def test_track_output(self):
        """Test tracking an output."""
        tracker = DataLineageTracker()

        tracker.track_output('training_dataset', 1000, 'data/ml_training/train.parquet')

        assert len(tracker.lineage['outputs']) == 1
        assert tracker.lineage['outputs'][0]['name'] == 'training_dataset'
        assert tracker.lineage['outputs'][0]['record_count'] == 1000
        assert tracker.lineage['outputs'][0]['location'] == 'data/ml_training/train.parquet'

    def test_create_version(self):
        """Test version creation."""
        tracker = DataLineageTracker()
        tracker.track_source('Source1', {})
        tracker.track_source('Source2', {})

        version = tracker.create_version()

        assert version is not None
        assert version.startswith('v_')
        assert tracker.lineage['version'] == version

    @patch('builtins.open', create=True)
    def test_save_lineage(self, mock_open):
        """Test saving lineage information."""
        tracker = DataLineageTracker()
        tracker.track_source('Test Source', {})
        tracker.create_version()

        tracker.save_lineage('test_lineage.json')

        mock_open.assert_called_once_with('test_lineage.json', 'w')


class TestMonitoringDashboard:
    """Test monitoring dashboard creation."""

    @patch('app.services.pipeline_monitoring.get_db')
    def test_create_monitoring_dashboard_success(self, mock_get_db):
        """Test successful dashboard creation."""
        mock_db = MagicMock()

        # Mock status query
        mock_status = MagicMock()
        mock_status.__getitem__ = lambda self, key: {
            'days_with_data': 7,
            'unique_prospects': 500,
            'total_records': 3500,
            'last_update': datetime.utcnow()
        }[key]

        # Mock quality query
        mock_quality = MagicMock()
        mock_quality.__getitem__ = lambda self, key: {
            'name_completeness': 0.98,
            'position_completeness': 0.95,
            'org_completeness': 0.99
        }[key]

        # Mock processing query
        mock_processing = MagicMock()
        mock_processing.__getitem__ = lambda self, key: {
            'prospects_with_stats': 450,
            'prospects_with_grades': 400,
            'avg_batting_avg': 0.275,
            'avg_scouting_grade': 55.5
        }[key]

        mock_db.execute.return_value.fetchone.side_effect = [
            mock_status, mock_quality, mock_processing
        ]
        mock_get_db.return_value = mock_db

        dashboard = create_monitoring_dashboard()

        assert 'pipeline_status' in dashboard
        assert dashboard['pipeline_status']['unique_prospects'] == 500
        assert 'data_quality' in dashboard
        assert dashboard['data_quality']['name_completeness'] == 0.98
        assert 'processing_metrics' in dashboard
        assert dashboard['processing_metrics']['avg_batting_avg'] == 0.275
        assert 'timestamp' in dashboard

    @patch('app.services.pipeline_monitoring.get_db')
    def test_create_monitoring_dashboard_error(self, mock_get_db):
        """Test dashboard creation with error."""
        mock_get_db.side_effect = Exception("Database error")

        dashboard = create_monitoring_dashboard()

        assert 'error' in dashboard
        assert dashboard['error'] == "Database error"