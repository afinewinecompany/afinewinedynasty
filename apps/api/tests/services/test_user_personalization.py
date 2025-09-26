"""
Tests for user personalization service functionality.
"""

import pytest
from unittest.mock import Mock

from app.services.user_personalization_service import (
    UserPersonalizationService,
    LeagueFormat,
    ScoringSystem
)


class TestUserPersonalizationService:
    """Test cases for the user personalization service."""

    @pytest.fixture
    def service(self):
        """Create user personalization service instance."""
        return UserPersonalizationService()

    @pytest.fixture
    def base_context(self):
        """Sample base context for testing."""
        return {
            'name': 'Test Player',
            'age': 21,
            'position': 'SS',
            'organization': 'Yankees',
            'level': 'Double-A',
            'success_probability': 0.75,
            'risk_level': 'Medium',
            'timeline_data': {
                'years_away': 2,
                'description': 'within 2 years'
            }
        }

    @pytest.fixture
    def dynasty_preferences(self):
        """Dynasty league user preferences."""
        return {
            'league_format': LeagueFormat.DYNASTY,
            'scoring_system': ScoringSystem.CATEGORIES,
            'timeline_preference': 'long_term'
        }

    @pytest.fixture
    def redraft_preferences(self):
        """Redraft league user preferences."""
        return {
            'league_format': LeagueFormat.REDRAFT,
            'scoring_system': ScoringSystem.POINTS,
            'timeline_preference': 'immediate'
        }

    @pytest.fixture
    def team_needs(self):
        """Sample team needs."""
        return {
            'positions': {
                'SS': 'critical',
                'OF': 'medium',
                'C': 'low'
            },
            'organizations': ['Yankees', 'Dodgers']
        }

    def test_personalize_outlook_context_dynasty(
        self,
        service,
        base_context,
        dynasty_preferences,
        team_needs
    ):
        """Test outlook personalization for dynasty league."""
        result = service.personalize_outlook_context(
            base_context,
            dynasty_preferences,
            team_needs
        )

        assert result['personalization_applied'] is True
        assert result['league_insights']['format'] == LeagueFormat.DYNASTY
        assert result['league_insights']['risk_tolerance'] == 'high'
        assert result['league_insights']['value_focus'] == 'upside'
        assert 'dynasty_insights' in result

    def test_personalize_outlook_context_redraft(
        self,
        service,
        base_context,
        redraft_preferences
    ):
        """Test outlook personalization for redraft league."""
        result = service.personalize_outlook_context(
            base_context,
            redraft_preferences
        )

        assert result['league_insights']['format'] == LeagueFormat.REDRAFT
        assert result['league_insights']['risk_tolerance'] == 'low'
        assert result['league_insights']['value_focus'] == 'floor'
        assert result['league_insights']['timeline_weight'] == 1.5

    def test_generate_dynasty_recommendation_young_star(self, service):
        """Test dynasty recommendation for young star prospect."""
        context = {'age': 20, 'success_probability': 0.8, 'risk_level': 'Low'}
        recommendation = service._get_dynasty_recommendation(context)
        assert "Excellent dynasty target" in recommendation

    def test_generate_dynasty_recommendation_old_prospect(self, service):
        """Test dynasty recommendation for older prospect."""
        context = {'age': 25, 'success_probability': 0.6, 'risk_level': 'Medium'}
        recommendation = service._get_dynasty_recommendation(context)
        assert "Limited dynasty appeal" in recommendation

    def test_generate_redraft_recommendation_mlb_ready(self, service):
        """Test redraft recommendation for MLB ready prospect."""
        context = {
            'timeline_data': {'years_away': 0},
            'success_probability': 0.8,
            'risk_level': 'Low'
        }
        recommendation = service._get_redraft_recommendation(context)
        assert "Immediate redraft relevance" in recommendation

    def test_generate_redraft_recommendation_distant(self, service):
        """Test redraft recommendation for distant prospect."""
        context = {
            'timeline_data': {'years_away': 3},
            'success_probability': 0.6,
            'risk_level': 'Medium'
        }
        recommendation = service._get_redraft_recommendation(context)
        assert "Limited redraft appeal" in recommendation

    def test_analyze_team_fit_critical_need(self, service, base_context, team_needs):
        """Test team fit analysis for critical positional need."""
        fit_analysis = service._analyze_team_fit(base_context, team_needs)

        assert fit_analysis['position_need'] == 'critical'
        assert fit_analysis['priority_level'] == 'high'
        assert fit_analysis['roster_impact'] == 'starter'
        assert "High priority target" in fit_analysis['recommendation']

    def test_analyze_team_fit_no_need(self, service, base_context):
        """Test team fit analysis with no specific needs."""
        context = base_context.copy()
        context['position'] = 'C'  # Not in team needs
        context['success_probability'] = 0.9  # High success rate

        fit_analysis = service._analyze_team_fit(context, {'positions': {'SS': 'critical'}})

        assert fit_analysis['position_need'] == 'unknown'
        assert "Consider regardless of need" in fit_analysis['recommendation']

    def test_assess_timeline_relevance_dynasty(self, service, base_context, dynasty_preferences):
        """Test timeline relevance for dynasty league."""
        relevance = service._assess_timeline_relevance(base_context, dynasty_preferences)

        assert relevance['years_away'] == 2
        assert relevance['relevance_score'] == 0.8  # Good for dynasty
        assert relevance['timeline_fit'] == 'good'

    def test_assess_timeline_relevance_redraft(self, service, base_context, redraft_preferences):
        """Test timeline relevance for redraft league."""
        relevance = service._assess_timeline_relevance(base_context, redraft_preferences)

        assert relevance['years_away'] == 2
        assert relevance['relevance_score'] == 0.1  # Poor for redraft
        assert relevance['timeline_fit'] == 'poor'

    def test_calculate_positional_value_catcher(self, service):
        """Test positional value calculation for catcher."""
        context = {'position': 'C'}
        preferences = {'scoring_system': ScoringSystem.CATEGORIES}

        value = service._calculate_positional_value(context, preferences)

        assert value['position'] == 'C'
        assert value['scarcity_rank'] == 1  # Most scarce
        assert value['scarcity_level'] == 'very_high'
        assert value['positional_premium'] == 1.3

    def test_calculate_positional_value_first_base(self, service):
        """Test positional value calculation for first base."""
        context = {'position': '1B'}
        preferences = {'scoring_system': ScoringSystem.POINTS}

        value = service._calculate_positional_value(context, preferences)

        assert value['position'] == '1B'
        assert value['scarcity_level'] == 'medium'
        # Should get boost in points leagues
        assert value['positional_premium'] > 0.95

    def test_generate_dynasty_insights_elite_prospect(self, service):
        """Test dynasty insights for elite prospect."""
        context = {
            'age': 19,
            'success_probability': 0.85,
            'timeline_data': {'years_away': 2}
        }

        insights = service._generate_dynasty_insights(context)

        assert insights['dynasty_grade'] in ['A+', 'A']
        assert insights['development_runway'] == 'extensive'
        assert insights['long_term_value'] == 'elite'

    def test_generate_dynasty_insights_older_prospect(self, service):
        """Test dynasty insights for older prospect."""
        context = {
            'age': 25,
            'success_probability': 0.5,
            'timeline_data': {'years_away': 1}
        }

        insights = service._generate_dynasty_insights(context)

        assert insights['dynasty_grade'] in ['C', 'C+', 'D']
        assert insights['development_runway'] == 'limited'
        assert insights['long_term_value'] in ['moderate', 'speculative']

    def test_calculate_dynasty_grade_scoring(self, service):
        """Test dynasty grade calculation scoring."""
        # Perfect prospect
        grade = service._calculate_dynasty_grade(19, 1.0, 1)
        assert grade == 'A+'

        # Good prospect
        grade = service._calculate_dynasty_grade(21, 0.7, 2)
        assert grade in ['A', 'B+']

        # Average prospect
        grade = service._calculate_dynasty_grade(23, 0.5, 3)
        assert grade in ['B', 'C+', 'C']

        # Poor prospect
        grade = service._calculate_dynasty_grade(26, 0.3, 5)
        assert grade in ['C', 'D']

    def test_assess_development_runway(self, service):
        """Test development runway assessment."""
        assert service._assess_development_runway(19) == 'extensive'
        assert service._assess_development_runway(21) == 'substantial'
        assert service._assess_development_runway(23) == 'moderate'
        assert service._assess_development_runway(26) == 'limited'

    def test_suggest_acquisition_timing(self, service):
        """Test acquisition timing suggestions."""
        # MLB ready, low risk
        context = {
            'timeline_data': {'years_away': 0},
            'risk_level': 'Low'
        }
        timing = service._suggest_acquisition_timing(context)
        assert timing == 'acquire_now'

        # Close timeline
        context = {
            'timeline_data': {'years_away': 2},
            'risk_level': 'Medium'
        }
        timing = service._suggest_acquisition_timing(context)
        assert timing == 'monitor_closely'

        # High risk prospect
        context = {
            'timeline_data': {'years_away': 3},
            'risk_level': 'High'
        }
        timing = service._suggest_acquisition_timing(context)
        assert timing == 'wait_for_discount'

    def test_personalization_without_preferences(self, service, base_context):
        """Test personalization with minimal user data."""
        result = service.personalize_outlook_context(base_context)

        assert result['personalization_applied'] is True
        assert 'league_insights' in result
        assert 'team_fit' in result
        assert 'timeline_relevance' in result
        assert 'positional_value' in result

    def test_team_fit_with_organizational_preference(self, service, base_context):
        """Test team fit with organizational preference."""
        team_needs = {
            'positions': {},
            'organizations': ['Yankees']
        }

        fit_analysis = service._analyze_team_fit(base_context, team_needs)
        assert fit_analysis.get('organizational_preference') is True


