"""
Test suite for historical data ingestion pipeline.
Tests data extraction, validation, and processing functions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import pandas as pd
import json
import asyncio

from app.services.data_processing import (
    RateLimiter,
    get_mlb_api_session,
    extract_mlb_historical_data,
    extract_fangraphs_data,
    validate_ingested_data,
    clean_normalize_data,
    deduplicate_records,
    perform_feature_engineering,
    update_prospect_rankings,
    cache_processed_results,
    calculate_age,
    process_player_stats,
    standardize_grade,
    save_batch_to_db,
    save_scouting_grades_to_db
)


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_within_limit(self):
        """Test that rate limiter allows requests within the limit."""
        limiter = RateLimiter(max_requests=2, time_window=1)

        start_time = asyncio.get_event_loop().time()
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        end_time = asyncio.get_event_loop().time()

        # Should complete quickly as we're within limits
        assert end_time - start_time < 0.5

    @pytest.mark.asyncio
    async def test_rate_limiter_delays_when_limit_exceeded(self):
        """Test that rate limiter delays when limit is exceeded."""
        limiter = RateLimiter(max_requests=2, time_window=1)

        # Make two requests quickly
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()

        # Third request should be delayed
        start_time = asyncio.get_event_loop().time()
        await limiter.wait_if_needed()
        end_time = asyncio.get_event_loop().time()

        # Should have waited approximately 1 second
        assert end_time - start_time >= 0.9


class TestMLBDataExtraction:
    """Test MLB API data extraction."""

    @patch('app.services.data_processing.get_mlb_api_session')
    @patch('app.services.data_processing.save_batch_to_db')
    @pytest.mark.asyncio
    async def test_extract_mlb_historical_data_success(self, mock_save, mock_session):
        """Test successful MLB data extraction."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'people': [
                {
                    'id': 123456,
                    'fullName': 'Test Player',
                    'birthDate': '2000-01-01',
                    'primaryPosition': {'abbreviation': 'SS'},
                    'currentTeam': {'name': 'Test Team'}
                }
            ]
        }

        mock_session.return_value.get.return_value = mock_response

        # Run extraction for a single year
        result = await extract_mlb_historical_data(
            start_year=2024,
            end_year=2024,
            rate_limit=10,
            batch_size=1
        )

        assert result['status'] == 'success'
        assert result['years_processed'] == 1
        assert mock_save.called

    @patch('app.services.data_processing.get_mlb_api_session')
    @pytest.mark.asyncio
    async def test_extract_mlb_historical_data_handles_errors(self, mock_session):
        """Test MLB data extraction error handling."""
        # Mock API error
        mock_session.return_value.get.side_effect = Exception("API Error")

        result = await extract_mlb_historical_data(
            start_year=2024,
            end_year=2024,
            rate_limit=10,
            batch_size=1
        )

        assert result['status'] == 'success'
        assert len(result['errors']) > 0


class TestFangraphsDataExtraction:
    """Test Fangraphs data extraction."""

    @patch('aiohttp.ClientSession')
    @patch('app.services.data_processing.save_scouting_grades_to_db')
    @pytest.mark.asyncio
    async def test_extract_fangraphs_data_success(self, mock_save, mock_session_class):
        """Test successful Fangraphs data extraction."""
        # Mock async session
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'prospects': [
                {
                    'name': 'Test Player',
                    'fv': 55,
                    'hit': 60,
                    'power': 50,
                    'speed': 45,
                    'field': 50,
                    'arm': 55
                }
            ]
        })

        mock_session.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session

        result = await extract_fangraphs_data(
            start_year=2024,
            end_year=2024,
            rate_limit_per_second=1
        )

        assert result['status'] == 'success'
        assert result['years_processed'] == 1
        assert mock_save.called


