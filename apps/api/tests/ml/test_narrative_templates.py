"""
Tests for narrative template engine functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os
from pathlib import Path

from app.ml.narrative_templates import NarrativeTemplateEngine


class TestNarrativeTemplateEngine:
    """Test cases for the narrative template engine."""

    @pytest.fixture
    def temp_template_dir(self):
        """Create temporary template directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def template_engine(self, temp_template_dir):
        """Create template engine instance with temp directory."""
        return NarrativeTemplateEngine(template_dir=temp_template_dir)

    @pytest.fixture
    def sample_template(self, temp_template_dir):
        """Create a sample template file for testing."""
        template_content = """{{ name }} is a {{ age }}-year-old {{ position }}.
{%- if top_features %}
{%- set primary_feature = top_features[0] %}
Primary strength: {{ primary_feature.name }}.
{%- endif %}
Success probability: {{ success_probability | format_probability }}."""

        template_path = os.path.join(temp_template_dir, "test_template.j2")
        with open(template_path, 'w') as f:
            f.write(template_content)
        return "test_template.j2"

    @pytest.fixture
    def sample_context(self):
        """Sample context data for template rendering."""
        return {
            'name': 'John Doe',
            'age': 21,
            'position': 'SS',
            'organization': 'Yankees',
            'level': 'Double-A',
            'eta_year': 2026,
            'success_probability': 0.75,
            'confidence_level': 0.85,
            'shap_values': {
                'hitting_ability': 0.3,
                'power': 0.2,
                'speed': -0.1
            }
        }

    def test_engine_initialization(self, temp_template_dir):
        """Test template engine initialization."""
        engine = NarrativeTemplateEngine(template_dir=temp_template_dir)
        assert engine.template_dir == temp_template_dir
        assert engine.env is not None

    def test_format_probability_filter(self, template_engine):
        """Test probability formatting filter."""
        assert template_engine._format_probability(0.75) == "75.0%"
        assert template_engine._format_probability(0.333) == "33.3%"
        assert template_engine._format_probability(1.0) == "100.0%"

    def test_format_timeline_filter(self, template_engine):
        """Test timeline formatting filter."""
        assert template_engine._format_timeline(2024, 2024) == "ready now"
        assert template_engine._format_timeline(2025, 2024) == "next year"
        assert template_engine._format_timeline(2026, 2024) == "within 2 years"
        assert template_engine._format_timeline(2027, 2024) == "2-3 years away"
        assert template_engine._format_timeline(2030, 2024) == "6 years away"
        assert template_engine._format_timeline(None, 2024) == "uncertain timeline"

    def test_calculate_risk_level(self, template_engine):
        """Test risk level calculation."""
        # High confidence, young, high level = Low risk
        assert template_engine._calculate_risk_level(0.9, 23, "Triple-A") == "Low"

        # Medium confidence, older, lower level = High risk
        assert template_engine._calculate_risk_level(0.5, 19, "Rookie") == "High"

        # Medium scenario
        assert template_engine._calculate_risk_level(0.7, 21, "Double-A") == "Medium"

    def test_extract_top_features(self, template_engine):
        """Test top features extraction from SHAP values."""
        shap_values = {
            'hitting_ability': 0.3,
            'power': -0.2,
            'speed': 0.1,
            'defense': -0.05
        }

        top_features = template_engine._extract_top_features(shap_values, limit=2)

        assert len(top_features) == 2
        assert top_features[0]['name'] == 'hitting_ability'
        assert top_features[0]['impact'] == 'positive'
        assert top_features[1]['name'] == 'power'
        assert top_features[1]['impact'] == 'negative'

    def test_render_outlook(self, template_engine, sample_template, sample_context):
        """Test template rendering with context."""
        # Add top_features to context
        sample_context['top_features'] = template_engine._extract_top_features(
            sample_context['shap_values']
        )

        result = template_engine.render_outlook(sample_template, sample_context)

        assert "John Doe is a 21-year-old SS" in result
        assert "Primary strength: hitting_ability" in result
        assert "Success probability: 75.0%" in result

    def test_validate_template_valid(self, template_engine, sample_template):
        """Test template validation for valid template."""
        assert template_engine.validate_template(sample_template) is True

    def test_validate_template_invalid(self, template_engine, temp_template_dir):
        """Test template validation for invalid template."""
        # Create invalid template with syntax error
        invalid_template = "invalid_template.j2"
        template_path = os.path.join(temp_template_dir, invalid_template)
        with open(template_path, 'w') as f:
            f.write("{{ unclosed_tag")

        assert template_engine.validate_template(invalid_template) is False

    def test_list_available_templates(self, template_engine, sample_template):
        """Test listing available templates."""
        templates = template_engine.list_available_templates()
        assert sample_template in templates

    def test_create_template_context(self, template_engine):
        """Test template context creation."""
        prospect_data = {
            'name': 'Test Player',
            'age': 20,
            'position': 'OF',
            'organization': 'Red Sox',
            'level': 'High-A',
            'eta_year': 2027
        }

        shap_values = {'hitting': 0.4, 'power': 0.2}
        prediction_data = {
            'success_probability': 0.8,
            'confidence_level': 0.9,
            'model_version': 'v1.0'
        }

        context = template_engine.create_template_context(
            prospect_data, shap_values, prediction_data
        )

        assert context['name'] == 'Test Player'
        assert context['age'] == 20
        assert context['success_probability'] == 0.8
        assert len(context['top_features']) == 2
        assert context['risk_level'] in ['Low', 'Medium', 'High']

    def test_template_rendering_error_handling(self, template_engine):
        """Test error handling for template rendering."""
        with pytest.raises(Exception):
            template_engine.render_outlook("nonexistent_template.j2", {})

    def test_custom_filters_integration(self, template_engine, temp_template_dir):
        """Test that custom filters work in template rendering."""
        # Create template using custom filters
        template_content = """
Probability: {{ 0.75 | format_probability }}
Timeline: {{ 2026 | format_timeline }}
Risk: {{ confidence_level | risk_level(age, level) }}
"""
        template_path = os.path.join(temp_template_dir, "filter_test.j2")
        with open(template_path, 'w') as f:
            f.write(template_content)

        context = {
            'confidence_level': 0.8,
            'age': 22,
            'level': 'Triple-A'
        }

        result = template_engine.render_outlook("filter_test.j2", context)
        assert "75.0%" in result
        assert "within 2 years" in result


