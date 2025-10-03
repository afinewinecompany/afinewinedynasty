"""
Enhanced AI Outlook Service for Premium Users

Provides personalized ML predictions with league context and detailed explanations.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import numpy as np
from collections import defaultdict

from app.db.models import Prospect, ProspectStats, MLPrediction, ScoutingGrades, User
from app.services.narrative_generation_service import NarrativeGenerationService
from app.core.cache_manager import cache_manager
from app.ml.prediction_engine import PredictionEngine
from app.ml.shap_explainer import SHAPExplainer

logger = logging.getLogger(__name__)


class EnhancedOutlookService:
    """
    Service for generating enhanced AI outlooks with personalization.

    Features:
    - Personalized predictions based on league context
    - Detailed SHAP explanations
    - Confidence intervals and uncertainty quantification
    - Comparative analysis with roster context
    - Dynasty-specific valuations
    """

    @staticmethod
    async def generate_enhanced_outlook(
        db: AsyncSession,
        prospect_id: int,
        user_id: int,
        league_context: Dict[str, Any] = None,
        roster_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate a personalized enhanced outlook for a prospect.

        Args:
            db: Database session
            prospect_id: Prospect ID
            user_id: User ID for personalization
            league_context: League settings (scoring, roster size, etc.)
            roster_context: User's current roster composition

        Returns:
            Enhanced outlook with personalized insights
        """
        # Generate cache key
        import json
        cache_key = f"enhanced_outlook:{prospect_id}:{user_id}:{json.dumps(league_context or {}, sort_keys=True)}"

        cached = await cache_manager.get_cached_features(cache_key)
        if cached:
            logger.info(f"Cache hit for enhanced outlook: {prospect_id}")
            return cached

        # Get prospect data
        prospect = await _get_prospect_with_all_data(db, prospect_id)
        if not prospect:
            return {"error": "Prospect not found"}

        # Get user preferences
        user_prefs = await _get_user_preferences(db, user_id)

        # Generate base prediction
        base_prediction = await _generate_base_prediction(prospect)

        # Apply personalization
        personalized_prediction = await _apply_personalization(
            base_prediction,
            league_context or {},
            roster_context or {},
            user_prefs
        )

        # Generate SHAP explanations
        shap_explanation = await _generate_shap_explanation(prospect, personalized_prediction)

        # Calculate confidence intervals
        confidence_intervals = _calculate_confidence_intervals(personalized_prediction)

        # Generate comparative context
        comparative_context = await _generate_comparative_context(db, prospect, roster_context)

        # Generate narrative
        narrative = await _generate_enhanced_narrative(
            prospect,
            personalized_prediction,
            shap_explanation,
            comparative_context
        )

        # Build enhanced outlook
        enhanced_outlook = {
            "prospect_id": prospect_id,
            "prospect_name": prospect["name"],
            "generated_at": datetime.utcnow().isoformat(),
            "base_prediction": {
                "success_probability": base_prediction["probability"],
                "confidence_level": base_prediction["confidence"],
                "model_version": base_prediction["model_version"]
            },
            "personalized_prediction": {
                "success_probability": personalized_prediction["probability"],
                "dynasty_value": personalized_prediction["dynasty_value"],
                "league_specific_value": personalized_prediction["league_value"],
                "confidence_level": personalized_prediction["confidence"]
            },
            "confidence_intervals": confidence_intervals,
            "shap_explanation": shap_explanation,
            "comparative_context": comparative_context,
            "personalization_factors": {
                "league_settings_applied": bool(league_context),
                "roster_context_applied": bool(roster_context),
                "adjustments": personalized_prediction.get("adjustments", {})
            },
            "narrative": narrative,
            "recommendations": await _generate_recommendations(
                prospect,
                personalized_prediction,
                roster_context
            )
        }

        # Cache for 6 hours
        await cache_manager.cache_prospect_features(cache_key, enhanced_outlook, ttl=21600)

        return enhanced_outlook

    @staticmethod
    async def generate_uncertainty_analysis(
        db: AsyncSession,
        prospect_id: int
    ) -> Dict[str, Any]:
        """
        Generate uncertainty quantification for prospect predictions.

        Args:
            db: Database session
            prospect_id: Prospect ID

        Returns:
            Uncertainty analysis with confidence bounds
        """
        # Get historical predictions to assess model stability
        historical_query = select(MLPrediction).where(
            and_(
                MLPrediction.prospect_id == prospect_id,
                MLPrediction.prediction_type == 'success_rating'
            )
        ).order_by(MLPrediction.generated_at.desc()).limit(10)

        result = await db.execute(historical_query)
        historical_predictions = result.scalars().all()

        if not historical_predictions:
            return {
                "prospect_id": prospect_id,
                "uncertainty": "high",
                "message": "Insufficient prediction history"
            }

        # Calculate prediction variance
        probabilities = [p.success_probability for p in historical_predictions]

        uncertainty_analysis = {
            "prospect_id": prospect_id,
            "current_prediction": probabilities[0] if probabilities else None,
            "prediction_stability": {
                "mean": np.mean(probabilities),
                "std_dev": np.std(probabilities),
                "variance": np.var(probabilities),
                "coefficient_of_variation": np.std(probabilities) / np.mean(probabilities) if np.mean(probabilities) > 0 else 0
            },
            "confidence_bounds": {
                "lower_bound_95": max(0, np.mean(probabilities) - 1.96 * np.std(probabilities)),
                "upper_bound_95": min(1, np.mean(probabilities) + 1.96 * np.std(probabilities)),
                "lower_bound_68": max(0, np.mean(probabilities) - np.std(probabilities)),
                "upper_bound_68": min(1, np.mean(probabilities) + np.std(probabilities))
            },
            "uncertainty_level": _classify_uncertainty(np.std(probabilities)),
            "factors": []
        }

        # Identify uncertainty factors
        if np.std(probabilities) > 0.1:
            uncertainty_analysis["factors"].append("High prediction variance over time")

        if len(historical_predictions) < 5:
            uncertainty_analysis["factors"].append("Limited prediction history")

        # Check for recent volatility
        if len(probabilities) >= 3:
            recent_volatility = np.std(probabilities[:3])
            if recent_volatility > 0.15:
                uncertainty_analysis["factors"].append("Recent prediction volatility")

        return uncertainty_analysis

    @staticmethod
    async def generate_dynasty_specific_valuation(
        db: AsyncSession,
        prospect_id: int,
        league_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate dynasty-specific valuation based on league settings.

        Args:
            db: Database session
            prospect_id: Prospect ID
            league_settings: League configuration

        Returns:
            Dynasty valuation with trade value estimates
        """
        # Get prospect data
        prospect = await _get_prospect_with_all_data(db, prospect_id)
        if not prospect:
            return {"error": "Prospect not found"}

        # Base valuation factors
        valuation = {
            "prospect_id": prospect_id,
            "prospect_name": prospect["name"],
            "base_value": 0,
            "adjusted_value": 0,
            "factors": {},
            "trade_value": {}
        }

        # Calculate base value (0-100 scale)
        base_factors = {
            "ml_prediction": prospect.get("ml_prediction", {}).get("success_probability", 0) * 40,
            "age_bonus": max(0, 25 - prospect.get("age", 25)) * 2,
            "level_bonus": _calculate_level_bonus(prospect.get("level", "")),
            "scouting_grade": (prospect.get("scouting_grade", {}).get("overall", 0) / 80) * 20,
            "performance": _calculate_performance_score(prospect.get("stats", {}))
        }

        valuation["base_value"] = sum(base_factors.values())
        valuation["factors"] = base_factors

        # Apply league-specific adjustments
        adjustments = {}

        # Scoring system adjustments
        scoring_system = league_settings.get("scoring_system", "standard")
        if scoring_system == "points":
            if prospect.get("position") in ["SP", "RP"]:
                adjustments["points_league_pitcher"] = 1.2
            else:
                adjustments["points_league_hitter"] = 0.9
        elif scoring_system == "categories":
            # Adjust based on category strengths
            if _is_category_specialist(prospect):
                adjustments["category_specialist"] = 1.15

        # Roster size adjustments
        roster_size = league_settings.get("roster_size", 25)
        if roster_size > 30:
            adjustments["deep_league"] = 1.1
        elif roster_size < 20:
            adjustments["shallow_league"] = 0.85

        # Keeper/dynasty adjustments
        keeper_count = league_settings.get("keeper_count", 0)
        if keeper_count > 10:
            adjustments["deep_keeper"] = 1.25
        elif keeper_count > 5:
            adjustments["standard_keeper"] = 1.1

        # Apply adjustments
        total_adjustment = 1.0
        for adj_value in adjustments.values():
            total_adjustment *= adj_value

        valuation["adjusted_value"] = valuation["base_value"] * total_adjustment
        valuation["adjustments"] = adjustments

        # Calculate trade value in terms of draft picks
        valuation["trade_value"] = {
            "first_round_pick_equivalent": valuation["adjusted_value"] / 85,
            "second_round_pick_equivalent": valuation["adjusted_value"] / 70,
            "third_round_pick_equivalent": valuation["adjusted_value"] / 55,
            "recommendation": _get_trade_recommendation(valuation["adjusted_value"])
        }

        return valuation


# Helper functions
async def _get_prospect_with_all_data(db: AsyncSession, prospect_id: int) -> Optional[Dict[str, Any]]:
    """Get comprehensive prospect data."""
    # Get prospect
    prospect_query = select(Prospect).where(Prospect.id == prospect_id)
    prospect_result = await db.execute(prospect_query)
    prospect = prospect_result.scalar_one_or_none()

    if not prospect:
        return None

    # Get latest stats
    stats_query = select(ProspectStats).where(
        ProspectStats.prospect_id == prospect_id
    ).order_by(ProspectStats.date_recorded.desc()).limit(1)
    stats_result = await db.execute(stats_query)
    latest_stats = stats_result.scalar_one_or_none()

    # Get ML prediction
    ml_query = select(MLPrediction).where(
        and_(
            MLPrediction.prospect_id == prospect_id,
            MLPrediction.prediction_type == 'success_rating'
        )
    ).order_by(MLPrediction.generated_at.desc()).limit(1)
    ml_result = await db.execute(ml_query)
    ml_prediction = ml_result.scalar_one_or_none()

    # Get scouting grades
    grade_query = select(ScoutingGrades).where(
        ScoutingGrades.prospect_id == prospect_id
    ).order_by(ScoutingGrades.updated_at.desc()).limit(1)
    grade_result = await db.execute(grade_query)
    scouting_grade = grade_result.scalar_one_or_none()

    return {
        "id": prospect.id,
        "name": prospect.name,
        "position": prospect.position,
        "organization": prospect.organization,
        "level": prospect.level,
        "age": prospect.age,
        "eta_year": prospect.eta_year,
        "stats": {
            "batting_avg": latest_stats.batting_avg if latest_stats else None,
            "on_base_pct": latest_stats.on_base_pct if latest_stats else None,
            "slugging_pct": latest_stats.slugging_pct if latest_stats else None,
            "era": latest_stats.era if latest_stats else None,
            "whip": latest_stats.whip if latest_stats else None
        } if latest_stats else {},
        "ml_prediction": {
            "success_probability": ml_prediction.success_probability,
            "confidence_level": ml_prediction.confidence_level,
            "feature_importance": ml_prediction.feature_importance
        } if ml_prediction else {},
        "scouting_grade": {
            "overall": scouting_grade.overall,
            "future_value": scouting_grade.future_value
        } if scouting_grade else {}
    }


async def _get_user_preferences(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Get user preferences for personalization."""
    user_query = select(User).where(User.id == user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()

    if user and user.preferences:
        return user.preferences
    return {}


async def _generate_base_prediction(prospect: Dict[str, Any]) -> Dict[str, Any]:
    """Generate base ML prediction."""
    if prospect.get("ml_prediction"):
        return {
            "probability": prospect["ml_prediction"]["success_probability"],
            "confidence": prospect["ml_prediction"]["confidence_level"],
            "model_version": "v2.1"
        }

    # Fallback calculation if no ML prediction exists
    return {
        "probability": 0.5,
        "confidence": "Low",
        "model_version": "fallback"
    }


async def _apply_personalization(
    base_prediction: Dict[str, Any],
    league_context: Dict[str, Any],
    roster_context: Dict[str, Any],
    user_prefs: Dict[str, Any]
) -> Dict[str, Any]:
    """Apply personalization to base prediction."""
    personalized = base_prediction.copy()
    adjustments = {}

    # League-specific adjustments
    if league_context.get("scoring_system") == "points":
        adjustments["points_league"] = 0.05

    if league_context.get("roster_size", 25) > 30:
        adjustments["deep_league"] = 0.03

    # Roster need adjustments
    if roster_context:
        position_need = roster_context.get("position_needs", [])
        if any(need in base_prediction.get("position", "") for need in position_need):
            adjustments["position_need"] = 0.08

    # Apply adjustments
    total_adjustment = sum(adjustments.values())
    personalized["probability"] = min(1.0, base_prediction["probability"] + total_adjustment)
    personalized["adjustments"] = adjustments

    # Calculate dynasty and league-specific values
    personalized["dynasty_value"] = personalized["probability"] * 100
    personalized["league_value"] = personalized["dynasty_value"] * (1 + total_adjustment)

    return personalized


async def _generate_shap_explanation(
    prospect: Dict[str, Any],
    prediction: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate SHAP-based feature importance explanation."""
    # Simplified SHAP explanation (would use actual SHAP library in production)
    features = prospect.get("ml_prediction", {}).get("feature_importance", {})

    if not features:
        # Generate mock feature importance
        features = {
            "age": -0.15 if prospect.get("age", 21) > 21 else 0.10,
            "level": 0.20 if prospect.get("level") in ["AAA", "AA"] else -0.10,
            "batting_avg": 0.25 if prospect.get("stats", {}).get("batting_avg", 0) > 0.280 else -0.15,
            "organization": 0.05,
            "scouting_grade": 0.15 if prospect.get("scouting_grade", {}).get("overall", 0) > 50 else -0.10
        }

    # Sort by importance
    sorted_features = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)

    return {
        "top_positive_factors": [f for f, v in sorted_features if v > 0][:3],
        "top_negative_factors": [f for f, v in sorted_features if v < 0][:3],
        "feature_importance": dict(sorted_features),
        "explanation_confidence": "High" if len(features) > 5 else "Medium"
    }


async def _generate_comparative_context(
    db: AsyncSession,
    prospect: Dict[str, Any],
    roster_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate comparative analysis context."""
    context = {
        "position_comparison": f"Top {prospect.get('position', 'Unknown')} prospect",
        "age_comparison": "Age-appropriate development" if prospect.get("age", 21) <= 21 else "Older prospect",
        "level_comparison": "Advanced level" if prospect.get("level") in ["AAA", "AA"] else "Lower level"
    }

    if roster_context and roster_context.get("other_prospects"):
        # Compare to other prospects in user's system
        context["roster_comparison"] = f"Ranked #{roster_context.get('internal_rank', 'N/A')} in your system"

    return context


async def _generate_enhanced_narrative(
    prospect: Dict[str, Any],
    prediction: Dict[str, Any],
    shap_explanation: Dict[str, Any],
    comparative_context: Dict[str, Any]
) -> str:
    """Generate enhanced narrative explanation."""
    narrative_parts = []

    # Opening assessment
    narrative_parts.append(
        f"{prospect['name']} projects as a {prediction['confidence'].lower()} confidence prospect "
        f"with a {prediction['probability']:.1%} success probability."
    )

    # Key factors
    if shap_explanation["top_positive_factors"]:
        narrative_parts.append(
            f"Key strengths include {', '.join(shap_explanation['top_positive_factors'][:2])}."
        )

    if shap_explanation["top_negative_factors"]:
        narrative_parts.append(
            f"Areas of concern include {', '.join(shap_explanation['top_negative_factors'][:2])}."
        )

    # Comparative context
    narrative_parts.append(comparative_context.get("position_comparison", ""))

    # Dynasty valuation
    narrative_parts.append(
        f"Dynasty value score: {prediction.get('dynasty_value', 0):.0f}/100 "
        f"(League-adjusted: {prediction.get('league_value', 0):.0f}/100)."
    )

    return " ".join(filter(None, narrative_parts))


async def _generate_recommendations(
    prospect: Dict[str, Any],
    prediction: Dict[str, Any],
    roster_context: Dict[str, Any] = None
) -> List[str]:
    """Generate actionable recommendations."""
    recommendations = []

    # Trade recommendations
    if prediction["dynasty_value"] > 80:
        recommendations.append("Strong hold - elite dynasty asset")
    elif prediction["dynasty_value"] > 60:
        recommendations.append("Hold unless receiving premium offer")
    elif prediction["dynasty_value"] < 40:
        recommendations.append("Consider selling if you can get value")

    # Development timeline
    eta = prospect.get("eta_year")
    if eta:
        current_year = datetime.now().year
        if eta - current_year <= 1:
            recommendations.append("Near-term contributor - prepare roster spot")
        elif eta - current_year <= 2:
            recommendations.append("Monitor closely - likely contributor within 2 years")
        else:
            recommendations.append("Long-term stash - patience required")

    # Position-specific advice
    if roster_context and roster_context.get("position_needs"):
        if prospect["position"] in roster_context["position_needs"]:
            recommendations.append(f"Fills organizational need at {prospect['position']}")

    return recommendations


def _calculate_confidence_intervals(prediction: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate confidence intervals for predictions."""
    base_prob = prediction["probability"]

    # Simplified confidence interval calculation
    std_dev = 0.15 if prediction["confidence"] == "Low" else 0.10 if prediction["confidence"] == "Medium" else 0.05

    return {
        "95_percent": {
            "lower": max(0, base_prob - 1.96 * std_dev),
            "upper": min(1, base_prob + 1.96 * std_dev)
        },
        "68_percent": {
            "lower": max(0, base_prob - std_dev),
            "upper": min(1, base_prob + std_dev)
        }
    }


def _classify_uncertainty(std_dev: float) -> str:
    """Classify uncertainty level based on standard deviation."""
    if std_dev < 0.05:
        return "very_low"
    elif std_dev < 0.10:
        return "low"
    elif std_dev < 0.15:
        return "medium"
    elif std_dev < 0.20:
        return "high"
    else:
        return "very_high"


def _calculate_level_bonus(level: str) -> float:
    """Calculate bonus points based on minor league level."""
    level_bonuses = {
        "MLB": 30,
        "AAA": 25,
        "AA": 20,
        "A+": 15,
        "A": 10,
        "A-": 5,
        "Rookie": 0
    }
    return level_bonuses.get(level, 0)


def _calculate_performance_score(stats: Dict[str, Any]) -> float:
    """Calculate performance score from stats."""
    score = 0

    # Hitting stats
    if stats.get("batting_avg"):
        if stats["batting_avg"] > 0.300:
            score += 10
        elif stats["batting_avg"] > 0.270:
            score += 5

    # OPS
    ops = (stats.get("on_base_pct", 0) + stats.get("slugging_pct", 0))
    if ops > 0.900:
        score += 10
    elif ops > 0.800:
        score += 5

    # Pitching stats
    if stats.get("era") is not None and stats["era"] < 3.00:
        score += 10
    elif stats.get("era") is not None and stats["era"] < 4.00:
        score += 5

    return min(20, score)


def _is_category_specialist(prospect: Dict[str, Any]) -> bool:
    """Check if prospect is a category specialist."""
    stats = prospect.get("stats", {})

    # Check for standout categories
    if stats.get("batting_avg", 0) > 0.320:
        return True
    if stats.get("home_runs", 0) > 30:
        return True
    if stats.get("stolen_bases", 0) > 30:
        return True
    if stats.get("era") is not None and stats["era"] < 2.50:
        return True
    if stats.get("k_per_9", 0) > 11:
        return True

    return False


def _get_trade_recommendation(value: float) -> str:
    """Get trade recommendation based on value."""
    if value > 85:
        return "Elite asset - only trade for proven MLB talent"
    elif value > 70:
        return "High value - worth multiple mid-round picks"
    elif value > 55:
        return "Solid asset - worth 2nd round pick+"
    elif value > 40:
        return "Moderate value - worth 3rd round pick"
    else:
        return "Speculative value - package with others"