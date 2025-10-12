"""
Narrative Generation Service for AI Player Outlook Generation

This service provides 3-4 sentence player outlooks using SHAP feature importance,
risk assessment, and timeline estimation.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import asyncio

from app.ml.narrative_templates import template_engine
from app.core.cache_manager import cache_manager
from app.db.models import Prospect, ScoutingGrades
from app.schemas.ml_predictions import PredictionResponse

logger = logging.getLogger(__name__)


class NarrativeGenerationService:
    """
    Service for generating AI-powered prospect outlooks with natural language explanations.
    """

    def __init__(self):
        """Initialize the narrative generation service."""
        self.template_engine = template_engine
        self.cache_manager = cache_manager
        self.current_year = datetime.now().year

    async def generate_prospect_outlook(
        self,
        prospect: Prospect,
        prediction_data: PredictionResponse,
        scouting_grades: Optional[ScoutingGrades] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> str:
        """
        Generate a comprehensive 3-4 sentence outlook for a prospect.

        Args:
            prospect: Prospect model instance
            prediction_data: ML prediction results with SHAP values
            scouting_grades: Optional scouting grade data
            user_preferences: Optional user personalization data
            user_id: Optional user ID for caching personalized outlooks

        Returns:
            Generated narrative outlook string

        Raises:
            ValueError: If required data is missing
            Exception: If narrative generation fails
        """
        try:
            # Validate inputs
            if not prospect or not prediction_data:
                raise ValueError("Prospect and prediction data are required")

            # Check cache first
            cached_narrative = await self.cache_manager.get_cached_narrative(
                prospect_id=prospect.id,
                model_version=prediction_data.model_version,
                user_id=user_id,
                template_version="v1.0"
            )

            if cached_narrative:
                logger.debug(f"Returned cached outlook for prospect {prospect.id}")
                return cached_narrative

            # Extract top contributing factors from SHAP values
            top_factors = self._extract_contributing_factors(
                prediction_data.feature_importance or {}
            )

            # Determine risk assessment
            risk_level = self._assess_risk_level(
                prediction_data.confidence_level,
                prospect.age,
                prospect.level,
                prediction_data.success_probability
            )

            # Calculate timeline estimation
            timeline = self._estimate_timeline(
                prospect.eta_year,
                prospect.age,
                prospect.level
            )

            # Select appropriate template
            template_name = self._select_template(prospect, prediction_data, scouting_grades)

            # Create comprehensive context
            context = self._create_narrative_context(
                prospect=prospect,
                prediction_data=prediction_data,
                scouting_grades=scouting_grades,
                user_preferences=user_preferences,
                top_factors=top_factors,
                risk_level=risk_level,
                timeline=timeline
            )

            # Generate narrative
            narrative = self.template_engine.render_outlook(template_name, context)

            # Apply readability optimization
            optimized_narrative = self._optimize_readability(narrative)

            # Cache the generated narrative
            await self.cache_manager.cache_narrative(
                prospect_id=prospect.id,
                model_version=prediction_data.model_version,
                user_id=user_id,
                narrative_data=optimized_narrative,
                template_version="v1.0",
                ttl=86400  # 24 hours
            )

            logger.info(f"Generated and cached outlook for prospect {prospect.id}")
            return optimized_narrative

        except Exception as e:
            logger.error(f"Failed to generate outlook for prospect {prospect.id}: {e}")
            raise

    def _extract_contributing_factors(
        self,
        shap_values: Dict[str, float],
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Extract top contributing factors from SHAP values.

        Args:
            shap_values: SHAP feature importance values
            limit: Maximum number of factors to extract

        Returns:
            List of factor dictionaries with name, impact, and magnitude
        """
        if not shap_values:
            return []

        # Sort by absolute impact
        sorted_factors = sorted(
            shap_values.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        factors = []
        for feature, value in sorted_factors[:limit]:
            # Convert technical feature names to readable descriptions
            readable_name = self._convert_feature_name(feature)

            factors.append({
                'name': readable_name,
                'technical_name': feature,
                'value': value,
                'impact': 'positive' if value > 0 else 'negative',
                'magnitude': abs(value),
                'importance_rank': len(factors) + 1
            })

        return factors

    def _convert_feature_name(self, technical_name: str) -> str:
        """
        Convert technical feature names to readable descriptions.

        Args:
            technical_name: Technical feature name from model

        Returns:
            Human-readable feature description
        """
        feature_mapping = {
            # Hitting features
            'hitting_ability': 'hitting ability',
            'power_potential': 'power potential',
            'contact_rate': 'contact skills',
            'plate_discipline': 'plate discipline',
            'bat_speed': 'bat speed',
            'exit_velocity': 'exit velocity',

            # Pitching features
            'fastball_velocity': 'fastball velocity',
            'command_control': 'command and control',
            'breaking_ball_quality': 'breaking ball quality',
            'changeup_effectiveness': 'changeup effectiveness',
            'strikeout_rate': 'strikeout ability',
            'walk_rate': 'command',

            # General features
            'age_adjusted_performance': 'age-adjusted performance',
            'level_performance': 'performance at current level',
            'organizational_ranking': 'organizational ranking',
            'injury_history': 'injury history',
            'physical_projection': 'physical projection',
            'mental_makeup': 'mental makeup',
            'work_ethic': 'work ethic'
        }

        return feature_mapping.get(technical_name, technical_name.replace('_', ' '))

    def _assess_risk_level(
        self,
        confidence: float,
        age: int,
        level: str,
        success_probability: float
    ) -> str:
        """
        Assess overall risk level for prospect development.

        Args:
            confidence: Model confidence level
            age: Prospect age
            level: Current playing level
            success_probability: Success probability from model

        Returns:
            Risk level: 'Low', 'Medium', or 'High'
        """
        risk_score = 0

        # Confidence factor (higher confidence = lower risk)
        if confidence >= 0.85:
            risk_score += 0
        elif confidence >= 0.7:
            risk_score += 1
        elif confidence >= 0.55:
            risk_score += 2
        else:
            risk_score += 3

        # Success probability factor
        if success_probability >= 0.8:
            risk_score += 0
        elif success_probability >= 0.6:
            risk_score += 1
        elif success_probability >= 0.4:
            risk_score += 2
        else:
            risk_score += 3

        # Age factor (development time remaining)
        if age <= 20:
            risk_score += 1  # More time but more uncertainty
        elif age <= 22:
            risk_score += 0  # Sweet spot
        elif age <= 24:
            risk_score += 1  # Narrowing window
        else:
            risk_score += 2  # Limited development time

        # Level factor (track record)
        level_lower = level.lower() if level else ""
        if any(term in level_lower for term in ['aaa', 'triple']):
            risk_score += 0  # Proven at high level
        elif any(term in level_lower for term in ['aa', 'double']):
            risk_score += 1  # Good experience
        elif any(term in level_lower for term in ['high-a', 'high a']):
            risk_score += 2  # Moderate experience
        else:
            risk_score += 3  # Limited experience

        # Determine final risk level
        if risk_score <= 3:
            return "Low"
        elif risk_score <= 6:
            return "Medium"
        else:
            return "High"

    def _estimate_timeline(
        self,
        eta_year: Optional[int],
        age: int,
        level: str
    ) -> Dict[str, Any]:
        """
        Estimate prospect timeline for MLB arrival.

        Args:
            eta_year: Estimated arrival year
            age: Prospect age
            level: Current playing level

        Returns:
            Timeline dictionary with arrival estimate and certainty
        """
        current_year = self.current_year

        if eta_year:
            years_away = eta_year - current_year
            certainty = "projected"
        else:
            # Estimate based on level and age
            years_away = self._estimate_years_by_level(level, age)
            certainty = "estimated"

        return {
            'years_away': max(0, years_away),
            'eta_year': current_year + max(0, years_away),
            'certainty': certainty,
            'description': self._format_timeline_description(years_away)
        }

    def _estimate_years_by_level(self, level: str, age: int) -> int:
        """Estimate years to MLB based on current level and age."""
        level_lower = level.lower() if level else ""

        # Base years by level
        if any(term in level_lower for term in ['aaa', 'triple']):
            base_years = 1
        elif any(term in level_lower for term in ['aa', 'double']):
            base_years = 2
        elif any(term in level_lower for term in ['high-a', 'high a']):
            base_years = 3
        elif any(term in level_lower for term in ['low-a', 'low a', 'single']):
            base_years = 4
        else:
            base_years = 5  # Rookie/complex leagues

        # Adjust for age (older players typically move faster)
        if age >= 23:
            base_years = max(1, base_years - 1)
        elif age <= 19:
            base_years += 1

        return base_years

    def _format_timeline_description(self, years_away: int) -> str:
        """Format timeline into readable description."""
        if years_away <= 0:
            return "ready now"
        elif years_away == 1:
            return "next year"
        elif years_away == 2:
            return "within 2 years"
        elif years_away == 3:
            return "2-3 years away"
        else:
            return f"{years_away} years away"

    def _select_template(
        self,
        prospect: Prospect,
        prediction_data: PredictionResponse,
        scouting_grades: Optional[ScoutingGrades] = None
    ) -> str:
        """
        Select appropriate template based on prospect characteristics.

        Args:
            prospect: Prospect model instance
            prediction_data: ML prediction results
            scouting_grades: Optional scouting grade data

        Returns:
            Template filename
        """
        # Special status templates (highest priority)
        if self._is_mlb_ready(prospect, prediction_data):
            return "mlb_ready.j2"

        if self._is_top_prospect(prospect, prediction_data):
            return "top_100_prospect.j2"

        if self._is_sleeper_prospect(prospect, prediction_data):
            return "sleeper_prospect.j2"

        # Age-based selection for young prospects
        if prospect.age <= 20:
            return "young_prospect.j2"

        # Level-based selection for advanced prospects
        level_lower = prospect.level.lower() if prospect.level else ""
        if any(term in level_lower for term in ['aaa', 'triple', 'aa', 'double']):
            return "advanced_prospect.j2"

        # Archetype-based selection
        archetype = self._determine_prospect_archetype(prospect, prediction_data, scouting_grades)

        if archetype:
            return f"{archetype}.j2"

        # Fallback to position-based selection
        position_lower = prospect.position.lower() if prospect.position else ""
        if any(term in position_lower for term in ['p', 'rhp', 'lhp', 'pitcher']):
            return "base_pitcher.j2"
        else:
            return "base_hitter.j2"

    def _is_mlb_ready(self, prospect: Prospect, prediction_data: PredictionResponse) -> bool:
        """Determine if prospect is MLB ready."""
        level_lower = prospect.level.lower() if prospect.level else ""
        return (
            any(term in level_lower for term in ['aaa', 'triple']) and
            prediction_data.success_probability >= 0.7 and
            prediction_data.confidence_level >= 0.8
        )

    def _is_top_prospect(self, prospect: Prospect, prediction_data: PredictionResponse) -> bool:
        """Determine if prospect is top-tier status."""
        return (
            prediction_data.success_probability >= 0.8 and
            prediction_data.confidence_level >= 0.85 and
            prospect.age <= 23
        )

    def _is_sleeper_prospect(self, prospect: Prospect, prediction_data: PredictionResponse) -> bool:
        """Determine if prospect is a sleeper candidate."""
        level_lower = prospect.level.lower() if prospect.level else ""
        return (
            prediction_data.success_probability >= 0.6 and
            prediction_data.confidence_level >= 0.7 and
            any(term in level_lower for term in ['high-a', 'low-a', 'single', 'rookie']) and
            prospect.age <= 22
        )

    def _determine_prospect_archetype(
        self,
        prospect: Prospect,
        prediction_data: PredictionResponse,
        scouting_grades: Optional[ScoutingGrades] = None
    ) -> Optional[str]:
        """
        Determine prospect archetype based on features and scouting grades.

        Returns:
            Archetype string or None if no clear archetype
        """
        position_lower = prospect.position.lower() if prospect.position else ""
        is_pitcher = any(term in position_lower for term in ['p', 'rhp', 'lhp', 'pitcher'])

        # Extract top SHAP features
        shap_values = prediction_data.feature_importance or {}
        if not shap_values:
            return None

        top_features = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:3]

        if is_pitcher:
            return self._determine_pitcher_archetype(top_features, scouting_grades)
        else:
            return self._determine_hitter_archetype(top_features, scouting_grades)

    def _determine_pitcher_archetype(
        self,
        top_features: List[Tuple[str, float]],
        scouting_grades: Optional[ScoutingGrades] = None
    ) -> Optional[str]:
        """Determine pitcher archetype from features and grades."""
        feature_names = [feature[0] for feature, _ in top_features]

        # Power pitcher indicators
        power_indicators = ['fastball_velocity', 'strikeout_rate', 'power', 'velocity']
        for feature in feature_names:
            if any(indicator in feature.lower() for indicator in power_indicators):
                return "power_pitcher"

        # Finesse pitcher indicators
        finesse_indicators = ['command', 'control', 'breaking_ball', 'changeup', 'location']
        for feature in feature_names:
            if any(indicator in feature.lower() for indicator in finesse_indicators):
                return "finesse_pitcher"

        return None

    def _determine_hitter_archetype(
        self,
        top_features: List[Tuple[str, float]],
        scouting_grades: Optional[ScoutingGrades] = None
    ) -> Optional[str]:
        """Determine hitter archetype from features and grades."""
        feature_names = [feature[0] for feature, _ in top_features]

        # Power hitter indicators
        power_indicators = ['power', 'exit_velocity', 'home_run', 'slugging']
        for feature in feature_names:
            if any(indicator in feature.lower() for indicator in power_indicators):
                return "power_hitter"

        # Contact hitter indicators
        contact_indicators = ['hitting_ability', 'contact', 'plate_discipline', 'average']
        for feature in feature_names:
            if any(indicator in feature.lower() for indicator in contact_indicators):
                return "contact_hitter"

        # Defensive specialist indicators
        defense_indicators = ['defense', 'fielding', 'arm', 'glove']
        for feature in feature_names:
            if any(indicator in feature.lower() for indicator in defense_indicators):
                return "defensive_specialist"

        return None

    def _create_narrative_context(
        self,
        prospect: Prospect,
        prediction_data: PredictionResponse,
        scouting_grades: Optional[ScoutingGrades],
        user_preferences: Optional[Dict[str, Any]],
        top_factors: List[Dict[str, Any]],
        risk_level: str,
        timeline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create comprehensive context for template rendering."""
        context = {
            # Prospect basics
            'name': prospect.name,
            'age': prospect.age,
            'position': prospect.position,
            'organization': prospect.organization,
            'level': prospect.level,
            'eta_year': prospect.eta_year,

            # Prediction data
            'success_probability': prediction_data.success_probability,
            'confidence_level': prediction_data.confidence_level,
            'model_version': prediction_data.model_version,

            # Analysis results
            'top_features': top_factors,
            'risk_level': risk_level,
            'timeline': timeline['description'],
            'timeline_data': timeline,

            # SHAP values
            'shap_values': prediction_data.feature_importance or {},

            # User personalization
            'user_preferences': user_preferences or {},

            # Context
            'current_year': self.current_year
        }

        # Add scouting grades if available
        if scouting_grades:
            context['scouting_grades'] = {
                'overall': scouting_grades.overall_grade,
                'hit': getattr(scouting_grades, 'hit_grade', None),
                'power': getattr(scouting_grades, 'power_grade', None),
                'run': getattr(scouting_grades, 'run_grade', None),
                'field': getattr(scouting_grades, 'field_grade', None),
                'arm': getattr(scouting_grades, 'arm_grade', None)
            }

        return context

    def _optimize_readability(self, narrative: str) -> str:
        """
        Optimize narrative for readability and coherence.

        Args:
            narrative: Raw generated narrative

        Returns:
            Optimized narrative text
        """
        # Clean up extra whitespace
        narrative = ' '.join(narrative.split())

        # Ensure proper sentence endings
        if not narrative.endswith('.'):
            narrative += '.'

        # Basic sentence flow optimization
        sentences = narrative.split('.')
        sentences = [s.strip() for s in sentences if s.strip()]

        # Rejoin with proper spacing
        optimized = '. '.join(sentences)
        if optimized and not optimized.endswith('.'):
            optimized += '.'

        return optimized

    async def generate_batch_outlooks(
        self,
        prospects: List[Prospect],
        prediction_data_list: List[PredictionResponse],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Generate outlooks for multiple prospects in batch.

        Args:
            prospects: List of prospect model instances
            prediction_data_list: List of prediction results
            user_preferences: Optional user personalization data

        Returns:
            List of generated narrative outlooks

        Raises:
            ValueError: If prospect and prediction lists don't match
        """
        if len(prospects) != len(prediction_data_list):
            raise ValueError("Prospect and prediction data lists must have same length")

        tasks = []
        for prospect, prediction_data in zip(prospects, prediction_data_list):
            task = self.generate_prospect_outlook(
                prospect=prospect,
                prediction_data=prediction_data,
                user_preferences=user_preferences
            )
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions in the results
            outlooks = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate outlook for prospect {prospects[i].id}: {result}")
                    outlooks.append(f"Unable to generate outlook for {prospects[i].name}")
                else:
                    outlooks.append(result)

            return outlooks

        except Exception as e:
            logger.error(f"Batch outlook generation failed: {e}")
            raise


# Singleton instance for application use
narrative_service = NarrativeGenerationService()