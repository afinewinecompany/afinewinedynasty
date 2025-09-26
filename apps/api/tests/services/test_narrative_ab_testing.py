"""
Tests for narrative A/B testing service functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.narrative_ab_testing import (
    NarrativeABTestManager,
    NarrativeTestConfig,
    NarrativeTestType,
    NarrativeTestResult
)
from app.ml.ab_testing import SplitStrategy


class TestNarrativeABTestManager:
    """Test cases for the narrative A/B test manager."""

    @pytest.fixture
    def manager(self):
        """Create narrative A/B test manager instance."""
        return NarrativeABTestManager()

    @pytest.fixture
    def test_config(self):
        """Sample test configuration."""
        return NarrativeTestConfig(
            test_name="template_comparison_test",
            description="Compare base vs power hitter templates",
            test_type=NarrativeTestType.TEMPLATE_COMPARISON,
            control_template="base_hitter.j2",
            variant_template="power_hitter.j2",
            control_config={},
            variant_config={"emphasis": "power"},
            traffic_split_ratio=0.5,
            split_strategy=SplitStrategy.HASH_BASED,
            minimum_sample_size=100,
            success_metrics=["quality_score", "readability_score"],
            quality_thresholds={"minimum_quality": 60.0}
        )

    @pytest.fixture
    def prospect_data(self):
        """Sample prospect data."""
        return {
            'id': 123,
            'name': 'John Smith',
            'age': 21,
            'position': 'OF',
            'organization': 'Yankees',
            'level': 'Double-A'
        }

    @pytest.fixture
    def prediction_data(self):
        """Sample prediction data."""
        return {
            'success_probability': 0.75,
            'confidence_level': 0.85,
            'model_version': 'v1.0',
            'feature_importance': {
                'power_potential': 0.3,
                'hitting_ability': 0.2
            }
        }

    def test_create_narrative_test(self, manager, test_config):
        """Test creating a narrative A/B test."""
        with patch.object(manager, '_validate_test_config'):
            test_id = manager.create_narrative_test(test_config)

            assert test_id == test_config.test_name
            assert test_config.test_name in manager.active_tests
            assert test_config.test_name in manager.test_data
            assert len(manager.test_data[test_config.test_name]['control']) == 0
            assert len(manager.test_data[test_config.test_name]['variant']) == 0

    def test_validate_test_config_success(self, manager):
        """Test successful test configuration validation."""
        config = NarrativeTestConfig(
            test_name="valid_test",
            description="Valid test config",
            test_type=NarrativeTestType.TEMPLATE_COMPARISON,
            control_template="base_hitter.j2",
            variant_template="power_hitter.j2",
            control_config={},
            variant_config={},
            traffic_split_ratio=0.5,
            split_strategy=SplitStrategy.RANDOM,
            minimum_sample_size=50,
            success_metrics=["quality_score"],
            quality_thresholds={"minimum_quality": 60.0}
        )

        with patch.object(manager, '_template_exists', return_value=True):
            # Should not raise exception
            manager._validate_test_config(config)

    def test_validate_test_config_invalid_template(self, manager):
        """Test validation failure for invalid template."""
        config = NarrativeTestConfig(
            test_name="invalid_test",
            description="Invalid test config",
            test_type=NarrativeTestType.TEMPLATE_COMPARISON,
            control_template="nonexistent.j2",
            variant_template="power_hitter.j2",
            control_config={},
            variant_config={},
            traffic_split_ratio=0.5,
            split_strategy=SplitStrategy.RANDOM,
            minimum_sample_size=50,
            success_metrics=["quality_score"],
            quality_thresholds={"minimum_quality": 60.0}
        )

        with patch.object(manager, '_template_exists', side_effect=lambda x: x != "nonexistent.j2"):
            with pytest.raises(ValueError, match="Control template.*not found"):
                manager._validate_test_config(config)

    @pytest.mark.asyncio
    async def test_assign_and_generate(self, manager, test_config, prospect_data, prediction_data):
        """Test variant assignment and narrative generation."""
        # Setup test
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        # Mock narrative generation
        mock_narrative = "Generated narrative for testing"
        mock_quality_metrics = Mock()
        mock_quality_metrics.quality_score = 75.0
        mock_quality_metrics.readability_score = 80.0

        with patch('app.services.narrative_ab_testing.narrative_service') as mock_service, \
             patch('app.services.narrative_ab_testing.narrative_quality_service') as mock_quality:

            mock_service.generate_prospect_outlook.return_value = mock_narrative
            mock_quality.assess_narrative_quality.return_value = mock_quality_metrics

            result = await manager.assign_and_generate(
                test_name=test_config.test_name,
                user_id="user_123",
                prospect_data=prospect_data,
                prediction_data=prediction_data
            )

            assert result['test_name'] == test_config.test_name
            assert result['user_id'] == "user_123"
            assert result['variant'] in ['control', 'variant']
            assert result['narrative'] == mock_narrative
            assert result['quality_score'] == 75.0

            # Check that data was recorded
            variant = result['variant']
            test_data = manager.test_data[test_config.test_name][variant]
            assert len(test_data) == 1
            assert test_data[0]['user_id'] == "user_123"

    def test_record_engagement_metrics(self, manager, test_config):
        """Test recording engagement metrics."""
        # Setup test with existing interaction
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        # Add existing interaction
        interaction = {
            'user_id': 'user_123',
            'timestamp': datetime.now().isoformat()
        }
        manager.test_data[test_config.test_name]['control'].append(interaction)

        # Record engagement
        engagement_data = {
            'click_through_rate': 0.15,
            'time_spent': 45.2,
            'user_satisfaction': 4.2
        }

        manager.record_engagement_metrics(
            test_name=test_config.test_name,
            user_id='user_123',
            variant='control',
            engagement_data=engagement_data
        )

        # Check that engagement was recorded
        updated_interaction = manager.test_data[test_config.test_name]['control'][0]
        assert updated_interaction['click_through_rate'] == 0.15
        assert updated_interaction['time_spent'] == 45.2
        assert updated_interaction['user_satisfaction'] == 4.2
        assert 'engagement_recorded_at' in updated_interaction

    def test_calculate_narrative_metrics(self, manager):
        """Test calculation of narrative metrics."""
        test_data = [
            {
                'quality_metrics': {'quality_score': 80.0, 'readability_score': 75.0},
                'user_satisfaction': 4.5
            },
            {
                'quality_metrics': {'quality_score': 70.0, 'readability_score': 85.0},
                'user_satisfaction': 4.0
            }
        ]

        metrics = manager._calculate_narrative_metrics(
            test_data, ['quality_score', 'readability_score', 'user_satisfaction']
        )

        assert metrics['quality_score'] == 75.0  # (80 + 70) / 2
        assert metrics['readability_score'] == 80.0  # (75 + 85) / 2
        assert metrics['user_satisfaction'] == 4.25  # (4.5 + 4.0) / 2

    def test_analyze_quality_differences(self, manager):
        """Test quality difference analysis."""
        control_data = [
            {'quality_metrics': {'quality_score': 70.0, 'readability_score': 75.0}},
            {'quality_metrics': {'quality_score': 80.0, 'readability_score': 80.0}}
        ]

        variant_data = [
            {'quality_metrics': {'quality_score': 85.0, 'readability_score': 85.0}},
            {'quality_metrics': {'quality_score': 90.0, 'readability_score': 90.0}}
        ]

        analysis = manager._analyze_quality_differences(control_data, variant_data)

        assert analysis['control_avg_quality'] == 75.0
        assert analysis['variant_avg_quality'] == 87.5
        assert analysis['quality_improvement'] == 12.5
        assert analysis['quality_improvement_pct'] == pytest.approx(16.67, rel=1e-2)

    def test_calculate_significance(self, manager):
        """Test statistical significance calculation."""
        control_metrics = {'quality_score': 70.0, 'readability_score': 75.0}
        variant_metrics = {'quality_score': 80.0, 'readability_score': 85.0}

        # Test with sufficient sample size and significant improvement
        is_significant, confidence = manager._calculate_significance(
            control_metrics, variant_metrics, 150, 150
        )

        assert is_significant is True
        assert confidence > 0.8

        # Test with insufficient sample size
        is_significant, confidence = manager._calculate_significance(
            control_metrics, variant_metrics, 50, 50
        )

        assert is_significant is False
        assert confidence == 0.0

    def test_generate_narrative_recommendation(self, manager, test_config):
        """Test narrative recommendation generation."""
        control_metrics = {'quality_score': 70.0}
        variant_metrics = {'quality_score': 85.0}
        quality_analysis = {
            'variant_avg_quality': 85.0,
            'quality_improvement': 15.0
        }
        engagement_analysis = {
            'click_through_rate_improvement': 0.05,
            'time_spent_improvement': 10.0,
            'user_satisfaction_improvement': 0.5
        }

        # Setup test data for sample size check
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        # Add sufficient sample data
        for i in range(150):
            manager.test_data[test_config.test_name]['control'].append({'user_id': f'user_{i}'})
            manager.test_data[test_config.test_name]['variant'].append({'user_id': f'user_{i+150}'})

        recommendation, winner = manager._generate_narrative_recommendation(
            control_metrics, variant_metrics, quality_analysis,
            engagement_analysis, True, test_config
        )

        assert "Promote variant" in recommendation
        assert winner == "variant"

    def test_analyze_narrative_test(self, manager, test_config):
        """Test comprehensive narrative test analysis."""
        # Setup test with data
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        # Add test data
        for i in range(50):
            manager.test_data[test_config.test_name]['control'].append({
                'user_id': f'control_user_{i}',
                'quality_metrics': {'quality_score': 70.0 + i, 'readability_score': 75.0}
            })
            manager.test_data[test_config.test_name]['variant'].append({
                'user_id': f'variant_user_{i}',
                'quality_metrics': {'quality_score': 80.0 + i, 'readability_score': 85.0}
            })

        result = manager.analyze_narrative_test(test_config.test_name)

        assert isinstance(result, NarrativeTestResult)
        assert result.test_name == test_config.test_name
        assert result.total_requests == 100
        assert result.control_requests == 50
        assert result.variant_requests == 50
        assert 'quality_score' in result.control_metrics
        assert 'quality_score' in result.variant_metrics

    def test_get_test_status(self, manager, test_config):
        """Test getting test status."""
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        status = manager.get_test_status(test_config.test_name)

        assert status['test_name'] == test_config.test_name
        assert status['test_type'] == test_config.test_type.value
        assert status['status'] == 'running'
        assert status['control_template'] == test_config.control_template
        assert status['variant_template'] == test_config.variant_template
        assert status['total_samples'] == 0

    def test_get_test_status_not_found(self, manager):
        """Test getting status for non-existent test."""
        status = manager.get_test_status("nonexistent_test")
        assert 'error' in status

    def test_stop_narrative_test(self, manager, test_config):
        """Test stopping a narrative test."""
        # Setup test
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        # Add some test data
        manager.test_data[test_config.test_name]['control'].append({
            'user_id': 'test_user',
            'quality_metrics': {'quality_score': 75.0}
        })

        result = manager.stop_narrative_test(test_config.test_name)

        assert isinstance(result, NarrativeTestResult)
        assert result.end_time is not None
        assert test_config.test_name not in manager.active_tests

    def test_export_narrative_test_results(self, manager, test_config, tmp_path):
        """Test exporting test results."""
        # Setup test with results
        with patch.object(manager, '_validate_test_config'):
            manager.create_narrative_test(test_config)

        # Create test result
        result = NarrativeTestResult(
            test_name=test_config.test_name,
            test_type=test_config.test_type.value,
            start_time=datetime.now().isoformat(),
            end_time=None,
            total_requests=10,
            control_requests=5,
            variant_requests=5,
            control_metrics={'quality_score': 70.0},
            variant_metrics={'quality_score': 80.0},
            quality_analysis={},
            engagement_analysis={},
            statistical_significance=True,
            confidence_level=0.95,
            recommendation="Promote variant",
            winner="variant"
        )

        manager.test_results[test_config.test_name] = result

        # Export results
        export_path = tmp_path / "test_results.json"
        manager.export_narrative_test_results(test_config.test_name, str(export_path))

        assert export_path.exists()

        # Read and verify exported data
        import json
        with open(export_path) as f:
            exported_data = json.load(f)

        assert 'result' in exported_data
        assert 'control_data' in exported_data
        assert 'variant_data' in exported_data
        assert exported_data['result']['test_name'] == test_config.test_name


class TestNarrativeTestIntegration:
    """Integration tests for narrative A/B testing."""

    @pytest.fixture
    def manager(self):
        """Manager instance for integration tests."""
        return NarrativeABTestManager()

    def test_full_template_comparison_workflow(self, manager):
        """Test complete template comparison workflow."""
        # Create test config
        config = NarrativeTestConfig(
            test_name="integration_test",
            description="Full workflow test",
            test_type=NarrativeTestType.TEMPLATE_COMPARISON,
            control_template="base_hitter.j2",
            variant_template="power_hitter.j2",
            control_config={},
            variant_config={"focus": "power"},
            traffic_split_ratio=0.5,
            split_strategy=SplitStrategy.HASH_BASED,
            minimum_sample_size=10,
            success_metrics=["quality_score", "readability_score"],
            quality_thresholds={"minimum_quality": 60.0}
        )

        # Create test
        with patch.object(manager, '_validate_test_config'):
            test_id = manager.create_test(config)

        # Simulate test interactions
        for i in range(20):
            variant = 'control' if i % 2 == 0 else 'variant'
            quality_score = 70.0 + (10.0 if variant == 'variant' else 0) + (i % 5)

            interaction = {
                'user_id': f'user_{i}',
                'timestamp': datetime.now().isoformat(),
                'quality_metrics': {
                    'quality_score': quality_score,
                    'readability_score': quality_score + 5
                }
            }

            manager.test_data[test_id][variant].append(interaction)

        # Analyze results
        result = manager.analyze_narrative_test(test_id)

        # Verify analysis
        assert result.total_requests == 20
        assert result.control_requests == 10
        assert result.variant_requests == 10
        assert result.variant_metrics['quality_score'] > result.control_metrics['quality_score']

        # Get status
        status = manager.get_test_status(test_id)
        assert status['sample_size_progress'] >= 1.0  # Above minimum

        # Stop test
        final_result = manager.stop_narrative_test(test_id)
        assert final_result.end_time is not None

    def test_personalization_comparison_workflow(self, manager):
        """Test personalization comparison workflow."""
        config = NarrativeTestConfig(
            test_name="personalization_test",
            description="Test personalization impact",
            test_type=NarrativeTestType.PERSONALIZATION_COMPARISON,
            control_template="base_hitter.j2",
            variant_template="base_hitter.j2",  # Same template
            control_config={"personalization": False},
            variant_config={"personalization": True, "dynasty_focus": True},
            traffic_split_ratio=0.5,
            split_strategy=SplitStrategy.RANDOM,
            minimum_sample_size=15,
            success_metrics=["quality_score", "user_satisfaction"],
            quality_thresholds={"minimum_quality": 65.0}
        )

        with patch.object(manager, '_validate_test_config'):
            test_id = manager.create_narrative_test(config)

        # Verify test was created for personalization
        assert config.test_type == NarrativeTestType.PERSONALIZATION_COMPARISON
        assert manager.active_tests[test_id].control_template == manager.active_tests[test_id].variant_template

        status = manager.get_test_status(test_id)
        assert status['test_type'] == 'personalization_comparison'