class TestDataValidation:
    """Test data validation functions."""

    @patch('app.services.data_processing.get_db')
    def test_validate_ingested_data_schema_check(self, mock_get_db):
        """Test schema validation."""
        # Mock database
        mock_db = MagicMock()
        mock_result = [
            {'id': 1, 'mlb_id': 123456, 'name': 'Test Player',
             'position': 'SS', 'organization': 'Test Team', 'level': 'Double-A'}
        ]
        mock_db.execute.return_value.fetchall.return_value = mock_result
        mock_get_db.return_value = mock_db

        result = validate_ingested_data(
            check_schemas=True,
            check_outliers=False,
            check_consistency=False
        )

        assert result['status'] == 'completed'
        assert 'validation_results' in result
        assert result['validation_results']['total_records_validated'] >= 0

    @patch('app.services.data_processing.get_db')
    @patch('pandas.read_sql')
    def test_validate_ingested_data_outlier_detection(self, mock_read_sql, mock_get_db):
        """Test outlier detection."""
        # Mock database
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock stats dataframe
        mock_df = pd.DataFrame({
            'prospect_id': [1, 2, 3, 4, 5],
            'batting_avg': [0.300, 0.280, 0.290, 0.999, 0.310]  # 0.999 is an outlier
        })
        mock_read_sql.return_value = mock_df

        result = validate_ingested_data(
            check_schemas=False,
            check_outliers=True,
            check_consistency=False
        )

        assert result['status'] == 'completed'
        assert len(result['validation_results']['outliers']) > 0


class TestDataCleaning:
    """Test data cleaning and normalization."""

    @patch('app.services.data_processing.get_db')
    def test_clean_normalize_data_name_standardization(self, mock_get_db):
        """Test name standardization."""
        mock_db = MagicMock()
        mock_db.execute.return_value.rowcount = 5
        mock_get_db.return_value = mock_db

        result = clean_normalize_data(
            standardize_names=True,
            normalize_stats=False,
            handle_missing='ignore'
        )

        assert result['status'] == 'completed'
        assert result['cleaning_metrics']['names_standardized'] == 5

    @patch('app.services.data_processing.get_db')
    @patch('pandas.read_sql')
    def test_clean_normalize_data_stats_normalization(self, mock_read_sql, mock_get_db):
        """Test statistics normalization."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock stats dataframe with values needing normalization
        mock_df = pd.DataFrame({
            'id': [1, 2],
            'batting_avg': [300, 0.280],  # 300 needs to be converted to 0.300
            'on_base_pct': [38, 0.350],   # 38 needs to be converted to 0.380
            'slugging_pct': [55, 0.480]   # 55 needs to be converted to 0.550
        })
        mock_read_sql.return_value = mock_df

        result = clean_normalize_data(
            standardize_names=False,
            normalize_stats=True,
            handle_missing='ignore'
        )

        assert result['status'] == 'completed'
        assert result['cleaning_metrics']['stats_normalized'] == 2


class TestDeduplication:
    """Test record deduplication."""

    @patch('app.services.data_processing.get_db')
    def test_deduplicate_records_most_recent(self, mock_get_db):
        """Test deduplication with most recent strategy."""
        mock_db = MagicMock()

        # Mock duplicate query result
        mock_duplicates = [
            {'mlb_id': 123456, 'count': 3},
            {'mlb_id': 789012, 'count': 2}
        ]
        mock_db.execute.return_value.fetchall.return_value = mock_duplicates
        mock_get_db.return_value = mock_db

        result = deduplicate_records(
            merge_strategy='most_recent',
            conflict_resolution='weighted_average'
        )

        assert result['status'] == 'completed'
        assert result['deduplication_metrics']['duplicates_found'] == 2
        assert result['deduplication_metrics']['records_merged'] == 3  # 2 + 1 from the duplicates


class TestFeatureEngineering:
    """Test feature engineering functions."""

    @patch('app.services.data_processing.get_db')
    @patch('pandas.read_sql')
    def test_perform_feature_engineering_age_adjusted(self, mock_read_sql, mock_get_db):
        """Test age-adjusted metrics calculation."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock stats dataframe
        mock_df = pd.DataFrame({
            'id': [1, 2, 3, 4],
            'prospect_id': [1, 2, 3, 4],
            'age': [20, 20, 21, 21],
            'level': ['Double-A', 'Double-A', 'Double-A', 'Double-A'],
            'batting_avg': [0.300, 0.280, 0.290, 0.310]
        })
        mock_read_sql.return_value = mock_df

        result = perform_feature_engineering(
            calculate_age_adjusted=True,
            calculate_progression_rates=False,
            calculate_peer_comparisons=False
        )

        assert result['status'] == 'completed'
        assert result['feature_metrics']['age_adjusted_calculated'] == 4

    @patch('app.services.data_processing.get_db')
    @patch('pandas.read_sql')
    def test_perform_feature_engineering_progression_rates(self, mock_read_sql, mock_get_db):
        """Test level progression rate calculation."""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock progression dataframe
        mock_df = pd.DataFrame({
            'prospect_id': [1, 2],
            'level_changes': [2, 1],
            'avg_days_between_levels': [180, 365]
        })
        mock_read_sql.return_value = mock_df

        result = perform_feature_engineering(
            calculate_age_adjusted=False,
            calculate_progression_rates=True,
            calculate_peer_comparisons=False
        )

        assert result['status'] == 'completed'
        assert result['feature_metrics']['progression_rates_calculated'] == 2


