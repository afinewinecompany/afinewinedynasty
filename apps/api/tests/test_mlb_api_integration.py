import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError
from aiohttp.web_response import Response

from app.services.mlb_api_service import (
    MLBAPIClient,
    MLBStatsAPIError,
    RateLimitExceededError,
)


@pytest.fixture
def mlb_client():
    """Create MLB API client for testing."""
    return MLBAPIClient()


@pytest.fixture
def mock_response_data():
    """Mock MLB API response data."""
    return {
        "people": [
            {
                "id": 123456,
                "fullName": "Test Player",
                "primaryPosition": {"code": "3", "name": "First Base"},
                "currentTeam": {"id": 111, "name": "Test Team"},
                "birthDate": "2000-01-01",
                "height": "6' 2\"",
                "weight": 200
            }
        ]
    }


class TestMLBAPIClient:
    """Test cases for MLB API client."""

    @pytest.mark.asyncio
    async def test_context_manager(self, mlb_client):
        """Test async context manager functionality."""
        async with mlb_client as client:
            assert client.session is not None
        # Session should be closed after exit
        assert mlb_client.session is None or mlb_client.session.closed

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, mlb_client):
        """Test rate limit checking."""
        # Set request count to daily limit
        mlb_client.request_count = mlb_client.daily_limit

        with pytest.raises(RateLimitExceededError):
            mlb_client._check_rate_limit()

    def test_daily_counter_reset(self, mlb_client):
        """Test daily counter reset functionality."""
        # Set request count and old date
        mlb_client.request_count = 100
        mlb_client.last_reset = datetime(2023, 1, 1)

        mlb_client._reset_daily_counter()

        assert mlb_client.request_count == 0
        assert mlb_client.last_reset.date() == datetime.now().date()

    @pytest.mark.asyncio
    async def test_successful_request(self, mlb_client, mock_response_data):
        """Test successful API request."""
        # Mock aiohttp session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        mlb_client.session = mock_session

        result = await mlb_client._make_request("people")

        assert result == mock_response_data
        assert mlb_client.request_count == 1

    @pytest.mark.asyncio
    async def test_api_error_handling(self, mlb_client):
        """Test API error handling."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_session = AsyncMock()
        mock_session.get = AsyncMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        mlb_client.session = mock_session

        with pytest.raises(MLBStatsAPIError, match="MLB API request failed with status 500"):
            await mlb_client._make_request("people")

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, mlb_client):
        """Test API rate limit error handling."""
        mock_response = AsyncMock()
        mock_response.status = 429

        mock_session = AsyncMock()
        mock_session.get = AsyncMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        mlb_client.session = mock_session

        with pytest.raises(RateLimitExceededError):
            await mlb_client._make_request("people")

    @pytest.mark.asyncio
    async def test_network_error_handling(self, mlb_client):
        """Test network error handling."""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=ClientError("Network error"))

        mlb_client.session = mock_session

        with pytest.raises(MLBStatsAPIError, match="Network error during MLB API request"):
            await mlb_client._make_request("people")

    @pytest.mark.asyncio
    async def test_get_prospects_data(self, mlb_client, mock_response_data):
        """Test get prospects data method."""
        with patch.object(mlb_client, '_make_request', return_value=mock_response_data) as mock_request:
            result = await mlb_client.get_prospects_data()

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert "people" in args[0]
            assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_get_player_stats(self, mlb_client):
        """Test get player stats method."""
        mock_stats_data = {
            "stats": [
                {
                    "type": {"displayName": "season"},
                    "group": {"displayName": "hitting"},
                    "stats": {
                        "gamesPlayed": 100,
                        "atBats": 350,
                        "hits": 95,
                        "avg": ".271"
                    }
                }
            ]
        }

        with patch.object(mlb_client, '_make_request', return_value=mock_stats_data) as mock_request:
            result = await mlb_client.get_player_stats(123456)

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert "people/123456/stats" in args[0]
            assert result == mock_stats_data

    @pytest.mark.asyncio
    async def test_get_teams_data(self, mlb_client):
        """Test get teams data method."""
        mock_teams_data = {
            "teams": [
                {
                    "id": 111,
                    "name": "Test Team",
                    "abbreviation": "TT",
                    "teamName": "Team",
                    "locationName": "Test City"
                }
            ]
        }

        with patch.object(mlb_client, '_make_request', return_value=mock_teams_data) as mock_request:
            result = await mlb_client.get_teams_data()

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            assert "teams" in args[0]
            assert result == mock_teams_data

    def test_get_request_stats(self, mlb_client):
        """Test request statistics method."""
        mlb_client.request_count = 50
        mlb_client.daily_limit = 1000

        stats = mlb_client.get_request_stats()

        assert stats["requests_made_today"] == 50
        assert stats["daily_limit"] == 1000
        assert stats["requests_remaining"] == 950
        assert "last_reset" in stats

    @pytest.mark.asyncio
    async def test_session_not_initialized_error(self, mlb_client):
        """Test error when session is not initialized."""
        mlb_client.session = None

        with pytest.raises(MLBStatsAPIError, match="Session not initialized"):
            await mlb_client._make_request("people")

    @pytest.mark.asyncio
    async def test_retry_mechanism(self, mlb_client):
        """Test retry mechanism on failures."""
        # Mock that first call fails, second succeeds
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"success": True})

        mock_response_failure = AsyncMock()
        mock_response_failure.status = 500
        mock_response_failure.text = AsyncMock(return_value="Server Error")

        mock_session = AsyncMock()
        mock_session.get = AsyncMock()

        # First call fails, second succeeds
        mock_session.get.return_value.__aenter__.side_effect = [
            mock_response_failure,
            mock_response_success
        ]
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        mlb_client.session = mock_session

        # Should succeed after retry
        with patch.object(mlb_client, 'get_prospects_data', wraps=mlb_client.get_prospects_data):
            result = await mlb_client.get_prospects_data()
            assert result is not None


class TestDataIngestionService:
    """Test cases for data ingestion service."""

    @pytest.fixture
    def ingestion_service(self):
        """Create data ingestion service for testing."""
        from app.services.data_ingestion_service import DataIngestionService
        return DataIngestionService()

    @pytest.mark.asyncio
    async def test_sample_prospect_data_creation(self, ingestion_service):
        """Test sample prospect data creation."""
        team_data = {
            "id": 123,
            "name": "Test Team"
        }

        prospect_data = ingestion_service._create_sample_prospect_data(team_data)

        assert prospect_data["mlb_id"] == "P000123"
        assert prospect_data["name"] == "Sample Player 123"
        assert prospect_data["organization"] == "Test Team"
        assert prospect_data["position"] == "OF"
        assert prospect_data["level"] == "AA"
        assert prospect_data["age"] == 22

    @pytest.mark.asyncio
    async def test_sample_stats_data_creation(self, ingestion_service):
        """Test sample stats data creation."""
        from app.db.models import Prospect
        from datetime import datetime

        prospect = Prospect(
            id=1,
            mlb_id="P000123",
            name="Test Player",
            position="OF"
        )

        stats_data = ingestion_service._create_sample_stats_data(prospect, 2024)

        assert stats_data["season"] == 2024
        assert stats_data["games_played"] == 100
        assert stats_data["at_bats"] == 350
        assert stats_data["hits"] == 95
        assert stats_data["batting_avg"] == 0.271
        assert "date" in stats_data

    def test_reset_stats(self, ingestion_service):
        """Test statistics reset functionality."""
        # Set some stats
        ingestion_service.ingestion_stats["prospects_added"] = 5
        ingestion_service.ingestion_stats["errors"] = ["test error"]

        ingestion_service._reset_stats()

        assert ingestion_service.ingestion_stats["prospects_added"] == 0
        assert ingestion_service.ingestion_stats["prospects_updated"] == 0
        assert ingestion_service.ingestion_stats["errors"] == []

    @pytest.mark.asyncio
    async def test_get_ingestion_status(self, ingestion_service):
        """Test ingestion status retrieval."""
        status = await ingestion_service.get_ingestion_status()

        assert "prospects_processed" in status
        assert "prospects_added" in status
        assert "mlb_api_stats" in status
        assert "last_run" in status


class TestSchedulerService:
    """Test cases for scheduler service."""

    @pytest.fixture
    def scheduler_service(self):
        """Create scheduler service for testing."""
        from app.services.scheduler_service import SchedulerService
        return SchedulerService()

    def test_scheduler_initialization(self, scheduler_service):
        """Test scheduler service initialization."""
        assert not scheduler_service.is_running
        assert len(scheduler_service.jobs) >= 2  # Default jobs should be created
        assert "daily_data_ingestion" in scheduler_service.jobs
        assert "hourly_health_check" in scheduler_service.jobs

    def test_job_scheduling(self, scheduler_service):
        """Test job scheduling functionality."""
        from datetime import time

        async def test_job():
            return {"status": "test"}

        scheduler_service.schedule_job(
            job_id="test_job",
            name="Test Job",
            job_function=test_job,
            scheduled_time=time(9, 0)
        )

        assert "test_job" in scheduler_service.jobs
        job = scheduler_service.jobs["test_job"]
        assert job.name == "Test Job"
        assert job.scheduled_time == time(9, 0)
        assert job.is_active

    def test_job_activation_deactivation(self, scheduler_service):
        """Test job activation and deactivation."""
        from datetime import time

        async def test_job():
            return {"status": "test"}

        scheduler_service.schedule_job(
            job_id="test_job",
            name="Test Job",
            job_function=test_job,
            scheduled_time=time(9, 0)
        )

        # Test deactivation
        result = scheduler_service.deactivate_job("test_job")
        assert result is True
        assert not scheduler_service.jobs["test_job"].is_active

        # Test activation
        result = scheduler_service.activate_job("test_job")
        assert result is True
        assert scheduler_service.jobs["test_job"].is_active

        # Test non-existent job
        result = scheduler_service.deactivate_job("non_existent")
        assert result is False

    def test_get_job_status(self, scheduler_service):
        """Test job status retrieval."""
        status = scheduler_service.get_job_status("daily_data_ingestion")

        assert status is not None
        assert status["id"] == "daily_data_ingestion"
        assert "name" in status
        assert "is_active" in status
        assert "next_run" in status

        # Test non-existent job
        status = scheduler_service.get_job_status("non_existent")
        assert status is None

    def test_get_all_jobs_status(self, scheduler_service):
        """Test all jobs status retrieval."""
        status = scheduler_service.get_all_jobs_status()

        assert "scheduler_running" in status
        assert "jobs" in status
        assert len(status["jobs"]) >= 2


class TestDataValidationService:
    """Test cases for data validation service."""

    @pytest.fixture
    def validation_service(self):
        """Create validation service for testing."""
        from app.services.data_validation_service import DataValidationService
        return DataValidationService()

    @pytest.mark.asyncio
    async def test_validate_prospect_data_valid(self, validation_service):
        """Test validation of valid prospect data."""
        valid_prospect = {
            "mlb_id": "P123456",
            "name": "Test Player",
            "position": "OF",
            "organization": "Test Team",
            "level": "AA",
            "age": 22,
            "eta_year": 2026
        }

        result = await validation_service.validate_prospect_data(valid_prospect)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.data_quality_score > 0.9

    @pytest.mark.asyncio
    async def test_validate_prospect_data_invalid(self, validation_service):
        """Test validation of invalid prospect data."""
        invalid_prospect = {
            "mlb_id": "",  # Empty MLB ID
            "name": "A",   # Too short name
            "position": "INVALID",  # Invalid position
            "age": 100,    # Invalid age
            "eta_year": 1990  # Invalid ETA year
        }

        result = await validation_service.validate_prospect_data(invalid_prospect)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert result.data_quality_score < 0.5

    @pytest.mark.asyncio
    async def test_validate_stats_data_valid(self, validation_service):
        """Test validation of valid stats data."""
        from datetime import date

        valid_stats = {
            "date": date.today(),
            "season": 2024,
            "games_played": 100,
            "at_bats": 350,
            "hits": 95,
            "home_runs": 12,
            "rbi": 55,
            "batting_avg": 0.271,
            "on_base_pct": 0.355,
            "slugging_pct": 0.420
        }

        result = await validation_service.validate_stats_data(valid_stats)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.data_quality_score > 0.8

    @pytest.mark.asyncio
    async def test_validate_stats_data_with_outliers(self, validation_service):
        """Test validation of stats data with outliers."""
        from datetime import date

        outlier_stats = {
            "date": date.today(),
            "season": 2024,
            "games_played": 100,
            "at_bats": 350,
            "hits": 95,
            "home_runs": 70,  # Outlier - too many home runs
            "batting_avg": 0.750,  # Outlier - too high batting average
            "era": 0.10  # Outlier - too low ERA
        }

        result = await validation_service.validate_stats_data(outlier_stats)

        assert result.is_valid  # Structure is valid
        assert len(result.outliers_detected) > 0
        assert any(outlier["metric"] == "batting_avg" for outlier in result.outliers_detected)

    @pytest.mark.asyncio
    async def test_validate_stats_consistency_errors(self, validation_service):
        """Test validation of inconsistent stats data."""
        from datetime import date

        inconsistent_stats = {
            "date": date.today(),
            "season": 2024,
            "at_bats": 300,
            "hits": 350,  # More hits than at-bats - impossible
            "home_runs": 400  # More home runs than hits - impossible
        }

        result = await validation_service.validate_stats_data(inconsistent_stats)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("hits cannot exceed at-bats" in error.lower() for error in result.errors)

    @pytest.mark.asyncio
    async def test_validate_mlb_api_response_player(self, validation_service):
        """Test validation of MLB API player response."""
        valid_response = {
            "people": [
                {
                    "id": 123456,
                    "fullName": "Test Player",
                    "primaryPosition": {"code": "3", "name": "First Base"},
                    "currentTeam": {"id": 111, "name": "Test Team"},
                    "birthDate": "2000-01-01",
                    "height": "6' 2\"",
                    "weight": 200
                }
            ]
        }

        result = await validation_service.validate_mlb_api_response(valid_response, "player")

        assert result.is_valid
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_mlb_api_response_invalid(self, validation_service):
        """Test validation of invalid MLB API response."""
        invalid_response = {
            "people": [
                {
                    "id": "invalid",  # Should be integer
                    "fullName": "",   # Empty name
                    "weight": 1000    # Invalid weight
                }
            ]
        }

        result = await validation_service.validate_mlb_api_response(invalid_response, "player")

        assert not result.is_valid
        assert len(result.errors) > 0

    def test_detect_statistical_outliers(self, validation_service):
        """Test statistical outlier detection."""
        stats_with_outliers = {
            "batting_avg": 0.600,  # Outlier
            "home_runs": 80,       # Outlier
            "era": 15.0,           # Outlier
            "woba": 0.280          # Normal
        }

        outliers = validation_service._detect_statistical_outliers(stats_with_outliers)

        assert len(outliers) >= 3
        outlier_metrics = [o["metric"] for o in outliers]
        assert "batting_avg" in outlier_metrics
        assert "home_runs" in outlier_metrics
        assert "era" in outlier_metrics

    def test_check_stats_consistency(self, validation_service):
        """Test stats consistency checking."""
        inconsistent_stats = {
            "at_bats": 300,
            "hits": 320,    # Impossible
            "home_runs": 350,  # Impossible
            "innings_pitched": 100,
            "earned_runs": 50,
            "era": 1.00     # Inconsistent with earned runs/innings
        }

        errors = validation_service._check_stats_consistency(inconsistent_stats)

        assert len(errors) > 0
        assert any("hits cannot exceed at-bats" in error.lower() for error in errors)

    @pytest.mark.asyncio
    async def test_generate_quality_report(self, validation_service):
        """Test quality report generation."""
        from app.schemas.prospect_schemas import ValidationResult

        # Create mock validation results
        results = [
            ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                data_quality_score=0.9,
                outliers_detected=[]
            ),
            ValidationResult(
                is_valid=False,
                errors=["Invalid field"],
                warnings=["Missing data"],
                data_quality_score=0.6,
                outliers_detected=[{"type": "range_outlier"}]
            )
        ]

        report = await validation_service.generate_quality_report(results)

        assert report.total_records_validated == 2
        assert report.valid_records == 1
        assert report.invalid_records == 1
        assert "Invalid field" in report.validation_errors
        assert report.overall_quality_score == 0.75


class TestDuplicateDetectionService:
    """Test cases for duplicate detection service."""

    @pytest.fixture
    def duplicate_service(self):
        """Create duplicate detection service for testing."""
        from app.services.duplicate_detection_service import DuplicateDetectionService
        return DuplicateDetectionService()

    def test_calculate_name_similarity_exact(self, duplicate_service):
        """Test exact name similarity calculation."""
        similarity = duplicate_service._calculate_name_similarity("John Smith", "John Smith")
        assert similarity == 1.0

    def test_calculate_name_similarity_case_insensitive(self, duplicate_service):
        """Test case-insensitive name similarity."""
        similarity = duplicate_service._calculate_name_similarity("John Smith", "john smith")
        assert similarity == 1.0

    def test_calculate_name_similarity_reversed(self, duplicate_service):
        """Test reversed name similarity."""
        similarity = duplicate_service._calculate_name_similarity("John Smith", "Smith John")
        assert similarity >= 0.8  # Should be high for reversed names

    def test_calculate_name_similarity_partial(self, duplicate_service):
        """Test partial name similarity."""
        similarity = duplicate_service._calculate_name_similarity("John Smith", "John Smyth")
        assert 0.7 <= similarity <= 0.95

    def test_calculate_name_similarity_different(self, duplicate_service):
        """Test different name similarity."""
        similarity = duplicate_service._calculate_name_similarity("John Smith", "Mary Johnson")
        assert similarity < 0.5

    def test_normalize_name(self, duplicate_service):
        """Test name normalization."""
        normalized = duplicate_service._normalize_name("John Smith Jr.")
        assert normalized == "john smith"

        normalized = duplicate_service._normalize_name("O'Connor, Mike III")
        assert normalized == "o connor mike"

    def test_calculate_text_similarity(self, duplicate_service):
        """Test text similarity calculation."""
        similarity = duplicate_service._calculate_text_similarity("New York Yankees", "NY Yankees")
        assert similarity > 0.5

        similarity = duplicate_service._calculate_text_similarity("Boston Red Sox", "New York Yankees")
        assert similarity < 0.3

    def test_resolve_field_conflict_preserve_non_null(self, duplicate_service):
        """Test field conflict resolution with preserve_non_null rule."""
        from app.db.models import Prospect
        from datetime import datetime

        primary = Prospect(id=1, name="John", updated_at=datetime.now())
        duplicate = Prospect(id=2, name="Johnny", updated_at=datetime.now())

        result = duplicate_service._resolve_field_conflict(
            "test_field", "primary_value", None, "preserve_non_null", primary, duplicate
        )
        assert result == "primary_value"

        result = duplicate_service._resolve_field_conflict(
            "test_field", None, "duplicate_value", "preserve_non_null", primary, duplicate
        )
        assert result == "duplicate_value"

    def test_resolve_field_conflict_prefer_longer(self, duplicate_service):
        """Test field conflict resolution with prefer_longer rule."""
        from app.db.models import Prospect
        from datetime import datetime

        primary = Prospect(id=1, updated_at=datetime.now())
        duplicate = Prospect(id=2, updated_at=datetime.now())

        result = duplicate_service._resolve_field_conflict(
            "name", "John", "Jonathan", "prefer_longer", primary, duplicate
        )
        assert result == "Jonathan"

        result = duplicate_service._resolve_field_conflict(
            "name", "Alexander", "Alex", "prefer_longer", primary, duplicate
        )
        assert result == "Alexander"

    def test_resolve_field_conflict_prefer_higher_level(self, duplicate_service):
        """Test field conflict resolution with prefer_higher rule for levels."""
        from app.db.models import Prospect
        from datetime import datetime

        primary = Prospect(id=1, updated_at=datetime.now())
        duplicate = Prospect(id=2, updated_at=datetime.now())

        result = duplicate_service._resolve_field_conflict(
            "level", "AA", "AAA", "prefer_higher", primary, duplicate
        )
        assert result == "AAA"

        result = duplicate_service._resolve_field_conflict(
            "level", "A", "Rookie", "prefer_higher", primary, duplicate
        )
        assert result == "A"

    def test_resolve_field_conflict_prefer_younger(self, duplicate_service):
        """Test field conflict resolution with prefer_younger rule."""
        from app.db.models import Prospect
        from datetime import datetime

        primary = Prospect(id=1, updated_at=datetime.now())
        duplicate = Prospect(id=2, updated_at=datetime.now())

        result = duplicate_service._resolve_field_conflict(
            "age", 25, 23, "prefer_younger", primary, duplicate
        )
        assert result == 23

        # Should prefer primary if age difference is too large
        result = duplicate_service._resolve_field_conflict(
            "age", 25, 20, "prefer_younger", primary, duplicate
        )
        assert result == 25

    def test_prospect_to_dict(self, duplicate_service):
        """Test prospect model to dictionary conversion."""
        from app.db.models import Prospect
        from datetime import datetime

        now = datetime.now()
        prospect = Prospect(
            id=1,
            mlb_id="P123456",
            name="Test Player",
            position="OF",
            organization="Test Team",
            level="AA",
            age=22,
            eta_year=2026,
            created_at=now,
            updated_at=now
        )

        result = duplicate_service._prospect_to_dict(prospect)

        assert result["id"] == 1
        assert result["mlb_id"] == "P123456"
        assert result["name"] == "Test Player"
        assert result["position"] == "OF"
        assert result["organization"] == "Test Team"
        assert result["level"] == "AA"
        assert result["age"] == 22
        assert result["eta_year"] == 2026

    @pytest.mark.asyncio
    async def test_compare_prospects_exact_mlb_id(self, duplicate_service):
        """Test prospect comparison with exact MLB ID match."""
        from app.db.models import Prospect

        prospect_data = {
            "mlb_id": "P123456",
            "name": "John Smith",
            "position": "OF"
        }

        existing_prospect = Prospect(
            id=2,
            mlb_id="P123456",
            name="John Smith",
            position="OF"
        )

        match = await duplicate_service._compare_prospects(prospect_data, existing_prospect)

        assert match is not None
        assert match.match_type == "exact_mlb_id"
        assert match.confidence_score == 1.0
        assert "mlb_id" in match.matching_fields
        assert match.merge_recommendation == "merge"

    @pytest.mark.asyncio
    async def test_compare_prospects_name_similarity(self, duplicate_service):
        """Test prospect comparison with high name similarity."""
        from app.db.models import Prospect

        prospect_data = {
            "name": "John Smith",
            "position": "OF",
            "organization": "Yankees"
        }

        existing_prospect = Prospect(
            id=2,
            name="Johnny Smith",
            position="OF",
            organization="Yankees"
        )

        match = await duplicate_service._compare_prospects(prospect_data, existing_prospect)

        assert match is not None
        assert match.match_type in ["name_similarity", "fuzzy_match"]
        assert match.confidence_score > 0.75
        assert "name" in match.matching_fields
        assert "position" in match.matching_fields

    @pytest.mark.asyncio
    async def test_compare_prospects_no_match(self, duplicate_service):
        """Test prospect comparison with no significant similarity."""
        from app.db.models import Prospect

        prospect_data = {
            "name": "John Smith",
            "position": "OF"
        }

        existing_prospect = Prospect(
            id=2,
            name="Mary Johnson",
            position="P"
        )

        match = await duplicate_service._compare_prospects(prospect_data, existing_prospect)

        assert match is None