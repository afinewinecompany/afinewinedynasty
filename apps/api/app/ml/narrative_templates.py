"""
Narrative Templates Engine for AI Player Outlook Generation

This module provides Jinja2-based template rendering for dynamic prospect outlooks
using SHAP feature importance data and prospect characteristics.
"""

import os
from typing import Dict, Any, Optional, List
from jinja2 import Environment, FileSystemLoader, Template, TemplateError
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class NarrativeTemplateEngine:
    """
    Jinja2-based template engine for generating dynamic prospect outlooks.
    Integrates with SHAP feature importance data for narrative generation.
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize the narrative template engine.

        Args:
            template_dir: Path to template directory. Defaults to app/templates/outlook
        """
        if template_dir is None:
            # Default to project template directory
            current_dir = Path(__file__).parent.parent
            template_dir = str(current_dir / "templates" / "outlook")

        self.template_dir = template_dir
        self._setup_environment()

    def _setup_environment(self):
        """Setup Jinja2 environment with custom filters and functions."""
        try:
            # Create template directory if it doesn't exist
            os.makedirs(self.template_dir, exist_ok=True)

            # Initialize Jinja2 environment
            self.env = Environment(
                loader=FileSystemLoader(self.template_dir),
                autoescape=True,
                trim_blocks=True,
                lstrip_blocks=True
            )

            # Register custom filters
            self.env.filters['format_probability'] = self._format_probability
            self.env.filters['format_timeline'] = self._format_timeline
            self.env.filters['risk_level'] = self._calculate_risk_level
            self.env.filters['top_features'] = self._extract_top_features

            logger.info(f"Narrative template engine initialized with directory: {self.template_dir}")

        except Exception as e:
            logger.error(f"Failed to setup template environment: {e}")
            raise

    def _format_probability(self, probability: float) -> str:
        """Format probability as percentage."""
        return f"{probability * 100:.1f}%"

    def _format_timeline(self, eta_year: Optional[int], current_year: int = 2024) -> str:
        """Format ETA timeline for narrative."""
        if not eta_year:
            return "uncertain timeline"

        years_away = eta_year - current_year
        if years_away <= 0:
            return "ready now"
        elif years_away == 1:
            return "next year"
        elif years_away <= 2:
            return "within 2 years"
        elif years_away <= 3:
            return "2-3 years away"
        else:
            return f"{years_away} years away"

    def _calculate_risk_level(self, confidence: float, age: int, level: str) -> str:
        """Calculate risk level based on confidence, age, and level."""
        risk_score = 0

        # Confidence factor (higher confidence = lower risk)
        if confidence >= 0.8:
            risk_score += 1  # Low risk
        elif confidence >= 0.6:
            risk_score += 2  # Medium risk
        else:
            risk_score += 3  # High risk

        # Age factor (younger = higher risk)
        if age <= 20:
            risk_score += 2
        elif age <= 22:
            risk_score += 1

        # Level factor (higher level = lower risk)
        level_lower = level.lower() if level else ""
        if "aaa" in level_lower or "triple" in level_lower:
            risk_score += 0
        elif "aa" in level_lower or "double" in level_lower:
            risk_score += 1
        else:
            risk_score += 2

        # Determine final risk level
        if risk_score <= 3:
            return "Low"
        elif risk_score <= 5:
            return "Medium"
        else:
            return "High"

    def _extract_top_features(self, shap_values: Dict[str, float], limit: int = 3) -> List[Dict[str, Any]]:
        """Extract top contributing features from SHAP values."""
        if not shap_values:
            return []

        # Sort by absolute SHAP value (impact magnitude)
        sorted_features = sorted(
            shap_values.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        top_features = []
        for feature, value in sorted_features[:limit]:
            top_features.append({
                'name': feature,
                'value': value,
                'impact': 'positive' if value > 0 else 'negative',
                'magnitude': abs(value)
            })

        return top_features

    def render_outlook(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render prospect outlook using specified template and context.

        Args:
            template_name: Name of the template file
            context: Context data for template rendering

        Returns:
            Rendered outlook text

        Raises:
            TemplateError: If template rendering fails
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except TemplateError as e:
            logger.error(f"Template rendering failed for {template_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error rendering template {template_name}: {e}")
            raise TemplateError(f"Failed to render template: {e}")

    def validate_template(self, template_name: str) -> bool:
        """
        Validate template syntax and availability.

        Args:
            template_name: Name of the template file

        Returns:
            True if template is valid, False otherwise
        """
        try:
            template = self.env.get_template(template_name)
            # Try to render with minimal context to check syntax
            template.render()
            return True
        except TemplateError as e:
            logger.warning(f"Template validation failed for {template_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating template {template_name}: {e}")
            return False

    def list_available_templates(self) -> List[str]:
        """
        List all available template files.

        Returns:
            List of template file names
        """
        try:
            return self.env.list_templates()
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return []

    def create_template_context(
        self,
        prospect_data: Dict[str, Any],
        shap_values: Dict[str, float],
        prediction_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create comprehensive template context from prospect and prediction data.

        Args:
            prospect_data: Basic prospect information
            shap_values: SHAP feature importance values
            prediction_data: ML prediction results
            user_preferences: Optional user personalization data

        Returns:
            Template context dictionary
        """
        context = {
            # Prospect basics
            'name': prospect_data.get('name', 'Unknown'),
            'position': prospect_data.get('position', 'Unknown'),
            'age': prospect_data.get('age', 0),
            'organization': prospect_data.get('organization', 'Unknown'),
            'level': prospect_data.get('level', 'Unknown'),
            'eta_year': prospect_data.get('eta_year'),

            # Prediction data
            'success_probability': prediction_data.get('success_probability', 0.0),
            'confidence_level': prediction_data.get('confidence_level', 0.0),
            'model_version': prediction_data.get('model_version', 'Unknown'),

            # SHAP analysis
            'shap_values': shap_values,
            'top_features': self._extract_top_features(shap_values),

            # Calculated fields
            'risk_level': self._calculate_risk_level(
                prediction_data.get('confidence_level', 0.0),
                prospect_data.get('age', 25),
                prospect_data.get('level', '')
            ),
            'timeline': self._format_timeline(prospect_data.get('eta_year')),

            # User personalization
            'user_preferences': user_preferences or {},

            # Current context
            'current_year': 2024
        }

        return context


# Singleton instance for application use
template_engine = NarrativeTemplateEngine()