"""
Tests for narrative generation service functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.services.narrative_generation_service import NarrativeGenerationService
from app.models.prospect import Prospect
from app.models.scouting_grades import ScoutingGrades
from app.schemas.ml_predictions import PredictionResponse


class TestNarrativeGenerationService:
    """Test cases for the narrative generation service."""

    @pytest.fixture
    def service(self):
        """Create narrative generation service instance."""
        return NarrativeGenerationService()

    @pytest.fixture
    def sample_prospect(self):
        """Create sample prospect for testing."""
        prospect = Mock(spec=Prospect)
        prospect.id = 1
        prospect.name = "John Smith"
        prospect.age = 21
        prospect.position = "SS"
        prospect.organization = "Yankees"
        prospect.level = "Double-A"
        prospect.eta_year = 2026
        return prospect

    @pytest.fixture
    def sample_prediction(self):
        """Create sample prediction response."""
        return PredictionResponse(
            prospect_id=1,
            success_probability=0.75,
            confidence_level=0.85,
            model_version="v1.0",
            feature_importance={
                'hitting_ability': 0.3,
                'power_potential': 0.2,
                'plate_discipline': -0.1,
                'age_adjusted_performance': 0.15
            },
            prediction_timestamp=datetime.now()
        )

    @pytest.fixture
    def sample_scouting_grades(self):
        """Create sample scouting grades."""
        grades = Mock(spec=ScoutingGrades)
        grades.overall_grade = 55
        grades.hit_grade = 60
        grades.power_grade = 50
        grades.run_grade = 55
        grades.field_grade = 60
        grades.arm_grade = 55
        return grades

    def test_extract_contributing_factors(self, service):
        """Test extraction of contributing factors from SHAP values."""
        shap_values = {
            'hitting_ability': 0.3,
            'power_potential': -0.2,
            'plate_discipline': 0.15,
            'defense': -0.05
        }

        factors = service._extract_contributing_factors(shap_values, limit=3)

        assert len(factors) == 3
        assert factors[0]['name'] == 'hitting ability'
        assert factors[0]['impact'] == 'positive'
        assert factors[1]['name'] == 'power potential'
        assert factors[1]['impact'] == 'negative'
        assert factors[2]['name'] == 'plate discipline'

    def test_convert_feature_name(self, service):
        """Test conversion of technical feature names to readable descriptions."""
        assert service._convert_feature_name('hitting_ability') == 'hitting ability'
        assert service._convert_feature_name('fastball_velocity') == 'fastball velocity'
        assert service._convert_feature_name('unknown_feature') == 'unknown feature'

    def test_assess_risk_level_low(self, service):
        """Test risk assessment for low risk prospect."""
        risk = service._assess_risk_level(
            confidence=0.9,
            age=22,
            level="Triple-A",
            success_probability=0.85
        )
        assert risk == "Low"

    def test_assess_risk_level_high(self, service):
        """Test risk assessment for high risk prospect."""
        risk = service._assess_risk_level(
            confidence=0.5,
            age=19,
            level="Rookie",
            success_probability=0.3
        )
        assert risk == "High"

    def test_assess_risk_level_medium(self, service):
        """Test risk assessment for medium risk prospect."""
        risk = service._assess_risk_level(
            confidence=0.7,
            age=21,
            level="Double-A",
            success_probability=0.6
        )
        assert risk == "Medium"

    def test_estimate_timeline_with_eta(self, service):
        """Test timeline estimation with provided ETA year."""
        service.current_year = 2024
        timeline = service._estimate_timeline(
            eta_year=2026,
            age=21,
            level="Double-A"
        )

        assert timeline['years_away'] == 2
        assert timeline['eta_year'] == 2026
        assert timeline['certainty'] == 'projected'
        assert timeline['description'] == 'within 2 years'

    def test_estimate_timeline_without_eta(self, service):
        """Test timeline estimation without provided ETA year."""
        service.current_year = 2024
        timeline = service._estimate_timeline(
            eta_year=None,
            age=21,
            level="Double-A"
        )

        assert timeline['years_away'] == 2  # Double-A typically 2 years
        assert timeline['eta_year'] == 2026
        assert timeline['certainty'] == 'estimated'

    def test_estimate_years_by_level(self, service):
        """Test years estimation based on current level."""
        assert service._estimate_years_by_level("Triple-A", 22) == 1
        assert service._estimate_years_by_level("Double-A", 21) == 2
        assert service._estimate_years_by_level("High-A", 20) == 3
        assert service._estimate_years_by_level("Low-A", 19) == 5  # +1 for age
        assert service._estimate_years_by_level("Triple-A", 24) == 1  # -1+1 for age

    def test_format_timeline_description(self, service):
        """Test timeline description formatting."""
        assert service._format_timeline_description(0) == "ready now"
        assert service._format_timeline_description(1) == "next year"
        assert service._format_timeline_description(2) == "within 2 years"
        assert service._format_timeline_description(3) == "2-3 years away"
        assert service._format_timeline_description(5) == "5 years away"

    def test_select_template_young_prospect(self, service, sample_prospect):
        """Test template selection for young prospect."""
        sample_prospect.age = 19
        template = service._select_template(sample_prospect, Mock())
        assert template == "young_prospect.j2"

    def test_select_template_advanced_prospect(self, service, sample_prospect):
        """Test template selection for advanced prospect."""
        sample_prospect.age = 23
        sample_prospect.level = "Triple-A"
        template = service._select_template(sample_prospect, Mock())
        assert template == "advanced_prospect.j2"

    def test_select_template_pitcher(self, service, sample_prospect):
        """Test template selection for pitcher."""
        sample_prospect.age = 22
        sample_prospect.position = "RHP"
        sample_prospect.level = "High-A"
        template = service._select_template(sample_prospect, Mock())
        assert template == "base_pitcher.j2"

    def test_select_template_hitter(self, service, sample_prospect):
        """Test template selection for hitter."""
        sample_prospect.age = 22
        sample_prospect.position = "OF"
        sample_prospect.level = "High-A"
        template = service._select_template(sample_prospect, Mock())
        assert template == "base_hitter.j2"

    def test_create_narrative_context(self, service, sample_prospect, sample_prediction, sample_scouting_grades):
        """Test narrative context creation."""
        top_factors = [{'name': 'hitting ability', 'impact': 'positive'}]
        risk_level = "Medium"
        timeline = {'description': 'within 2 years', 'years_away': 2}

        context = service._create_narrative_context(
            prospect=sample_prospect,
            prediction_data=sample_prediction,
            scouting_grades=sample_scouting_grades,
            user_preferences={'league_type': 'dynasty'},
            top_factors=top_factors,
            risk_level=risk_level,
            timeline=timeline
        )

        assert context['name'] == "John Smith"
        assert context['age'] == 21
        assert context['success_probability'] == 0.75
        assert context['risk_level'] == "Medium"
        assert context['timeline'] == 'within 2 years'
        assert context['scouting_grades']['overall'] == 55
        assert context['user_preferences']['league_type'] == 'dynasty'

    def test_optimize_readability(self, service):
        """Test narrative readability optimization."""
        raw_narrative = "  This is a test.   Another sentence  "
        optimized = service._optimize_readability(raw_narrative)
        assert optimized == "This is a test. Another sentence."

        # Test without ending period
        raw_narrative = "This is a test"
        optimized = service._optimize_readability(raw_narrative)
        assert optimized == "This is a test."

    @patch('app.services.narrative_generation_service.template_engine')
    async def test_generate_prospect_outlook_success(
        self,
        mock_template_engine,
        service,
        sample_prospect,
        sample_prediction
    ):
        """Test successful prospect outlook generation."""
        mock_template_engine.render_outlook.return_value = "John Smith is a promising 21-year-old shortstop. His hitting ability stands out as his premier tool. The model projects 75.0% success probability with medium risk, expecting arrival within 2 years."

        result = await service.generate_prospect_outlook(
            prospect=sample_prospect,
            prediction_data=sample_prediction
        )

        assert "John Smith" in result
        assert "21-year-old" in result
        assert "75.0%" in result
        mock_template_engine.render_outlook.assert_called_once()

    async def test_generate_prospect_outlook_missing_data(self, service):
        """Test outlook generation with missing required data."""
        with pytest.raises(ValueError, match="Prospect and prediction data are required"):
            await service.generate_prospect_outlook(
                prospect=None,
                prediction_data=None
            )

    @patch('app.services.narrative_generation_service.template_engine')
    async def test_generate_batch_outlooks_success(
        self,
        mock_template_engine,
        service,
        sample_prospect,
        sample_prediction
    ):
        """Test successful batch outlook generation."""
        mock_template_engine.render_outlook.return_value = "Test outlook"

        prospects = [sample_prospect, sample_prospect]
        predictions = [sample_prediction, sample_prediction]

        results = await service.generate_batch_outlooks(prospects, predictions)

        assert len(results) == 2
        assert all("Test outlook" in result for result in results)

    async def test_generate_batch_outlooks_mismatched_lists(self, service, sample_prospect, sample_prediction):
        """Test batch generation with mismatched list lengths."""
        prospects = [sample_prospect]
        predictions = [sample_prediction, sample_prediction]

        with pytest.raises(ValueError, match="must have same length"):
            await service.generate_batch_outlooks(prospects, predictions)

    @patch('app.services.narrative_generation_service.template_engine')
    async def test_generate_batch_outlooks_with_exception(
        self,
        mock_template_engine,
        service,
        sample_prospect,
        sample_prediction
    ):
        """Test batch generation handling individual exceptions."""
        # First call succeeds, second call fails
        mock_template_engine.render_outlook.side_effect = [
            "Success outlook",
            Exception("Template error")
        ]

        prospects = [sample_prospect, sample_prospect]
        predictions = [sample_prediction, sample_prediction]

        results = await service.generate_batch_outlooks(prospects, predictions)

        assert len(results) == 2
        assert "Success outlook" in results[0]
        assert "Unable to generate outlook" in results[1]


class TestNarrativeServiceIntegration:
    """Integration tests for narrative generation service."""

    @pytest.fixture
    def service(self):
        """Create service with real dependencies."""
        return NarrativeGenerationService()

    def test_full_feature_extraction_flow(self, service):
        """Test complete feature extraction workflow."""
        shap_values = {
            'hitting_ability': 0.4,
            'power_potential': 0.3,
            'plate_discipline': 0.2,
            'defense': 0.1,
            'speed': -0.1,
            'injury_history': -0.2
        }

        factors = service._extract_contributing_factors(shap_values)

        # Should get top 3 by absolute value
        assert len(factors) == 3
        assert factors[0]['name'] == 'hitting ability'
        assert factors[0]['magnitude'] == 0.4
        assert factors[1]['name'] == 'power potential'
        assert factors[1]['magnitude'] == 0.3
        assert factors[2]['name'] == 'injury history'  # -0.2 has higher magnitude than 0.2

    def test_risk_assessment_scenarios(self, service):
        """Test various risk assessment scenarios."""
        # Young star prospect
        risk = service._assess_risk_level(0.95, 20, "Double-A", 0.9)
        assert risk == "Low"

        # Older prospect with questions
        risk = service._assess_risk_level(0.6, 25, "High-A", 0.5)
        assert risk == "High"

        # Typical prospect
        risk = service._assess_risk_level(0.75, 22, "Double-A", 0.65)
        assert risk == "Medium"

        # High-level prospect with age concerns
        risk = service._assess_risk_level(0.8, 24, "Triple-A", 0.7)
        assert risk == "Low"  # High level compensates for age