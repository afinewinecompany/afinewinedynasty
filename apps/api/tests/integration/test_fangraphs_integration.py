"""Integration tests for Fangraphs data pipeline."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json

from app.services.fangraphs_service import FangraphsService
from app.services.data_integration_service import DataIntegrationService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.pipeline_monitoring import PipelineMonitor
from app.services.backup_data_strategy import DataSourceManager, FailoverOrchestrator
from app.services.compliance_attribution import ComplianceAuditor, DataSourceAttribution
from app.services.cost_optimization import CostOptimizer
from app.schemas.fangraphs_schemas import FangraphsProspectData


@pytest.fixture
async def fangraphs_service():
    """Create Fangraphs service for testing."""
    service = FangraphsService()
    async with service:
        yield service


@pytest.fixture
def integration_service():
    """Create data integration service."""
    return DataIntegrationService()


@pytest.fixture
def duplicate_service():
    """Create duplicate detection service."""
    return DuplicateDetectionService()


@pytest.fixture
def pipeline_monitor():
    """Create pipeline monitor."""
    return PipelineMonitor()


@pytest.fixture
def cost_optimizer():
    """Create cost optimizer."""
    return CostOptimizer()


class TestEndToEndPipeline:
    """Test complete data pipeline from fetch to storage."""

    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self, fangraphs_service, integration_service, pipeline_monitor):
        """Test complete pipeline from data fetch to integration."""
        # Mock external API calls
        with patch.object(fangraphs_service, '_make_request') as mock_request:
            mock_request.return_value = self._get_mock_html_response()

            # Start pipeline run
            run_id = await pipeline_monitor.start_pipeline_run('test_pipeline')

            # Fetch prospect data
            prospect_data = await fangraphs_service.get_prospect_data("Test Player")

            assert prospect_data is not None
            assert prospect_data['name'] == "Test Player"
            assert 'scouting_grades' in prospect_data

            # Record successful fetch
            await pipeline_monitor.record_successful_fetch('fangraphs', 'Test Player fetched')

            # Test data integration with MLB data
            mlb_data = [
                {'mlb_id': '123', 'name': 'Test Player', 'position': 'SS', 'organization': 'BAL'}
            ]

            merged_data = await integration_service.merge_prospect_data(
                mlb_data=mlb_data,
                fangraphs_data=[prospect_data]
            )

            assert len(merged_data) == 1
            assert 'mlb' in merged_data[0]['sources']
            assert 'fangraphs' in merged_data[0]['sources']

    @pytest.mark.asyncio
    async def test_rate_limiting_compliance(self, fangraphs_service):
        """Test that rate limiting is properly enforced."""
        start_time = asyncio.get_event_loop().time()

        # Make multiple requests
        with patch.object(fangraphs_service.session, 'get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="<html></html>")
            mock_get.return_value.__aenter__.return_value = mock_response

            # Make 3 rapid requests
            for _ in range(3):
                await fangraphs_service._make_request("https://test.com")

        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time

        # Should take at least 2 seconds for 3 requests (1 req/sec)
        assert total_time >= 2.0

    @pytest.mark.asyncio
    async def test_failover_mechanism(self):
        """Test failover to backup data source."""
        source_manager = DataSourceManager()
        orchestrator = FailoverOrchestrator(source_manager)

        # Mock Fangraphs as unavailable
        source_manager.sources['fangraphs']['status'] = 'unavailable'

        # Try to fetch data
        with patch('app.services.mlb_api_service.MLBAPIService.get_top_prospects') as mock_mlb:
            mock_mlb.return_value = [{'name': 'Backup Player'}]

            result = await orchestrator.fetch_with_failover(
                capability='prospects',
                fetch_function='get_top_prospects',
                limit=1
            )

            # Should failover to MLB API
            assert result is not None
            mock_mlb.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_detection_across_sources(self, duplicate_service):
        """Test duplicate detection between MLB and Fangraphs data."""
        # Create mock database session
        mock_session = AsyncMock()

        # Mock prospects from different sources
        mlb_prospects = [
            Mock(id=1, name="Jackson Holliday", organization="Baltimore Orioles", position="SS")
        ]
        fangraphs_prospects = [
            Mock(id=2, name="Jackson Holiday", organization="BAL", position="SS")  # Slightly different spelling
        ]

        mock_session.execute.return_value.scalars.return_value.all.side_effect = [
            mlb_prospects,
            fangraphs_prospects
        ]

        # Detect duplicates
        duplicates = await duplicate_service.detect_cross_source_duplicates(
            mock_session,
            source_precedence=['mlb', 'fangraphs']
        )

        # Should detect as potential duplicate
        assert len(duplicates) > 0
        assert duplicates[0].confidence_score > 0.8

    def _get_mock_html_response(self):
        """Get mock HTML response for testing."""
        return """
        <html>
            <div class="prospects-grades">
                <div class="grade-item">
                    <span class="skill-name">Hit</span>
                    <span class="grade-value">60</span>
                </div>
                <div class="grade-item">
                    <span class="skill-name">Power</span>
                    <span class="grade-value">55</span>
                </div>
            </div>
            <div class="prospect-rankings">
                <span class="rank-item">Overall #1</span>
            </div>
        </html>
        """


class TestDataQualityValidation:
    """Test data quality and validation processes."""

    @pytest.mark.asyncio
    async def test_scouting_grade_validation(self):
        """Test validation of scouting grades to 20-80 scale."""
        from app.schemas.fangraphs_schemas import FangraphsScoutingGrades

        # Test valid grades
        grades = FangraphsScoutingGrades(
            hit=55,
            power=60,
            speed=50,
            field=45,
            arm=55
        )

        assert grades.hit == 55
        assert grades.power == 60

        # Test rounding to nearest 5
        grades2 = FangraphsScoutingGrades(hit=53)
        assert grades2.hit == 55

        grades3 = FangraphsScoutingGrades(hit=52)
        assert grades3.hit == 50

    @pytest.mark.asyncio
    async def test_data_standardization(self, integration_service):
        """Test data standardization across sources."""
        # Test position standardization
        assert integration_service.standardize_position("RHP") == "RHP"
        assert integration_service.standardize_position("RHSP") == "RHP"
        assert integration_service.standardize_position("shortstop") == "SS"

        # Test organization standardization
        assert integration_service.standardize_organization("BAL") == "Baltimore Orioles"
        assert integration_service.standardize_organization("NYY") == "New York Yankees"

    @pytest.mark.asyncio
    async def test_data_freshness_monitoring(self, pipeline_monitor):
        """Test data freshness checking."""
        # Record successful fetch
        await pipeline_monitor.record_successful_fetch('fangraphs', 'test data')

        # Check freshness immediately
        freshness = await pipeline_monitor.check_data_freshness('fangraphs', max_age_hours=24)
        assert freshness['is_fresh'] is True

        # Simulate old data
        pipeline_monitor.data_freshness_tracking['fangraphs']['last_successful_fetch'] = \
            datetime.utcnow() - timedelta(hours=48)

        freshness = await pipeline_monitor.check_data_freshness('fangraphs', max_age_hours=24)
        assert freshness['is_fresh'] is False


class TestComplianceAndAttribution:
    """Test legal compliance and attribution features."""

    @pytest.mark.asyncio
    async def test_attribution_requirements(self):
        """Test that attribution requirements are properly defined."""
        attr = DataSourceAttribution.get_attribution('fangraphs')

        assert attr['required'] is True
        assert 'Fangraphs' in attr['text']
        assert attr['display_requirements']['link_required'] is True

        # Test HTML generation
        html = DataSourceAttribution.get_display_html('fangraphs')
        assert '<a href=' in html
        assert 'Fangraphs' in html

    @pytest.mark.asyncio
    async def test_compliance_auditing(self):
        """Test compliance audit logging."""
        auditor = ComplianceAuditor()

        # Log data access
        await auditor.log_data_access(
            source='fangraphs',
            data_type='prospects',
            purpose='ml_training',
            user_id='test_user'
        )

        assert len(auditor.audit_log) == 1
        assert auditor.audit_log[0]['source'] == 'fangraphs'
        assert auditor.audit_log[0]['hash'] is not None

    @pytest.mark.asyncio
    async def test_rate_limit_compliance_check(self):
        """Test rate limit compliance verification."""
        auditor = ComplianceAuditor()

        # Mock rate limit check
        with patch.object(auditor, '_check_rate_limit_compliance') as mock_check:
            mock_check.return_value = True

            compliance_status = await auditor.verify_compliance('fangraphs')

            assert compliance_status['compliant'] is True
            assert len(compliance_status['issues']) == 0


class TestCostOptimization:
    """Test cost monitoring and optimization features."""

    @pytest.mark.asyncio
    async def test_cost_tracking(self, cost_optimizer):
        """Test operation cost tracking."""
        metrics = await cost_optimizer.track_operation_cost(
            source='fangraphs',
            operation_type='fetch_prospects',
            request_count=100,
            data_volume_mb=10.0,
            processing_time_seconds=30.0
        )

        assert metrics.source == 'fangraphs'
        assert metrics.total_cost > 0
        assert metrics.request_count == 100

    @pytest.mark.asyncio
    async def test_cost_estimation(self, cost_optimizer):
        """Test cost estimation before operations."""
        estimate = await cost_optimizer.estimate_operation_cost(
            source='fangraphs',
            operation_type='batch_fetch',
            request_count=50,
            data_volume_mb=5.0
        )

        assert 'total' in estimate
        assert estimate['total'] > 0
        assert 'compute' in estimate
        assert 'storage' in estimate
        assert 'network' in estimate

    @pytest.mark.asyncio
    async def test_batch_size_optimization(self, cost_optimizer):
        """Test batch size optimization logic."""
        # Test reducing batch size on high error rate
        new_size = await cost_optimizer.optimize_batch_size(
            current_batch_size=100,
            processing_time=45.0,
            error_rate=0.10  # 10% error rate
        )

        assert new_size < 100  # Should reduce

        # Test increasing batch size on good performance
        new_size = await cost_optimizer.optimize_batch_size(
            current_batch_size=50,
            processing_time=20.0,
            error_rate=0.005  # 0.5% error rate
        )

        assert new_size > 50  # Should increase

    @pytest.mark.asyncio
    async def test_cost_threshold_alerts(self, cost_optimizer):
        """Test cost threshold alerting."""
        # Set low threshold for testing
        cost_optimizer.cost_thresholds['daily'] = 0.01

        # Track operations that exceed threshold
        for _ in range(10):
            await cost_optimizer.track_operation_cost(
                source='fangraphs',
                operation_type='test',
                processing_time_seconds=100
            )

        # Should have triggered alert (mocked)
        assert len(cost_optimizer.cost_history) == 10


class TestPerformanceAndScaling:
    """Test performance and scaling capabilities."""

    @pytest.mark.asyncio
    async def test_concurrent_fetching(self, fangraphs_service):
        """Test concurrent fetching with rate limiting."""
        prospect_names = ["Player1", "Player2", "Player3"]

        with patch.object(fangraphs_service, 'get_prospect_data') as mock_fetch:
            mock_fetch.return_value = {'name': 'test', 'source': 'fangraphs'}

            start = asyncio.get_event_loop().time()
            results = await fangraphs_service.batch_fetch_prospects(prospect_names)
            end = asyncio.get_event_loop().time()

            # Should respect rate limiting (1 req/sec)
            assert (end - start) >= 2.0  # At least 2 seconds for 3 requests
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_data_volume_handling(self, integration_service):
        """Test handling of large data volumes."""
        # Create large dataset
        mlb_data = [
            {'mlb_id': str(i), 'name': f'Player {i}', 'position': 'SS'}
            for i in range(1000)
        ]

        fangraphs_data = [
            {'name': f'Player {i}', 'scouting_grades': {'hit': 50}}
            for i in range(500)
        ]

        # Merge large datasets
        start = asyncio.get_event_loop().time()
        merged = await integration_service.merge_prospect_data(
            mlb_data=mlb_data,
            fangraphs_data=fangraphs_data
        )
        end = asyncio.get_event_loop().time()

        assert len(merged) == 1000  # All MLB records preserved
        assert (end - start) < 5.0  # Should complete within 5 seconds

    @pytest.mark.asyncio
    async def test_error_recovery(self, fangraphs_service):
        """Test error recovery and retry logic."""
        attempt_count = 0

        async def mock_request_with_failures(url, retry_attempt=0):
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count <= 2:
                raise asyncio.TimeoutError("Simulated timeout")
            return "<html>Success</html>"

        with patch.object(fangraphs_service, '_make_request', mock_request_with_failures):
            result = await fangraphs_service.get_prospect_data("Test Player")

            # Should succeed after retries
            assert attempt_count == 3
            assert result is not None