class TestHelperFunctions:
    """Test helper functions."""

    def test_calculate_age(self):
        """Test age calculation."""
        assert calculate_age('2000-01-01', 2024) == 24
        assert calculate_age('1995-06-15', 2024) == 29
        assert calculate_age(None, 2024) is None
        assert calculate_age('invalid-date', 2024) is None

    def test_process_player_stats(self):
        """Test player stats processing."""
        stats_data = {
            'stats': [
                {
                    'group': {'displayName': 'hitting'},
                    'stats': {
                        'avg': 0.300,
                        'obp': 0.380,
                        'slg': 0.550,
                        'homeRuns': 25,
                        'rbi': 85
                    }
                },
                {
                    'group': {'displayName': 'pitching'},
                    'stats': {
                        'era': 3.45,
                        'whip': 1.25,
                        'strikeoutsPer9Inn': 9.5,
                        'inningsPitched': 150.0
                    }
                }
            ]
        }

        processed = process_player_stats(stats_data)

        assert processed['batting_avg'] == 0.300
        assert processed['on_base_pct'] == 0.380
        assert processed['era'] == 3.45
        assert processed['strikeouts_per_nine'] == 9.5

    def test_standardize_grade(self):
        """Test scouting grade standardization."""
        # 2-8 scale to 20-80
        assert standardize_grade(5.5) == 55

        # 0-100 scale to 20-80
        assert standardize_grade(90) == 74  # 20 + (90/100) * 60

        # Already on 20-80 scale
        assert standardize_grade(55) == 55

        # None handling
        assert standardize_grade(None) is None

        # Invalid value handling
        assert standardize_grade('invalid') is None


class TestIntegration:
    """Integration tests for complete pipeline."""

    @patch('app.services.data_processing.get_db')
    def test_update_prospect_rankings(self, mock_get_db):
        """Test prospect ranking updates."""
        mock_db = MagicMock()
        mock_db.execute.return_value.rowcount = 100
        mock_get_db.return_value = mock_db

        result = update_prospect_rankings()

        assert result['status'] == 'completed'
        assert result['rankings_updated'] == 100

    def test_cache_processed_results(self):
        """Test result caching."""
        result = cache_processed_results(
            cache_type='redis',
            ttl_hours=24
        )

        assert result['status'] == 'completed'
        assert result['cache_type'] == 'redis'
        assert result['ttl_hours'] == 24


@pytest.fixture
def mock_database():
    """Fixture for mocking database connections."""
    with patch('app.services.data_processing.get_db') as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


@pytest.fixture
def sample_prospect_data():
    """Fixture for sample prospect data."""
    return {
        'mlb_id': 123456,
        'name': 'Test Player',
        'position': 'SS',
        'organization': 'Test Team',
        'level': 'Double-A',
        'age': 22,
        'stats': {
            'batting_avg': 0.300,
            'on_base_pct': 0.380,
            'slugging_pct': 0.550,
            'home_runs': 25,
            'rbi': 85
        }
    }


@pytest.fixture
def sample_scouting_grades():
    """Fixture for sample scouting grades."""
    return {
        'player_name': 'Test Player',
        'source': 'Fangraphs',
        'overall_grade': 55,
        'hit_grade': 60,
        'power_grade': 50,
        'speed_grade': 45,
        'field_grade': 50,
        'arm_grade': 55
    }