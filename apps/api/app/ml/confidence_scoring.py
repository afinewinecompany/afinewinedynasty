"""Confidence Scoring Algorithm for ML Predictions

Implements confidence level calculation based on prediction probability,
SHAP values, and feature quality to classify predictions as High/Medium/Low confidence.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass

from ..schemas.ml_predictions import ConfidenceLevel

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceThresholds:
    """Configurable thresholds for confidence scoring."""

    # Probability-based thresholds
    high_prob_min: float = 0.75    # High confidence requires >75% or <25% probability
    high_prob_max: float = 0.25
    medium_prob_min: float = 0.65  # Medium confidence for 65-75% or 25-35%
    medium_prob_max: float = 0.35

    # SHAP-based thresholds
    high_shap_consistency: float = 0.8   # 80% of top features align with prediction
    medium_shap_consistency: float = 0.6 # 60% alignment for medium confidence

    # Feature quality thresholds
    high_data_completeness: float = 0.9   # 90% of features have valid data
    medium_data_completeness: float = 0.7 # 70% for medium confidence

    # Prediction stability thresholds
    high_stability_threshold: float = 0.05  # <5% variance in ensemble predictions
    medium_stability_threshold: float = 0.15 # <15% for medium confidence


class ConfidenceScorer:
    """
    Calculate confidence levels for ML predictions based on multiple factors:
    1. Prediction probability extremeness
    2. SHAP value consistency
    3. Feature data quality
    4. Prediction stability
    """

    def __init__(self, thresholds: Optional[ConfidenceThresholds] = None):
        self.thresholds = thresholds or ConfidenceThresholds()
        self._confidence_weights = {
            "probability": 0.4,
            "shap_consistency": 0.3,
            "data_quality": 0.2,
            "stability": 0.1
        }

    async def calculate_confidence(
        self,
        prediction_probability: float,
        shap_values: Optional[List[float]] = None,
        features: Optional[Dict[str, Any]] = None,
        ensemble_predictions: Optional[List[float]] = None
    ) -> ConfidenceLevel:
        """
        Calculate overall confidence level for a prediction.

        Args:
            prediction_probability: Model prediction probability (0.0 to 1.0)
            shap_values: SHAP importance values for features
            features: Input features used for prediction
            ensemble_predictions: Multiple predictions for stability assessment

        Returns:
            ConfidenceLevel: HIGH, MEDIUM, or LOW confidence classification
        """
        try:
            # Calculate individual confidence components
            prob_confidence = self._calculate_probability_confidence(prediction_probability)
            shap_confidence = self._calculate_shap_confidence(prediction_probability, shap_values)
            data_confidence = self._calculate_data_quality_confidence(features)
            stability_confidence = self._calculate_stability_confidence(ensemble_predictions)

            # Weighted confidence score
            confidence_score = (
                self._confidence_weights["probability"] * prob_confidence +
                self._confidence_weights["shap_consistency"] * shap_confidence +
                self._confidence_weights["data_quality"] * data_confidence +
                self._confidence_weights["stability"] * stability_confidence
            )

            # Classify into High/Medium/Low
            if confidence_score >= 0.8:
                return ConfidenceLevel.HIGH
            elif confidence_score >= 0.5:
                return ConfidenceLevel.MEDIUM
            else:
                return ConfidenceLevel.LOW

        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            # Default to LOW confidence on errors
            return ConfidenceLevel.LOW

    def _calculate_probability_confidence(self, probability: float) -> float:
        """
        Calculate confidence based on prediction probability extremeness.

        More extreme probabilities (close to 0 or 1) indicate higher confidence.
        """
        # Distance from 0.5 (maximum uncertainty)
        distance_from_center = abs(probability - 0.5)

        # Normalize to 0-1 scale
        if distance_from_center >= 0.25:  # 75%+ or 25%- probability
            return 1.0  # High confidence
        elif distance_from_center >= 0.15:  # 65%+ or 35%- probability
            return 0.6  # Medium confidence
        else:
            return 0.2  # Low confidence

    def _calculate_shap_confidence(
        self,
        prediction_probability: float,
        shap_values: Optional[List[float]]
    ) -> float:
        """
        Calculate confidence based on SHAP value consistency with prediction.

        Consistent SHAP explanations indicate model confidence in prediction logic.
        """
        if not shap_values or len(shap_values) == 0:
            return 0.5  # Neutral confidence without SHAP data

        try:
            shap_array = np.array(shap_values)

            # Determine if prediction is positive (>50%) or negative
            prediction_positive = prediction_probability > 0.5

            # Calculate SHAP consistency
            positive_shap_sum = np.sum(shap_array[shap_array > 0])
            negative_shap_sum = np.abs(np.sum(shap_array[shap_array < 0]))
            total_shap_magnitude = positive_shap_sum + negative_shap_sum

            if total_shap_magnitude == 0:
                return 0.5  # Neutral when no SHAP signal

            # Consistency ratio
            if prediction_positive:
                consistency_ratio = positive_shap_sum / total_shap_magnitude
            else:
                consistency_ratio = negative_shap_sum / total_shap_magnitude

            # Additional consistency check: top features alignment
            top_features_alignment = self._calculate_top_features_alignment(
                shap_array, prediction_positive
            )

            # Combine consistency measures
            overall_consistency = (consistency_ratio + top_features_alignment) / 2

            return min(overall_consistency, 1.0)

        except Exception as e:
            logger.warning(f"SHAP confidence calculation error: {e}")
            return 0.5

    def _calculate_top_features_alignment(
        self,
        shap_values: np.ndarray,
        prediction_positive: bool
    ) -> float:
        """Calculate alignment of top SHAP features with prediction direction."""

        # Get top 10 most important features by absolute value
        top_indices = np.argsort(np.abs(shap_values))[-10:]
        top_shap_values = shap_values[top_indices]

        if prediction_positive:
            aligned_features = np.sum(top_shap_values > 0)
        else:
            aligned_features = np.sum(top_shap_values < 0)

        return aligned_features / len(top_shap_values)

    def _calculate_data_quality_confidence(
        self,
        features: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate confidence based on input data quality and completeness.

        Higher quality data leads to more confident predictions.
        """
        if not features:
            return 0.3  # Low confidence without feature data

        try:
            # Count valid vs missing/default features
            total_features = len(features)
            valid_features = 0

            for key, value in features.items():
                if self._is_valid_feature_value(key, value):
                    valid_features += 1

            completeness_ratio = valid_features / total_features if total_features > 0 else 0

            # Check for key feature categories
            key_categories = {
                "prospect_info": ["age", "position_encoded", "level_encoded"],
                "performance": ["career_avg", "career_era", "career_pa", "career_ip"],
                "scouting": ["grade_overall", "grade_hit", "grade_fastball"],
                "physical": ["height", "weight", "bmi"]
            }

            category_completeness = []
            for category, required_features in key_categories.items():
                category_valid = sum(
                    1 for feat in required_features
                    if feat in features and self._is_valid_feature_value(feat, features[feat])
                )
                category_ratio = category_valid / len(required_features)
                category_completeness.append(category_ratio)

            # Overall data quality score
            overall_completeness = np.mean(category_completeness) if category_completeness else completeness_ratio

            # Bonus for recent data
            recent_data_bonus = self._calculate_recency_bonus(features)

            return min(overall_completeness + recent_data_bonus, 1.0)

        except Exception as e:
            logger.warning(f"Data quality confidence calculation error: {e}")
            return 0.3

    def _is_valid_feature_value(self, feature_name: str, value: Any) -> bool:
        """Check if a feature value is valid (not missing/default)."""

        # Handle None/null values
        if value is None:
            return False

        # Handle numeric features
        if isinstance(value, (int, float)):
            # Check for obvious default/missing values
            if feature_name.endswith("_encoded") and value == 0:
                return False
            if feature_name.startswith("grade_") and value == 50.0:
                return False  # 50 is default scouting grade
            if feature_name.startswith("career_") and value == 0:
                return False
            return True

        # Handle string features
        if isinstance(value, str):
            return len(value.strip()) > 0

        return True

    def _calculate_recency_bonus(self, features: Dict[str, Any]) -> float:
        """Calculate bonus for recent/fresh data."""

        recency_bonus = 0.0

        # Check for recent scouting grades
        if "grade_age_days" in features:
            days_old = features["grade_age_days"]
            if days_old < 30:  # Very recent
                recency_bonus += 0.1
            elif days_old < 90:  # Fairly recent
                recency_bonus += 0.05

        # Check for recent performance data
        if "games_played" in features and features["games_played"] > 0:
            recency_bonus += 0.05

        return recency_bonus

    def _calculate_stability_confidence(
        self,
        ensemble_predictions: Optional[List[float]]
    ) -> float:
        """
        Calculate confidence based on prediction stability across ensemble models.

        Lower variance in ensemble predictions indicates higher confidence.
        """
        if not ensemble_predictions or len(ensemble_predictions) <= 1:
            return 0.7  # Default medium confidence without ensemble data

        try:
            predictions_array = np.array(ensemble_predictions)
            prediction_variance = np.var(predictions_array)

            # Convert variance to confidence score (lower variance = higher confidence)
            if prediction_variance <= self.thresholds.high_stability_threshold:
                return 1.0
            elif prediction_variance <= self.thresholds.medium_stability_threshold:
                return 0.6
            else:
                return 0.2

        except Exception as e:
            logger.warning(f"Stability confidence calculation error: {e}")
            return 0.7

    def get_confidence_explanation(
        self,
        prediction_probability: float,
        confidence_level: ConfidenceLevel,
        shap_values: Optional[List[float]] = None,
        features: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate human-readable explanation for confidence level.
        """
        explanations = []

        # Probability explanation
        if abs(prediction_probability - 0.5) >= 0.25:
            explanations.append("Strong prediction probability")
        elif abs(prediction_probability - 0.5) >= 0.15:
            explanations.append("Moderate prediction probability")
        else:
            explanations.append("Weak prediction probability")

        # SHAP explanation
        if shap_values:
            shap_confidence = self._calculate_shap_confidence(prediction_probability, shap_values)
            if shap_confidence >= 0.8:
                explanations.append("consistent feature importance")
            elif shap_confidence >= 0.6:
                explanations.append("mostly consistent feature importance")
            else:
                explanations.append("mixed feature importance signals")

        # Data quality explanation
        if features:
            data_confidence = self._calculate_data_quality_confidence(features)
            if data_confidence >= 0.9:
                explanations.append("comprehensive data available")
            elif data_confidence >= 0.7:
                explanations.append("good data quality")
            else:
                explanations.append("limited data available")

        base_explanation = f"{confidence_level.value} confidence prediction based on " + ", ".join(explanations)

        return base_explanation + "."

    def update_thresholds(self, new_thresholds: ConfidenceThresholds):
        """Update confidence scoring thresholds for tuning."""
        self.thresholds = new_thresholds
        logger.info("Confidence scoring thresholds updated")

    def get_confidence_metrics(self) -> Dict[str, Any]:
        """Get current confidence scoring configuration and metrics."""
        return {
            "thresholds": {
                "high_prob_range": f"{self.thresholds.high_prob_max:.2f} - {self.thresholds.high_prob_min:.2f}",
                "medium_prob_range": f"{self.thresholds.medium_prob_max:.2f} - {self.thresholds.medium_prob_min:.2f}",
                "high_shap_consistency": self.thresholds.high_shap_consistency,
                "medium_shap_consistency": self.thresholds.medium_shap_consistency,
                "high_data_completeness": self.thresholds.high_data_completeness,
                "medium_data_completeness": self.thresholds.medium_data_completeness
            },
            "weights": self._confidence_weights
        }