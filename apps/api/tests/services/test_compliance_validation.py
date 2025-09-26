"""Automated compliance validation tests."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import aiohttp

from app.services.compliance_attribution import (
    ComplianceAuditor,
    DataSourceAttribution,
    DataRetentionPolicy,
    TermsOfServiceManager,
    CostTracker
)
from app.services.fangraphs_service import FangraphsService


class TestComplianceValidation:
    """Test suite for automated compliance validation."""

    @pytest.fixture
    def compliance_auditor(self):
        """Create compliance auditor instance."""
        return ComplianceAuditor()

    @pytest.fixture
    def fangraphs_service(self):
        """Create FanGraphs service instance."""
        return FangraphsService()

    @pytest.mark.asyncio
    async def test_rate_limiting_compliance(self, fangraphs_service):
        """Test that FanGraphs service respects rate limiting."""
        # Mock session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html></html>")
        mock_response.request_info = Mock()
        mock_response.history = Mock()

        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        # Test rate limiting by measuring request intervals
        start_time = datetime.utcnow()
        request_times = []

        with patch.object(fangraphs_service, 'session', mock_session):
            for i in range(3):
                await fangraphs_service._make_request("https://test.com")
                request_times.append(datetime.utcnow())

        # Verify rate limiting (should be at least 1 second between requests)
        for i in range(1, len(request_times)):
            time_diff = (request_times[i] - request_times[i-1]).total_seconds()
            assert time_diff >= 0.9, f"Rate limit violated: {time_diff}s between requests"

    @pytest.mark.asyncio
    async def test_attribution_requirements(self):
        """Test attribution requirements are properly defined."""
        # Test FanGraphs attribution
        fangraphs_attr = DataSourceAttribution.get_attribution('fangraphs')
        assert fangraphs_attr['required'] is True
        assert 'Data provided by Fangraphs.com' in fangraphs_attr['text']
        assert fangraphs_attr['url'] == 'https://www.fangraphs.com'

        # Test MLB API attribution
        mlb_attr = DataSourceAttribution.get_attribution('mlb_api')
        assert mlb_attr['required'] is True
        assert '© MLB Advanced Media' in mlb_attr['text']

        # Test attribution HTML generation
        fangraphs_html = DataSourceAttribution.get_display_html('fangraphs')
        assert '<a href="https://www.fangraphs.com"' in fangraphs_html
        assert 'Data provided by Fangraphs.com' in fangraphs_html

    @pytest.mark.asyncio
    async def test_data_retention_policies(self):
        """Test data retention policy compliance."""
        # Test retention periods
        prospect_retention = await DataRetentionPolicy.apply_retention_policy('prospect_data', 'raw_data')
        assert prospect_retention == 90

        user_profile_retention = await DataRetentionPolicy.apply_retention_policy('user_data', 'profile')
        assert user_profile_retention == -1  # Indefinite

        # Test cleanup simulation
        cleanup_stats = await DataRetentionPolicy.cleanup_expired_data()
        assert isinstance(cleanup_stats, dict)
        assert all(isinstance(count, int) for count in cleanup_stats.values())

    @pytest.mark.asyncio
    async def test_terms_of_service_compliance(self):
        """Test terms of service compliance checking."""
        # Test ToS acceptance verification
        fangraphs_tos = TermsOfServiceManager.verify_tos_acceptance('fangraphs')
        assert fangraphs_tos is True

        mlb_tos = TermsOfServiceManager.verify_tos_acceptance('mlb_api')
        assert mlb_tos is True

        # Test unknown source
        unknown_tos = TermsOfServiceManager.verify_tos_acceptance('unknown_source')
        assert unknown_tos is False

        # Test ToS requirements
        fangraphs_requirements = TermsOfServiceManager.get_tos_requirements('fangraphs')
        assert 'Rate limit 1 request/second' in fangraphs_requirements['key_terms']
        assert 'Attribution required' in fangraphs_requirements['key_terms']

    @pytest.mark.asyncio
    async def test_audit_logging(self, compliance_auditor):
        """Test audit logging functionality."""
        # Test audit log creation
        await compliance_auditor.log_data_access(
            source='fangraphs',
            data_type='prospect_data',
            purpose='data_collection',
            user_id='test_user',
            ip_address='127.0.0.1'
        )

        assert len(compliance_auditor.audit_log) == 1
        audit_entry = compliance_auditor.audit_log[0]

        assert audit_entry['source'] == 'fangraphs'
        assert audit_entry['data_type'] == 'prospect_data'
        assert audit_entry['purpose'] == 'data_collection'
        assert audit_entry['user_id'] == 'test_user'
        assert audit_entry['ip_address'] == '127.0.0.1'
        assert 'hash' in audit_entry
        assert 'timestamp' in audit_entry

    @pytest.mark.asyncio
    async def test_compliance_verification(self, compliance_auditor):
        """Test comprehensive compliance verification."""
        # Mock monitoring service
        mock_monitor = AsyncMock()
        compliance_auditor.monitor = mock_monitor

        # Test FanGraphs compliance
        with patch.object(compliance_auditor, '_check_rate_limit_compliance', return_value=True), \
             patch.object(compliance_auditor, '_check_attribution_compliance', return_value=True), \
             patch.object(compliance_auditor, '_check_retention_compliance', return_value=True):

            compliance_status = await compliance_auditor.verify_compliance('fangraphs')

            assert compliance_status['source'] == 'fangraphs'
            assert compliance_status['compliant'] is True
            assert len(compliance_status['issues']) == 0

        # Test non-compliant scenario
        with patch.object(compliance_auditor, '_check_rate_limit_compliance', return_value=False), \
             patch.object(compliance_auditor, '_check_attribution_compliance', return_value=True), \
             patch.object(compliance_auditor, '_check_retention_compliance', return_value=True):

            compliance_status = await compliance_auditor.verify_compliance('fangraphs')

            assert compliance_status['compliant'] is False
            assert 'Rate limit exceeded' in compliance_status['issues']

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        """Test cost tracking functionality."""
        cost_tracker = CostTracker()

        # Test request tracking
        await cost_tracker.track_request('fangraphs')
        await cost_tracker.track_request('fangraphs')
        await cost_tracker.track_request('mlb_api')

        assert cost_tracker.cost_data['fangraphs']['current_usage'] == 2
        assert cost_tracker.cost_data['mlb_api']['current_usage'] == 1

        # Test cost calculation
        fangraphs_cost = await cost_tracker.get_monthly_cost('fangraphs')
        assert fangraphs_cost == 0.0  # Free service

        # Test cost report
        cost_report = await cost_tracker.get_cost_report()
        assert 'sources' in cost_report
        assert 'total_cost' in cost_report
        assert cost_report['sources']['fangraphs']['requests'] == 2
        assert cost_report['sources']['mlb_api']['requests'] == 1

    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, compliance_auditor):
        """Test compliance report generation."""
        # Mock compliance checks
        with patch.object(compliance_auditor, 'verify_compliance') as mock_verify:
            mock_verify.return_value = {
                'source': 'fangraphs',
                'compliant': True,
                'issues': [],
                'checked_at': datetime.utcnow().isoformat()
            }

            report = await compliance_auditor.generate_compliance_report()

            assert 'generated_at' in report
            assert 'sources' in report
            assert 'data_retention' in report
            assert 'audit_summary' in report
            assert 'recommendations' in report

            # Verify sources were checked
            assert 'fangraphs' in report['sources']
            assert 'mlb_api' in report['sources']

            # Verify data retention section
            assert 'prospect_data' in report['data_retention']
            assert 'user_data' in report['data_retention']

    @pytest.mark.asyncio
    async def test_circuit_breaker_compliance(self, fangraphs_service):
        """Test circuit breaker integration for compliance."""
        # Test that circuit breaker is properly configured
        assert fangraphs_service.circuit_breaker is not None
        assert fangraphs_service.circuit_breaker.name == "fangraphs_service"
        assert fangraphs_service.circuit_breaker.failure_threshold == 5
        assert fangraphs_service.circuit_breaker.recovery_timeout == 300

        # Test service health reporting
        health = fangraphs_service.get_service_health()
        assert 'circuit_breaker' in health
        assert 'service' in health
        assert health['service'] == 'fangraphs'

    def test_attribution_display_requirements(self):
        """Test attribution display requirements are met."""
        # Test all required attributions
        sources = ['fangraphs', 'mlb_api']
        attributions = DataSourceAttribution.get_all_required_attributions(sources)

        assert len(attributions) == 2

        for attr in attributions:
            assert attr['required'] is True
            assert 'text' in attr
            assert 'display_requirements' in attr

            # Check display requirements
            display_req = attr['display_requirements']
            assert 'position' in display_req
            assert 'font_size' in display_req
            assert 'visibility' in display_req

    @pytest.mark.asyncio
    async def test_monitoring_integration(self, compliance_auditor):
        """Test integration with monitoring system."""
        # Mock pipeline monitor
        mock_monitor = AsyncMock()
        compliance_auditor.monitor = mock_monitor

        # Test violation logging
        await TermsOfServiceManager.log_tos_violation(
            'fangraphs',
            'Rate limit exceeded during testing'
        )

        # Verify alert was sent
        mock_monitor.send_alert.assert_called_once()
        call_args = mock_monitor.send_alert.call_args
        assert call_args[1]['level'] == 'critical'
        assert 'Terms of Service violation' in call_args[1]['message']

    @pytest.mark.asyncio
    async def test_compliance_automation_schedule(self):
        """Test that compliance checks can be automated."""
        auditor = ComplianceAuditor()

        # Simulate scheduled compliance check
        async def run_compliance_check():
            report = await auditor.generate_compliance_report()
            return report

        # Test that the check runs without errors
        report = await run_compliance_check()
        assert report is not None
        assert 'generated_at' in report

        # Verify timestamp is recent
        generated_time = datetime.fromisoformat(report['generated_at'])
        time_diff = datetime.utcnow() - generated_time
        assert time_diff.total_seconds() < 10  # Generated within last 10 seconds


class TestComplianceEdgeCases:
    """Test edge cases and error conditions in compliance validation."""

    @pytest.mark.asyncio
    async def test_network_failure_compliance(self):
        """Test compliance during network failures."""
        service = FangraphsService()

        # Mock network failure
        mock_session = AsyncMock()
        mock_session.get.side_effect = aiohttp.ClientError("Network failure")

        with patch.object(service, 'session', mock_session):
            result = await service._make_request("https://test.com")
            assert result is None  # Should handle gracefully

    @pytest.mark.asyncio
    async def test_rate_limit_response_compliance(self):
        """Test compliance when receiving rate limit responses."""
        service = FangraphsService()

        # Mock rate limit response
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.request_info = Mock()
        mock_response.history = Mock()

        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with patch.object(service, 'session', mock_session):
            with pytest.raises(Exception):  # Should raise exception for rate limiting
                await service._execute_request("https://test.com")

    @pytest.mark.asyncio
    async def test_compliance_with_invalid_data(self, compliance_auditor):
        """Test compliance validation with invalid or missing data."""
        # Test with missing source
        compliance_status = await compliance_auditor.verify_compliance('invalid_source')
        assert 'source' in compliance_status
        assert compliance_status['source'] == 'invalid_source'

        # Test attribution for unknown source
        unknown_attr = DataSourceAttribution.get_attribution('unknown_source')
        assert unknown_attr == {}

        # Test HTML generation for unknown source
        unknown_html = DataSourceAttribution.get_display_html('unknown_source')
        assert unknown_html == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])