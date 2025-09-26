"""
Integration tests for the complete data processing pipeline.
Tests end-to-end functionality and pipeline execution.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import pandas as pd
import json
import os
import asyncio
from pathlib import Path

from scripts.historical_data_ingestion import HistoricalDataPipeline


class TestHistoricalDataPipeline:
    """Test the complete historical data pipeline."""

    @patch('scripts.historical_data_ingestion.extract_mlb_historical_data')
    @patch('scripts.historical_data_ingestion.extract_fangraphs_data')
    @pytest.mark.asyncio
    async def test_run_extraction_success(self, mock_fg_extract, mock_mlb_extract):
        """Test successful data extraction phase."""
        # Mock extraction results
        mock_mlb_extract.return_value = {
            'status': 'success',
            'records_extracted': 5000,
            'years_processed': 15,
            'errors': []
        }

        mock_fg_extract.return_value = {
            'status': 'success',
            'grades_extracted': 1000,
            'years_processed': 15,
            'errors': []
        }

        pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
        result = await pipeline.run_extraction()

        assert result is True
        assert pipeline.metrics['extraction']['mlb']['records_extracted'] == 5000
        assert pipeline.metrics['extraction']['fangraphs']['grades_extracted'] == 1000

    @patch('scripts.historical_data_ingestion.validate_ingested_data')
    def test_run_validation(self, mock_validate):
        """Test data validation phase."""
        mock_validate.return_value = {
            'status': 'completed',
            'validation_results': {
                'schema_errors': [],
                'outliers': [{'prospect_id': 1, 'metric': 'batting_avg', 'value': 0.999}],
                'consistency_issues': [],
                'total_records_validated': 100
            }
        }

        pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
        result = pipeline.run_validation()

        assert result is True
        assert len(pipeline.metrics['validation']['validation_results']['outliers']) == 1

    @patch('scripts.historical_data_ingestion.clean_normalize_data')
    @patch('scripts.historical_data_ingestion.deduplicate_records')
    def test_run_processing(self, mock_dedupe, mock_clean):
        """Test data processing phase."""
        mock_clean.return_value = {
            'status': 'completed',
            'cleaning_metrics': {
                'names_standardized': 500,
                'stats_normalized': 1000,
                'missing_handled': 50
            }
        }

        mock_dedupe.return_value = {
            'status': 'completed',
            'deduplication_metrics': {
                'duplicates_found': 10,
                'records_merged': 10
            }
        }

        pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
        result = pipeline.run_processing()

        assert result is True
        assert pipeline.metrics['processing']['cleaning']['cleaning_metrics']['stats_normalized'] == 1000
        assert pipeline.metrics['processing']['deduplication']['deduplication_metrics']['duplicates_found'] == 10

    @patch('scripts.historical_data_ingestion.perform_feature_engineering')
    def test_run_feature_engineering(self, mock_feature_eng):
        """Test feature engineering phase."""
        mock_feature_eng.return_value = {
            'status': 'completed',
            'feature_metrics': {
                'age_adjusted_calculated': 1000,
                'progression_rates_calculated': 500,
                'peer_comparisons_calculated': 1000
            }
        }

        pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
        result = pipeline.run_feature_engineering()

        assert result is True
        assert pipeline.metrics['features']['feature_metrics']['age_adjusted_calculated'] == 1000

    @patch('scripts.historical_data_ingestion.update_prospect_rankings')
    @patch('scripts.historical_data_ingestion.cache_processed_results')
    def test_update_rankings_and_cache(self, mock_cache, mock_rankings):
        """Test rankings update and caching phase."""
        mock_rankings.return_value = {
            'status': 'completed',
            'rankings_updated': 500
        }

        mock_cache.return_value = {
            'status': 'completed',
            'cache_type': 'redis',
            'ttl_hours': 24
        }

        pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
        result = pipeline.update_rankings_and_cache()

        assert result is True
        assert pipeline.metrics['rankings']['rankings_updated'] == 500
        assert pipeline.metrics['caching']['cache_type'] == 'redis'

    @patch('pandas.read_sql')
    @patch('scripts.historical_data_ingestion.engine')
    @patch('pathlib.Path.mkdir')
    def test_create_ml_training_dataset(self, mock_mkdir, mock_engine, mock_read_sql):
        """Test ML training dataset creation."""
        # Mock SQL query result
        mock_df = pd.DataFrame({
            'mlb_id': [1, 2, 3, 4, 5],
            'name': ['Player1', 'Player2', 'Player3', 'Player4', 'Player5'],
            'position': ['SS', '2B', 'CF', '1B', 'P'],
            'age': [22, 23, 21, 24, 22],
            'avg_batting_avg': [0.300, 0.280, 0.290, 0.310, None],
            'target': [1, 0, 1, 1, 0],
            'year': [2020, 2021, 2022, 2023, 2024]
        })
        mock_read_sql.return_value = mock_df

        # Mock parquet file writing
        with patch.object(pd.DataFrame, 'to_parquet'):
            pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
            result = pipeline.create_ml_training_dataset()

            assert result is True
            assert pipeline.metrics['ml_dataset']['train_samples'] == 2
            assert pipeline.metrics['ml_dataset']['validation_samples'] == 1
            assert pipeline.metrics['ml_dataset']['test_samples'] == 2

    @pytest.mark.asyncio
    async def test_run_pipeline_complete(self):
        """Test complete pipeline execution."""
        with patch.multiple(
            'scripts.historical_data_ingestion',
            extract_mlb_historical_data=AsyncMock(return_value={
                'status': 'success', 'records_extracted': 100, 'errors': []
            }),
            extract_fangraphs_data=AsyncMock(return_value={
                'status': 'success', 'grades_extracted': 50, 'errors': []
            }),
            validate_ingested_data=Mock(return_value={
                'status': 'completed',
                'validation_results': {'schema_errors': [], 'outliers': [], 'consistency_issues': []}
            }),
            clean_normalize_data=Mock(return_value={
                'status': 'completed',
                'cleaning_metrics': {'stats_normalized': 100}
            }),
            deduplicate_records=Mock(return_value={
                'status': 'completed',
                'deduplication_metrics': {'duplicates_found': 0}
            }),
            perform_feature_engineering=Mock(return_value={
                'status': 'completed',
                'feature_metrics': {'age_adjusted_calculated': 100}
            }),
            update_prospect_rankings=Mock(return_value={
                'status': 'completed', 'rankings_updated': 100
            }),
            cache_processed_results=Mock(return_value={
                'status': 'completed', 'cache_type': 'redis'
            })
        ):
            with patch.object(HistoricalDataPipeline, 'create_ml_training_dataset', return_value=True):
                with patch('builtins.open', create=True):
                    pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
                    result = await pipeline.run_pipeline()

                    assert result is True
                    assert 'total_runtime' in pipeline.metrics
                    assert 'error' not in pipeline.metrics

    @pytest.mark.asyncio
    async def test_run_pipeline_with_error(self):
        """Test pipeline execution with error handling."""
        with patch('scripts.historical_data_ingestion.extract_mlb_historical_data') as mock_extract:
            mock_extract.side_effect = Exception("Extraction failed")

            with patch('builtins.open', create=True):
                pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)

                with pytest.raises(Exception):
                    await pipeline.run_pipeline()

                assert 'error' in pipeline.metrics


class TestPipelinePerformance:
    """Test pipeline performance and scalability."""

    @pytest.mark.asyncio
    async def test_large_dataset_processing(self):
        """Test processing of large datasets."""
        # Create mock large dataset
        large_data = [
            {
                'mlb_id': i,
                'name': f'Player{i}',
                'stats': {'batting_avg': 0.250 + (i % 100) / 1000}
            }
            for i in range(10000)
        ]

        with patch('scripts.historical_data_ingestion.extract_mlb_historical_data') as mock_extract:
            mock_extract.return_value = {
                'status': 'success',
                'records_extracted': len(large_data),
                'errors': []
            }

            pipeline = HistoricalDataPipeline(start_year=2009, end_year=2024)
            result = await pipeline.run_extraction()

            assert result is True
            assert pipeline.metrics['extraction']['mlb']['records_extracted'] == 10000

    @pytest.mark.asyncio
    async def test_rate_limiting_compliance(self):
        """Test that rate limiting is properly enforced."""
        from app.services.data_processing import RateLimiter

        limiter = RateLimiter(max_requests=5, time_window=1)

        start_time = asyncio.get_event_loop().time()

        # Make 10 requests
        for _ in range(10):
            await limiter.wait_if_needed()

        end_time = asyncio.get_event_loop().time()

        # Should have taken at least 1 second due to rate limiting
        assert end_time - start_time >= 1.0


class TestDataQualityIntegration:
    """Test data quality throughout the pipeline."""

    @patch('app.services.pipeline_monitoring.get_db')
    def test_quality_monitoring_throughout_pipeline(self, mock_get_db):
        """Test that quality is monitored at each pipeline stage."""
        from app.services.pipeline_monitoring import DataQualityMonitor

        # Mock database results for different quality checks
        mock_db = MagicMock()
        mock_results = [
            # Completeness check
            MagicMock(**{
                '__getitem__': lambda self, key: {
                    'total_records': 100,
                    'has_mlb_id': 100,
                    'has_name': 98,
                    'has_position': 95,
                    'has_organization': 100,
                    'has_level': 100
                }[key]
            }),
            # Freshness check
            MagicMock(**{
                '__getitem__': lambda self, key: {
                    'latest_update': datetime.utcnow() - timedelta(hours=2),
                    'oldest_update': datetime.utcnow() - timedelta(days=1),
                    'unique_days': 2
                }[key]
            }),
            # Duplicate check results
            MagicMock(**{'__getitem__': lambda self, key: {'duplicate_groups': 0, 'duplicate_records': 0}[key]}),
            MagicMock(**{'__getitem__': lambda self, key: {'total': 100}[key]})
        ]

        mock_db.execute.return_value.fetchone.side_effect = mock_results
        mock_db.execute.return_value.fetchall.return_value = []
        mock_get_db.return_value = mock_db

        monitor = DataQualityMonitor()
        results = monitor.run_all_checks()

        assert 'completeness' in results
        assert 'freshness' in results
        assert 'duplicates' in results
        assert results['completeness']['completeness']['name'] == 0.98


class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    @pytest.mark.asyncio
    async def test_daily_update_scenario(self):
        """Test daily update scenario."""
        # Simulate a daily update with new data
        with patch.multiple(
            'scripts.historical_data_ingestion',
            extract_mlb_historical_data=AsyncMock(return_value={
                'status': 'success',
                'records_extracted': 50,  # Daily update is smaller
                'errors': []
            }),
            extract_fangraphs_data=AsyncMock(return_value={
                'status': 'success',
                'grades_extracted': 10,
                'errors': []
            }),
            validate_ingested_data=Mock(return_value={'status': 'completed', 'validation_results': {}}),
            clean_normalize_data=Mock(return_value={'status': 'completed', 'cleaning_metrics': {}}),
            deduplicate_records=Mock(return_value={'status': 'completed', 'deduplication_metrics': {}}),
            perform_feature_engineering=Mock(return_value={'status': 'completed', 'feature_metrics': {}}),
            update_prospect_rankings=Mock(return_value={'status': 'completed', 'rankings_updated': 50}),
            cache_processed_results=Mock(return_value={'status': 'completed'})
        ):
            with patch.object(HistoricalDataPipeline, 'create_ml_training_dataset', return_value=True):
                with patch('builtins.open', create=True):
                    # Run with just current year for daily update
                    pipeline = HistoricalDataPipeline(start_year=2024, end_year=2024)
                    result = await pipeline.run_pipeline()

                    assert result is True
                    assert pipeline.metrics['extraction']['mlb']['records_extracted'] == 50

    @pytest.mark.asyncio
    async def test_recovery_from_partial_failure(self):
        """Test recovery from partial pipeline failure."""
        call_count = 0

        async def mock_extract_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary failure")
            return {'status': 'success', 'records_extracted': 100, 'errors': []}

        with patch('scripts.historical_data_ingestion.extract_mlb_historical_data', mock_extract_with_retry):
            with patch('builtins.open', create=True):
                pipeline = HistoricalDataPipeline(start_year=2024, end_year=2024)

                # First attempt should fail
                with pytest.raises(Exception):
                    await pipeline.run_extraction()

                # Second attempt should succeed
                result = await pipeline.run_extraction()
                assert result is True


@pytest.fixture
def mock_pipeline_environment():
    """Fixture to set up mock pipeline environment."""
    with patch.multiple(
        'scripts.historical_data_ingestion',
        engine=MagicMock(),
        settings=MagicMock()
    ):
        yield


@pytest.fixture
def sample_pipeline_config():
    """Fixture for sample pipeline configuration."""
    return {
        'start_year': 2020,
        'end_year': 2024,
        'batch_size': 100,
        'rate_limit': 1000,
        'cache_ttl': 24
    }