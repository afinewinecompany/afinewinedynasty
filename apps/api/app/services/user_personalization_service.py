"""
User Personalization Service for AI Player Outlook Generation

This service provides personalized prospect insights based on user league settings,
team needs, and preferences.
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class LeagueFormat(str, Enum):
    """League format types for personalization."""
    DYNASTY = "dynasty"
    REDRAFT = "redraft"
    KEEPER = "keeper"
    BEST_BALL = "best_ball"


class ScoringSystem(str, Enum):
    """Scoring system types."""
    POINTS = "points"
    CATEGORIES = "categories"
    ROTO = "roto"


class UserPersonalizationService:
    """
    Service for personalizing prospect outlooks based on user preferences and needs.
    """

    def __init__(self):
        """Initialize the user personalization service."""
        self.position_priorities = {
            'hitter': ['C', '1B', '2B', '3B', 'SS', 'OF', 'DH'],
            'pitcher': ['SP', 'RP', 'P']
        }

    def personalize_outlook_context(
        self,
        base_context: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
        team_needs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enhance outlook context with user-specific personalization.

        Args:
            base_context: Base template context
            user_preferences: User league settings and preferences
            team_needs: Current team roster needs

        Returns:
            Enhanced context with personalization data
        """
        if not user_preferences:
            user_preferences = {}

        if not team_needs:
            team_needs = {}

        # Create enhanced context
        enhanced_context = base_context.copy()

        # Add league format insights
        league_format = user_preferences.get('league_format', LeagueFormat.DYNASTY)
        enhanced_context['league_insights'] = self._generate_league_insights(
            base_context, league_format
        )

        # Add team need analysis
        enhanced_context['team_fit'] = self._analyze_team_fit(
            base_context, team_needs
        )

        # Add timeline relevance
        enhanced_context['timeline_relevance'] = self._assess_timeline_relevance(
            base_context, user_preferences
        )

        # Add positional value
        enhanced_context['positional_value'] = self._calculate_positional_value(
            base_context, user_preferences
        )

        # Add dynasty-specific insights
        if league_format == LeagueFormat.DYNASTY:
            enhanced_context['dynasty_insights'] = self._generate_dynasty_insights(
                base_context
            )

        # Add user preference flags
        enhanced_context['user_preferences'] = user_preferences
        enhanced_context['personalization_applied'] = True

        return enhanced_context

    def _generate_league_insights(
        self,
        context: Dict[str, Any],
        league_format: str
    ) -> Dict[str, Any]:
        """
        Generate league format specific insights.

        Args:
            context: Base context data
            league_format: Type of league format

        Returns:
            League-specific insights
        """
        insights = {
            'format': league_format,
            'timeline_weight': 1.0,
            'risk_tolerance': 'medium',
            'value_focus': 'balanced'
        }

        if league_format == LeagueFormat.DYNASTY:
            insights.update({
                'timeline_weight': 0.7,  # Less important for dynasty
                'risk_tolerance': 'high',  # More willing to take risks
                'value_focus': 'upside',  # Focus on ceiling
                'recommendation': self._get_dynasty_recommendation(context)
            })

        elif league_format == LeagueFormat.REDRAFT:
            insights.update({
                'timeline_weight': 1.5,  # Very important for redraft
                'risk_tolerance': 'low',  # Want safe picks
                'value_focus': 'floor',  # Focus on reliability
                'recommendation': self._get_redraft_recommendation(context)
            })

        elif league_format == LeagueFormat.KEEPER:
            insights.update({
                'timeline_weight': 1.0,  # Balanced importance
                'risk_tolerance': 'medium',  # Moderate risk
                'value_focus': 'balanced',  # Balance floor and ceiling
                'recommendation': self._get_keeper_recommendation(context)
            })

        return insights

    def _get_dynasty_recommendation(self, context: Dict[str, Any]) -> str:
        """Generate dynasty-specific recommendation."""
        age = context.get('age', 25)
        success_prob = context.get('success_probability', 0.5)
        risk_level = context.get('risk_level', 'Medium')

        if age <= 21 and success_prob >= 0.7:
            return "Excellent dynasty target with long-term upside"
        elif age <= 23 and success_prob >= 0.6:
            return "Strong dynasty asset with good development runway"
        elif risk_level == 'High' and success_prob >= 0.6:
            return "High-upside dynasty lottery ticket worth considering"
        elif age >= 24:
            return "Limited dynasty appeal due to shortened development window"
        else:
            return "Moderate dynasty interest depending on acquisition cost"

    def _get_redraft_recommendation(self, context: Dict[str, Any]) -> str:
        """Generate redraft-specific recommendation."""
        timeline_data = context.get('timeline_data', {})
        years_away = timeline_data.get('years_away', 3)
        success_prob = context.get('success_probability', 0.5)
        risk_level = context.get('risk_level', 'Medium')

        if years_away <= 0:
            return "Immediate redraft relevance with MLB readiness"
        elif years_away == 1 and success_prob >= 0.7:
            return "Potential late-season contributor in redraft leagues"
        elif years_away <= 2 and risk_level == 'Low':
            return "Monitor for redraft relevance next season"
        else:
            return "Limited redraft appeal due to timeline"

    def _get_keeper_recommendation(self, context: Dict[str, Any]) -> str:
        """Generate keeper-specific recommendation."""
        age = context.get('age', 25)
        timeline_data = context.get('timeline_data', {})
        years_away = timeline_data.get('years_away', 3)
        success_prob = context.get('success_probability', 0.5)

        if years_away <= 1 and success_prob >= 0.6:
            return "Strong keeper candidate with near-term impact"
        elif age <= 22 and success_prob >= 0.6:
            return "Solid keeper value with development upside"
        elif years_away <= 2:
            return "Reasonable keeper option depending on league settings"
        else:
            return "Limited keeper appeal due to distant timeline"

    def _analyze_team_fit(
        self,
        context: Dict[str, Any],
        team_needs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze how prospect fits team needs.

        Args:
            context: Base context data
            team_needs: Team roster needs

        Returns:
            Team fit analysis
        """
        position = context.get('position', 'Unknown')
        prospect_name = context.get('name', 'Unknown')

        fit_analysis = {
            'position_need': 'unknown',
            'priority_level': 'medium',
            'roster_impact': 'depth',
            'recommendation': 'Monitor based on team needs'
        }

        if not team_needs:
            return fit_analysis

        # Check positional needs
        position_needs = team_needs.get('positions', {})
        if position in position_needs:
            need_level = position_needs[position]
            fit_analysis.update({
                'position_need': need_level,
                'priority_level': 'high' if need_level == 'critical' else 'medium',
                'roster_impact': 'starter' if need_level in ['critical', 'high'] else 'depth'
            })

        # Check organizational preferences
        org_preferences = team_needs.get('organizations', [])
        prospect_org = context.get('organization', '')
        if prospect_org in org_preferences:
            fit_analysis['organizational_preference'] = True

        # Generate recommendation
        fit_analysis['recommendation'] = self._generate_team_fit_recommendation(
            fit_analysis, context
        )

        return fit_analysis

    def _generate_team_fit_recommendation(
        self,
        fit_analysis: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Generate team fit recommendation."""
        position_need = fit_analysis.get('position_need', 'unknown')
        success_prob = context.get('success_probability', 0.5)

        if position_need == 'critical' and success_prob >= 0.6:
            return "High priority target addressing critical team need"
        elif position_need == 'high' and success_prob >= 0.5:
            return "Strong consideration given positional need"
        elif position_need in ['medium', 'low']:
            return "Monitor as depth option for positional need"
        elif success_prob >= 0.8:
            return "Consider regardless of need given high success probability"
        else:
            return "Lower priority given current team composition"

    def _assess_timeline_relevance(
        self,
        context: Dict[str, Any],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess prospect timeline relevance to user.

        Args:
            context: Base context data
            user_preferences: User preferences including timeline

        Returns:
            Timeline relevance assessment
        """
        timeline_data = context.get('timeline_data', {})
        years_away = timeline_data.get('years_away', 3)
        league_format = user_preferences.get('league_format', LeagueFormat.DYNASTY)

        relevance = {
            'years_away': years_away,
            'relevance_score': 0.5,
            'timeline_fit': 'neutral',
            'user_timeline_preference': user_preferences.get('timeline_preference', 'balanced')
        }

        # Calculate relevance score based on league format
        if league_format == LeagueFormat.DYNASTY:
            # Dynasty values all timelines
            if years_away <= 1:
                relevance['relevance_score'] = 0.9
                relevance['timeline_fit'] = 'excellent'
            elif years_away <= 3:
                relevance['relevance_score'] = 0.8
                relevance['timeline_fit'] = 'good'
            else:
                relevance['relevance_score'] = 0.6
                relevance['timeline_fit'] = 'acceptable'

        elif league_format == LeagueFormat.REDRAFT:
            # Redraft needs immediate impact
            if years_away <= 0:
                relevance['relevance_score'] = 1.0
                relevance['timeline_fit'] = 'perfect'
            elif years_away == 1:
                relevance['relevance_score'] = 0.4
                relevance['timeline_fit'] = 'marginal'
            else:
                relevance['relevance_score'] = 0.1
                relevance['timeline_fit'] = 'poor'

        return relevance

    def _calculate_positional_value(
        self,
        context: Dict[str, Any],
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate positional value and scarcity.

        Args:
            context: Base context data
            user_preferences: User preferences

        Returns:
            Positional value analysis
        """
        position = context.get('position', 'Unknown')
        scoring_system = user_preferences.get('scoring_system', ScoringSystem.CATEGORIES)

        # Position scarcity rankings (lower = more scarce/valuable)
        position_scarcity = {
            'C': 1,    # Most scarce
            'SS': 2,
            '2B': 3,
            '3B': 4,
            'CF': 5,
            'OF': 6,
            '1B': 7,
            'DH': 8,   # Least scarce for hitters
            'SP': 3,   # Pitchers
            'RP': 6,
            'P': 4
        }

        scarcity_score = position_scarcity.get(position, 5)

        value_analysis = {
            'position': position,
            'scarcity_rank': scarcity_score,
            'scarcity_level': self._get_scarcity_level(scarcity_score),
            'positional_premium': self._calculate_positional_premium(position, scoring_system)
        }

        return value_analysis

    def _get_scarcity_level(self, scarcity_score: int) -> str:
        """Convert scarcity score to descriptive level."""
        if scarcity_score <= 2:
            return "very_high"
        elif scarcity_score <= 4:
            return "high"
        elif scarcity_score <= 6:
            return "medium"
        else:
            return "low"

    def _calculate_positional_premium(self, position: str, scoring_system: str) -> float:
        """Calculate position premium based on scoring system."""
        # Base premiums
        premiums = {
            'C': 1.3,
            'SS': 1.2,
            '2B': 1.1,
            '3B': 1.05,
            'CF': 1.02,
            'OF': 1.0,
            '1B': 0.95,
            'DH': 0.9,
            'SP': 1.1,
            'RP': 0.8,
            'P': 1.0
        }

        base_premium = premiums.get(position, 1.0)

        # Adjust for scoring system
        if scoring_system == ScoringSystem.POINTS:
            # Points leagues often favor offensive positions
            if position in ['1B', 'DH', 'OF']:
                base_premium *= 1.1
        elif scoring_system == ScoringSystem.CATEGORIES:
            # Categories may value speed/steals more
            if position in ['SS', '2B', 'CF']:
                base_premium *= 1.05

        return base_premium

    def _generate_dynasty_insights(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate dynasty-specific insights."""
        age = context.get('age', 25)
        success_prob = context.get('success_probability', 0.5)
        timeline_data = context.get('timeline_data', {})
        years_away = timeline_data.get('years_away', 3)

        insights = {
            'dynasty_grade': self._calculate_dynasty_grade(age, success_prob, years_away),
            'development_runway': self._assess_development_runway(age),
            'long_term_value': self._assess_long_term_value(age, success_prob),
            'acquisition_timing': self._suggest_acquisition_timing(context)
        }

        return insights

    def _calculate_dynasty_grade(self, age: int, success_prob: float, years_away: int) -> str:
        """Calculate dynasty grade (A+ to D)."""
        score = 0

        # Age component (younger is better)
        if age <= 20:
            score += 25
        elif age <= 22:
            score += 20
        elif age <= 24:
            score += 10
        else:
            score += 0

        # Success probability component
        score += success_prob * 50

        # Timeline component (less important for dynasty)
        if years_away <= 2:
            score += 15
        elif years_away <= 4:
            score += 10
        else:
            score += 5

        # Convert to grade
        if score >= 80:
            return "A+"
        elif score >= 70:
            return "A"
        elif score >= 60:
            return "B+"
        elif score >= 50:
            return "B"
        elif score >= 40:
            return "C+"
        elif score >= 30:
            return "C"
        else:
            return "D"

    def _assess_development_runway(self, age: int) -> str:
        """Assess remaining development runway."""
        if age <= 20:
            return "extensive"
        elif age <= 22:
            return "substantial"
        elif age <= 24:
            return "moderate"
        else:
            return "limited"

    def _assess_long_term_value(self, age: int, success_prob: float) -> str:
        """Assess long-term dynasty value."""
        if age <= 22 and success_prob >= 0.7:
            return "elite"
        elif age <= 24 and success_prob >= 0.6:
            return "high"
        elif success_prob >= 0.5:
            return "moderate"
        else:
            return "speculative"

    def _suggest_acquisition_timing(self, context: Dict[str, Any]) -> str:
        """Suggest optimal acquisition timing."""
        timeline_data = context.get('timeline_data', {})
        years_away = timeline_data.get('years_away', 3)
        risk_level = context.get('risk_level', 'Medium')

        if years_away <= 1 and risk_level == 'Low':
            return "acquire_now"
        elif years_away <= 2:
            return "monitor_closely"
        elif risk_level == 'High':
            return "wait_for_discount"
        else:
            return "standard_timing"


# Singleton instance for application use
user_personalization_service = UserPersonalizationService()