class TestPersonalizationIntegration:
    """Integration tests for personalization service."""

    @pytest.fixture
    def service(self):
        """Service instance for integration tests."""
        return UserPersonalizationService()

    def test_full_personalization_workflow_dynasty(self, service):
        """Test complete personalization workflow for dynasty league."""
        base_context = {
            'name': 'Ronald Acuna III',
            'age': 19,
            'position': 'OF',
            'organization': 'Braves',
            'success_probability': 0.8,
            'risk_level': 'Medium',
            'timeline_data': {'years_away': 3}
        }

        user_preferences = {
            'league_format': LeagueFormat.DYNASTY,
            'scoring_system': ScoringSystem.CATEGORIES,
            'timeline_preference': 'long_term'
        }

        team_needs = {
            'positions': {'OF': 'high'},
            'organizations': ['Braves']
        }

        result = service.personalize_outlook_context(
            base_context, user_preferences, team_needs
        )

        # Verify all personalization components
        assert result['league_insights']['value_focus'] == 'upside'
        assert result['team_fit']['organizational_preference'] is True
        assert result['timeline_relevance']['timeline_fit'] in ['acceptable', 'good']
        assert result['dynasty_insights']['dynasty_grade'] in ['A+', 'A', 'B+']

    def test_full_personalization_workflow_redraft(self, service):
        """Test complete personalization workflow for redraft league."""
        base_context = {
            'name': 'MLB Ready Player',
            'age': 24,
            'position': 'C',
            'organization': 'Dodgers',
            'success_probability': 0.7,
            'risk_level': 'Low',
            'timeline_data': {'years_away': 0}
        }

        user_preferences = {
            'league_format': LeagueFormat.REDRAFT,
            'scoring_system': ScoringSystem.POINTS
        }

        team_needs = {
            'positions': {'C': 'critical'}
        }

        result = service.personalize_outlook_context(
            base_context, user_preferences, team_needs
        )

        # Verify redraft-specific optimizations
        assert result['league_insights']['risk_tolerance'] == 'low'
        assert result['team_fit']['priority_level'] == 'high'
        assert result['timeline_relevance']['timeline_fit'] == 'perfect'
        assert result['positional_value']['scarcity_level'] == 'very_high'