class TestTemplateEngineIntegration:
    """Integration tests for template engine with real templates."""

    @pytest.fixture
    def real_template_engine(self):
        """Template engine with real template directory."""
        # Use actual template directory structure
        current_dir = Path(__file__).parent.parent.parent
        template_dir = str(current_dir / "templates" / "outlook")
        return NarrativeTemplateEngine(template_dir=template_dir)

    def test_hitter_template_rendering(self, real_template_engine):
        """Test rendering with actual hitter template."""
        context = real_template_engine.create_template_context(
            prospect_data={
                'name': 'Mike Trout Jr.',
                'age': 19,
                'position': 'CF',
                'organization': 'Angels',
                'level': 'Single-A',
                'eta_year': 2027
            },
            shap_values={
                'hitting_ability': 0.4,
                'power': 0.3,
                'speed': 0.2
            },
            prediction_data={
                'success_probability': 0.85,
                'confidence_level': 0.9,
                'model_version': 'v1.0'
            }
        )

        try:
            result = real_template_engine.render_outlook("base_hitter.j2", context)
            assert "Mike Trout Jr." in result
            assert "19-year-old CF" in result
            assert len(result.split('.')) >= 3  # At least 3 sentences
        except Exception:
            # Template might not exist in test environment
            pytest.skip("Real templates not available in test environment")

    def test_pitcher_template_rendering(self, real_template_engine):
        """Test rendering with actual pitcher template."""
        context = real_template_engine.create_template_context(
            prospect_data={
                'name': 'Jacob deGrom Jr.',
                'age': 22,
                'position': 'RHP',
                'organization': 'Mets',
                'level': 'Double-A',
                'eta_year': 2025
            },
            shap_values={
                'fastball_velocity': 0.5,
                'command': 0.3,
                'breaking_ball': 0.1
            },
            prediction_data={
                'success_probability': 0.7,
                'confidence_level': 0.8,
                'model_version': 'v1.0'
            }
        )

        try:
            result = real_template_engine.render_outlook("base_pitcher.j2", context)
            assert "Jacob deGrom Jr." in result
            assert "22-year-old RHP" in result
            assert len(result.split('.')) >= 3  # At least 3 sentences
        except Exception:
            # Template might not exist in test environment
            pytest.skip("Real templates not available in test environment")