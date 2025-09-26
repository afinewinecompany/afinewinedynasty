"""
Narrative A/B Testing Service for AI Player Outlook Generation

This service extends the existing A/B testing framework to support testing
different narrative templates and generation approaches.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import json

from app.ml.ab_testing import ABTestManager, ABTestConfig, SplitStrategy, TrafficSplitter
from app.services.narrative_generation_service import narrative_service
from app.services.narrative_quality_service import narrative_quality_service
from app.core.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class NarrativeTestType(str, Enum):
    """Types of narrative A/B tests."""
    TEMPLATE_COMPARISON = "template_comparison"
    PERSONALIZATION_COMPARISON = "personalization_comparison"
    QUALITY_OPTIMIZATION = "quality_optimization"
    ARCHETYPE_EFFECTIVENESS = "archetype_effectiveness"


@dataclass
class NarrativeTestConfig:
    """Configuration for narrative A/B testing."""
    test_name: str
    description: str
    test_type: NarrativeTestType
    control_template: str
    variant_template: str
    control_config: Dict[str, Any]
    variant_config: Dict[str, Any]
    traffic_split_ratio: float  # Percentage for variant
    split_strategy: SplitStrategy
    minimum_sample_size: int
    success_metrics: List[str]  # engagement, quality_score, user_satisfaction
    quality_thresholds: Dict[str, float]
    user_segments: Optional[List[str]] = None


@dataclass
class NarrativeTestResult:
    """Results from narrative A/B testing."""
    test_name: str
    test_type: str
    start_time: str
    end_time: Optional[str]
    total_requests: int
    control_requests: int
    variant_requests: int
    control_metrics: Dict[str, float]
    variant_metrics: Dict[str, float]
    quality_analysis: Dict[str, Any]
    engagement_analysis: Dict[str, Any]
    statistical_significance: bool
    confidence_level: float
    recommendation: str
    winner: Optional[str]


class NarrativeABTestManager:
    """
    Manager for narrative A/B testing with template and personalization experiments.
    """

    def __init__(self):
        """Initialize the narrative A/B test manager."""
        self.active_tests: Dict[str, NarrativeTestConfig] = {}
        self.test_data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self.test_results: Dict[str, NarrativeTestResult] = {}

    def create_narrative_test(self, config: NarrativeTestConfig) -> str:
        """
        Create a new narrative A/B test.

        Args:
            config: Narrative test configuration

        Returns:
            Test ID
        """
        logger.info(f"Creating narrative A/B test: {config.test_name}")

        # Validate template configurations
        self._validate_test_config(config)

        # Store test configuration
        self.active_tests[config.test_name] = config
        self.test_data[config.test_name] = {
            'control': [],
            'variant': []
        }

        logger.info(f"Narrative A/B test {config.test_name} created successfully")
        return config.test_name

    def _validate_test_config(self, config: NarrativeTestConfig) -> None:
        """Validate test configuration."""
        # Check template existence
        if not self._template_exists(config.control_template):
            raise ValueError(f"Control template {config.control_template} not found")

        if not self._template_exists(config.variant_template):
            raise ValueError(f"Variant template {config.variant_template} not found")

        # Validate metrics
        valid_metrics = [
            'quality_score', 'readability_score', 'coherence_score',
            'user_engagement', 'click_through_rate', 'time_spent',
            'user_satisfaction', 'conversion_rate'
        ]

        for metric in config.success_metrics:
            if metric not in valid_metrics:
                logger.warning(f"Unknown metric: {metric}")

    def _template_exists(self, template_name: str) -> bool:
        """Check if template exists."""
        try:
            # Check if template is in available templates
            available_templates = narrative_service.template_engine.list_available_templates()
            return template_name in available_templates
        except Exception:
            return True  # Assume exists if check fails

    async def assign_and_generate(
        self,
        test_name: str,
        user_id: str,
        prospect_data: Dict[str, Any],
        prediction_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assign user to variant and generate narrative.

        Args:
            test_name: Name of the narrative test
            user_id: User identifier
            prospect_data: Prospect information
            prediction_data: ML prediction results
            user_preferences: User personalization data
            request_context: Additional context

        Returns:
            Dictionary with variant assignment and generated narrative
        """
        if test_name not in self.active_tests:
            raise ValueError(f"Test {test_name} not found")

        config = self.active_tests[test_name]

        # Assign variant using traffic splitter
        splitter = TrafficSplitter(
            ABTestConfig(
                test_name=config.test_name,
                description=config.description,
                champion_model="control",
                challenger_model="variant",
                traffic_split_ratio=config.traffic_split_ratio,
                split_strategy=config.split_strategy,
                minimum_sample_size=config.minimum_sample_size,
                minimum_test_duration_days=7,
                maximum_test_duration_days=30,
                significance_level=0.05,
                power=0.8,
                early_stopping_enabled=False,
                success_metrics=config.success_metrics,
                guardrail_metrics={}
            )
        )

        variant = splitter.assign_variant(user_id, request_context or {})
        variant_name = "variant" if variant == "challenger" else "control"

        # Select template and configuration
        template_name = config.variant_template if variant_name == "variant" else config.control_template
        template_config = config.variant_config if variant_name == "variant" else config.control_config

        try:
            # Generate narrative using appropriate template
            narrative = await self._generate_narrative_with_template(
                template_name=template_name,
                prospect_data=prospect_data,
                prediction_data=prediction_data,
                user_preferences=user_preferences,
                template_config=template_config
            )

            # Assess narrative quality
            quality_metrics = narrative_quality_service.assess_narrative_quality(narrative)

            # Record test interaction
            interaction_data = {
                'user_id': user_id,
                'timestamp': datetime.now().isoformat(),
                'template_name': template_name,
                'template_config': template_config,
                'narrative': narrative,
                'quality_metrics': asdict(quality_metrics),
                'prospect_id': prospect_data.get('id'),
                'user_preferences': user_preferences,
                'request_context': request_context
            }

            self.test_data[test_name][variant_name].append(interaction_data)

            return {
                'test_name': test_name,
                'user_id': user_id,
                'variant': variant_name,
                'template_name': template_name,
                'narrative': narrative,
                'quality_score': quality_metrics.quality_score,
                'readability_score': quality_metrics.readability_score,
                'timestamp': interaction_data['timestamp']
            }

        except Exception as e:
            logger.error(f"Narrative generation failed for test {test_name}, variant {variant_name}: {e}")
            raise

    async def _generate_narrative_with_template(
        self,
        template_name: str,
        prospect_data: Dict[str, Any],
        prediction_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]],
        template_config: Dict[str, Any]
    ) -> str:
        """
        Generate narrative using specified template and configuration.

        Args:
            template_name: Template to use
            prospect_data: Prospect information
            prediction_data: ML prediction results
            user_preferences: User personalization
            template_config: Template-specific configuration

        Returns:
            Generated narrative text
        """
        # Create mock prospect and prediction objects for service
        from unittest.mock import Mock

        prospect = Mock()
        for key, value in prospect_data.items():
            setattr(prospect, key, value)

        prediction = Mock()
        for key, value in prediction_data.items():
            setattr(prediction, key, value)

        # Apply template config overrides
        modified_preferences = (user_preferences or {}).copy()
        modified_preferences.update(template_config.get('personalization_overrides', {}))

        # Generate narrative
        narrative = await narrative_service.generate_prospect_outlook(
            prospect=prospect,
            prediction_data=prediction,
            user_preferences=modified_preferences
        )

        return narrative

    def record_engagement_metrics(
        self,
        test_name: str,
        user_id: str,
        variant: str,
        engagement_data: Dict[str, Any]
    ) -> None:
        """
        Record user engagement metrics for a narrative.

        Args:
            test_name: Name of the test
            user_id: User identifier
            variant: Assigned variant
            engagement_data: Engagement metrics (clicks, time, etc.)
        """
        if test_name not in self.test_data:
            raise ValueError(f"Test {test_name} not found")

        # Find the corresponding interaction
        interactions = self.test_data[test_name][variant]
        for interaction in reversed(interactions):  # Search from most recent
            if interaction['user_id'] == user_id:
                # Update with engagement data
                interaction.update({
                    'engagement_recorded_at': datetime.now().isoformat(),
                    **engagement_data
                })
                logger.debug(f"Recorded engagement for test {test_name}, user {user_id}")
                break
        else:
            logger.warning(f"No interaction found for user {user_id} in test {test_name}")

    def analyze_narrative_test(self, test_name: str) -> NarrativeTestResult:
        """
        Analyze narrative A/B test results.

        Args:
            test_name: Name of the test

        Returns:
            NarrativeTestResult with comprehensive analysis
        """
        if test_name not in self.active_tests:
            raise ValueError(f"Test {test_name} not found")

        config = self.active_tests[test_name]
        control_data = self.test_data[test_name]['control']
        variant_data = self.test_data[test_name]['variant']

        logger.info(f"Analyzing narrative A/B test {test_name}")

        # Calculate aggregate metrics
        control_metrics = self._calculate_narrative_metrics(control_data, config.success_metrics)
        variant_metrics = self._calculate_narrative_metrics(variant_data, config.success_metrics)

        # Perform quality analysis
        quality_analysis = self._analyze_quality_differences(control_data, variant_data)

        # Perform engagement analysis
        engagement_analysis = self._analyze_engagement_differences(control_data, variant_data)

        # Determine statistical significance
        statistical_significance, confidence_level = self._calculate_significance(
            control_metrics, variant_metrics, len(control_data), len(variant_data)
        )

        # Generate recommendation
        recommendation, winner = self._generate_narrative_recommendation(
            control_metrics, variant_metrics, quality_analysis,
            engagement_analysis, statistical_significance, config
        )

        # Create result
        result = NarrativeTestResult(
            test_name=test_name,
            test_type=config.test_type.value,
            start_time=datetime.now().isoformat(),  # Should track actual start
            end_time=None,
            total_requests=len(control_data) + len(variant_data),
            control_requests=len(control_data),
            variant_requests=len(variant_data),
            control_metrics=control_metrics,
            variant_metrics=variant_metrics,
            quality_analysis=quality_analysis,
            engagement_analysis=engagement_analysis,
            statistical_significance=statistical_significance,
            confidence_level=confidence_level,
            recommendation=recommendation,
            winner=winner
        )

        self.test_results[test_name] = result
        return result

    def _calculate_narrative_metrics(
        self,
        data: List[Dict[str, Any]],
        success_metrics: List[str]
    ) -> Dict[str, float]:
        """Calculate aggregate metrics for narrative data."""
        if not data:
            return {metric: 0.0 for metric in success_metrics}

        metrics = {}

        for metric in success_metrics:
            values = []

            for interaction in data:
                if metric == 'quality_score':
                    quality_data = interaction.get('quality_metrics', {})
                    values.append(quality_data.get('quality_score', 0.0))
                elif metric == 'readability_score':
                    quality_data = interaction.get('quality_metrics', {})
                    values.append(quality_data.get('readability_score', 0.0))
                elif metric == 'coherence_score':
                    quality_data = interaction.get('quality_metrics', {})
                    values.append(quality_data.get('coherence_score', 0.0))
                elif metric in interaction:
                    values.append(float(interaction[metric]))
                else:
                    values.append(0.0)

            metrics[metric] = sum(values) / len(values) if values else 0.0

        return metrics

    def _analyze_quality_differences(
        self,
        control_data: List[Dict[str, Any]],
        variant_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze quality differences between variants."""
        control_quality = [
            item.get('quality_metrics', {}) for item in control_data
        ]
        variant_quality = [
            item.get('quality_metrics', {}) for item in variant_data
        ]

        # Calculate average quality scores
        control_avg_quality = sum(
            q.get('quality_score', 0) for q in control_quality
        ) / len(control_quality) if control_quality else 0

        variant_avg_quality = sum(
            q.get('quality_score', 0) for q in variant_quality
        ) / len(variant_quality) if variant_quality else 0

        # Calculate readability differences
        control_avg_readability = sum(
            q.get('readability_score', 0) for q in control_quality
        ) / len(control_quality) if control_quality else 0

        variant_avg_readability = sum(
            q.get('readability_score', 0) for q in variant_quality
        ) / len(variant_quality) if variant_quality else 0

        return {
            'control_avg_quality': control_avg_quality,
            'variant_avg_quality': variant_avg_quality,
            'quality_improvement': variant_avg_quality - control_avg_quality,
            'quality_improvement_pct': (
                (variant_avg_quality - control_avg_quality) / control_avg_quality * 100
                if control_avg_quality > 0 else 0
            ),
            'control_avg_readability': control_avg_readability,
            'variant_avg_readability': variant_avg_readability,
            'readability_improvement': variant_avg_readability - control_avg_readability
        }

    def _analyze_engagement_differences(
        self,
        control_data: List[Dict[str, Any]],
        variant_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze engagement differences between variants."""
        # Extract engagement metrics
        engagement_metrics = ['click_through_rate', 'time_spent', 'user_satisfaction']

        analysis = {}
        for metric in engagement_metrics:
            control_values = [item.get(metric, 0) for item in control_data if metric in item]
            variant_values = [item.get(metric, 0) for item in variant_data if metric in item]

            control_avg = sum(control_values) / len(control_values) if control_values else 0
            variant_avg = sum(variant_values) / len(variant_values) if variant_values else 0

            analysis[f'control_{metric}'] = control_avg
            analysis[f'variant_{metric}'] = variant_avg
            analysis[f'{metric}_improvement'] = variant_avg - control_avg

        return analysis

    def _calculate_significance(
        self,
        control_metrics: Dict[str, float],
        variant_metrics: Dict[str, float],
        control_sample_size: int,
        variant_sample_size: int
    ) -> Tuple[bool, float]:
        """Calculate statistical significance of differences."""
        # Simple significance test based on sample size and effect size
        min_sample_size = 100  # Minimum for significance
        min_effect_size = 0.05  # 5% improvement threshold

        if control_sample_size < min_sample_size or variant_sample_size < min_sample_size:
            return False, 0.0

        # Check for meaningful improvements in key metrics
        significant_improvements = 0
        total_metrics = 0

        for metric in control_metrics:
            if metric in variant_metrics:
                control_value = control_metrics[metric]
                variant_value = variant_metrics[metric]

                if control_value > 0:
                    improvement = (variant_value - control_value) / control_value
                    if abs(improvement) >= min_effect_size:
                        significant_improvements += 1
                total_metrics += 1

        if total_metrics == 0:
            return False, 0.0

        significance_ratio = significant_improvements / total_metrics
        confidence_level = min(0.95, 0.5 + significance_ratio * 0.45)

        is_significant = significance_ratio >= 0.5 and confidence_level >= 0.8

        return is_significant, confidence_level

    def _generate_narrative_recommendation(
        self,
        control_metrics: Dict[str, float],
        variant_metrics: Dict[str, float],
        quality_analysis: Dict[str, Any],
        engagement_analysis: Dict[str, Any],
        statistical_significance: bool,
        config: NarrativeTestConfig
    ) -> Tuple[str, Optional[str]]:
        """Generate recommendation for narrative test."""

        # Check sample size
        total_samples = len(self.test_data[config.test_name]['control']) + \
                       len(self.test_data[config.test_name]['variant'])

        if total_samples < config.minimum_sample_size:
            return "Continue test - Insufficient sample size", None

        # Check quality thresholds
        variant_quality = quality_analysis.get('variant_avg_quality', 0)
        quality_threshold = config.quality_thresholds.get('minimum_quality', 60.0)

        if variant_quality < quality_threshold:
            return "Stop test - Variant quality below threshold", "control"

        # Check for statistical significance
        if not statistical_significance:
            return "Continue test - No significant difference detected", None

        # Determine winner based on improvements
        quality_improvement = quality_analysis.get('quality_improvement', 0)
        engagement_improvements = sum(
            engagement_analysis.get(f'{metric}_improvement', 0)
            for metric in ['click_through_rate', 'time_spent', 'user_satisfaction']
        )

        if quality_improvement > 0 and engagement_improvements > 0:
            return "Promote variant - Significant improvements in quality and engagement", "variant"
        elif quality_improvement > 5:  # 5 point quality improvement
            return "Promote variant - Significant quality improvement", "variant"
        elif engagement_improvements > 0:
            return "Consider variant - Improved engagement with stable quality", "variant"
        else:
            return "Promote control - No clear improvement in variant", "control"

    def get_test_status(self, test_name: str) -> Dict[str, Any]:
        """Get current status of a narrative test."""
        if test_name not in self.active_tests:
            return {'error': f'Test {test_name} not found'}

        config = self.active_tests[test_name]
        control_samples = len(self.test_data[test_name]['control'])
        variant_samples = len(self.test_data[test_name]['variant'])

        return {
            'test_name': test_name,
            'test_type': config.test_type.value,
            'status': 'running',
            'control_template': config.control_template,
            'variant_template': config.variant_template,
            'traffic_split_ratio': config.traffic_split_ratio,
            'control_samples': control_samples,
            'variant_samples': variant_samples,
            'total_samples': control_samples + variant_samples,
            'minimum_sample_size': config.minimum_sample_size,
            'sample_size_progress': (control_samples + variant_samples) / config.minimum_sample_size,
            'success_metrics': config.success_metrics
        }

    def stop_narrative_test(self, test_name: str, reason: str = "Manual stop") -> NarrativeTestResult:
        """
        Stop a narrative A/B test and finalize results.

        Args:
            test_name: Name of the test to stop
            reason: Reason for stopping

        Returns:
            Final test result
        """
        if test_name not in self.active_tests:
            raise ValueError(f"Test {test_name} not found")

        # Perform final analysis
        result = self.analyze_narrative_test(test_name)
        result.end_time = datetime.now().isoformat()

        # Remove from active tests
        del self.active_tests[test_name]

        # Clear cache if variant wins to deploy new template
        if result.winner == "variant":
            config = self.active_tests.get(test_name)
            if config:
                asyncio.create_task(
                    cache_manager.invalidate_template_caches("v1.0")
                )

        logger.info(f"Narrative A/B test {test_name} stopped. Reason: {reason}")
        return result

    def export_narrative_test_results(self, test_name: str, filepath: str) -> None:
        """Export narrative test results to JSON file."""
        if test_name not in self.test_results:
            raise ValueError(f"No results found for test {test_name}")

        result = self.test_results[test_name]
        export_data = {
            'result': asdict(result),
            'control_data': self.test_data[test_name]['control'],
            'variant_data': self.test_data[test_name]['variant'],
            'export_timestamp': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Narrative test results exported to {filepath}")


# Singleton instance for application use
narrative_ab_test_manager = NarrativeABTestManager()