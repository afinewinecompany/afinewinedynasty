"""
Fit Scoring Service

Calculates prospect-team fit scores based on positional needs, timeline alignment,
and organizational requirements for optimal prospect recommendations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Prospect, MLPrediction
import logging

logger = logging.getLogger(__name__)


class FitScoringService:
    """
    Service for calculating prospect-team fit scores

    Evaluates how well prospects match team needs based on position requirements,
    competitive timeline alignment, depth chart impact, and organizational context.

    @class FitScoringService
    @since 4.4.0
    """

    # Fit scoring weights (must sum to 1.0)
    WEIGHTS = {
        "position_need": 0.30,      # Position gap severity
        "timeline_alignment": 0.25,  # ETA vs competitive window
        "depth_impact": 0.20,        # Starter vs depth piece
        "prospect_quality": 0.15,    # ML prediction quality
        "value": 0.10                # Value vs ADP/cost
    }

    def __init__(self, db: AsyncSession):
        """
        Initialize Fit Scoring Service

        @param db - Database session for prospect and ML prediction data

        @since 4.4.0
        """
        self.db = db

    async def calculate_fit_score(
        self,
        prospect: Prospect,
        team_analysis: Dict[str, Any],
        league_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive fit score for prospect-team match

        @param prospect - Prospect to evaluate
        @param team_analysis - Complete team analysis from RosterAnalysisService
        @param league_settings - League configuration and scoring settings

        @returns Fit score breakdown with overall score and component scores

        @performance
        - Response time: 50-100ms per prospect
        - Database query for ML predictions

        @since 4.4.0
        """
        # Get ML prediction for prospect quality
        ml_prediction = await self._get_ml_prediction(prospect.id)

        # Calculate component scores
        position_score = self._calculate_position_need_score(
            prospect,
            team_analysis.get("positional_gap_scores", {}),
            team_analysis.get("weaknesses", [])
        )

        timeline_score = self._calculate_timeline_alignment_score(
            prospect,
            team_analysis.get("competitive_window", {})
        )

        depth_impact_score = self._calculate_depth_impact_score(
            prospect,
            team_analysis.get("position_depth", {}),
            team_analysis.get("positional_gap_scores", {})
        )

        quality_score = self._calculate_quality_score(
            prospect,
            ml_prediction
        )

        value_score = self._calculate_value_score(
            prospect,
            position_score,
            team_analysis.get("weaknesses", [])
        )

        # Calculate weighted overall fit score (0-10 scale)
        overall_score = (
            self.WEIGHTS["position_need"] * position_score +
            self.WEIGHTS["timeline_alignment"] * timeline_score +
            self.WEIGHTS["depth_impact"] * depth_impact_score +
            self.WEIGHTS["prospect_quality"] * quality_score +
            self.WEIGHTS["value"] * value_score
        )

        return {
            "overall_score": round(overall_score, 2),
            "position_fit": round(position_score, 2),
            "timeline_fit": round(timeline_score, 2),
            "depth_impact": round(depth_impact_score, 2),
            "quality_score": round(quality_score, 2),
            "value_score": round(value_score, 2),
            "fit_rating": self._get_fit_rating(overall_score),
            "components": {
                "position_need_weight": self.WEIGHTS["position_need"],
                "timeline_weight": self.WEIGHTS["timeline_alignment"],
                "depth_weight": self.WEIGHTS["depth_impact"],
                "quality_weight": self.WEIGHTS["prospect_quality"],
                "value_weight": self.WEIGHTS["value"]
            }
        }

    def _calculate_position_need_score(
        self,
        prospect: Prospect,
        gap_scores: Dict[str, Dict[str, Any]],
        weaknesses: List[str]
    ) -> float:
        """
        Calculate position need match score

        @param prospect - Prospect to evaluate
        @param gap_scores - Positional gap scores from team analysis
        @param weaknesses - List of weak positions

        @returns Position need score (0-10)

        @since 4.4.0
        """
        prospect_position = prospect.position

        # Get gap score for prospect's position
        position_gap = gap_scores.get(prospect_position, {})
        gap_score = position_gap.get("gap_score", 0)

        # Normalize gap score to 0-10 scale (gap scores are already 0-10)
        position_score = gap_score

        # Bonus if position is in weaknesses list
        if prospect_position in weaknesses:
            position_score = min(10, position_score + 1)

        return position_score

    def _calculate_timeline_alignment_score(
        self,
        prospect: Prospect,
        competitive_window: Dict[str, Any]
    ) -> float:
        """
        Calculate timeline alignment between prospect ETA and team window

        @param prospect - Prospect to evaluate
        @param competitive_window - Team competitive window analysis

        @returns Timeline alignment score (0-10)

        @since 4.4.0
        """
        window_type = competitive_window.get("window", "transitional")
        prospect_eta = prospect.eta_year
        current_year = datetime.now().year
        years_to_eta = prospect_eta - current_year if prospect_eta else 2

        # Perfect alignment scoring
        if window_type == "contending":
            # Contending teams want immediate help (ETA <= 1 year)
            if years_to_eta <= 1:
                return 10
            elif years_to_eta == 2:
                return 6
            else:
                return 3

        elif window_type == "rebuilding":
            # Rebuilding teams want future assets (ETA 2-4 years)
            if 2 <= years_to_eta <= 4:
                return 10
            elif years_to_eta == 1:
                return 7
            else:
                return 4

        elif window_type == "retooling":
            # Retooling teams want 1-3 year timeline
            if 1 <= years_to_eta <= 3:
                return 10
            elif years_to_eta == 4:
                return 6
            else:
                return 4

        else:  # transitional or balanced
            # Balanced approach: 1-3 years preferred
            if 1 <= years_to_eta <= 3:
                return 10
            else:
                return 6

    def _calculate_depth_impact_score(
        self,
        prospect: Prospect,
        position_depth: Dict[str, Any],
        gap_scores: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Calculate expected depth chart impact (starter vs depth piece)

        @param prospect - Prospect to evaluate
        @param position_depth - Position depth analysis
        @param gap_scores - Positional gap scores

        @returns Depth impact score (0-10)

        @since 4.4.0
        """
        prospect_position = prospect.position
        pos_depth = position_depth.get(prospect_position, {})
        current_count = pos_depth.get("active_count", 0)

        # Get gap information
        gap_info = gap_scores.get(prospect_position, {})
        deficit = gap_info.get("deficit", 0)

        # High deficit = likely starter
        if deficit >= 2:
            return 10  # Clear starter opportunity

        # Some deficit = potential starter
        elif deficit == 1:
            return 8

        # No deficit but weak depth = depth piece upgrade
        elif current_count <= 2:
            return 6

        # Already strong depth = less impact
        else:
            return 4

    def _calculate_quality_score(
        self,
        prospect: Prospect,
        ml_prediction: Optional[MLPrediction]
    ) -> float:
        """
        Calculate prospect quality score from overall grade and ML predictions

        @param prospect - Prospect to evaluate
        @param ml_prediction - ML prediction data if available

        @returns Quality score (0-10)

        @since 4.4.0
        """
        # Use ML prediction if available
        if ml_prediction:
            # Convert success probability (0-1) to 0-10 scale
            success_prob = ml_prediction.success_probability
            confidence = ml_prediction.confidence_level

            base_score = success_prob * 10

            # Adjust for confidence
            if confidence == "High":
                return base_score
            elif confidence == "Medium":
                return base_score * 0.9
            else:
                return base_score * 0.8

        # Fallback to overall grade (20-80 scale -> 0-10 scale)
        overall_grade = getattr(prospect, 'overall_grade', 50)
        return (overall_grade - 20) / 6  # Maps 20-80 to 0-10

    def _calculate_value_score(
        self,
        prospect: Prospect,
        position_need_score: float,
        weaknesses: List[str]
    ) -> float:
        """
        Calculate value score (prospect value relative to team need)

        @param prospect - Prospect to evaluate
        @param position_need_score - Already calculated position need score
        @param weaknesses - Team weakness positions

        @returns Value score (0-10)

        @since 4.4.0
        """
        # Value increases when high-quality prospect fills urgent need
        prospect_position = prospect.position

        # Base value on position need
        value_score = position_need_score * 0.7

        # Bonus for filling critical weakness
        if prospect_position in weaknesses:
            value_score += 3

        # Cap at 10
        return min(10, value_score)

    async def _get_ml_prediction(self, prospect_id: int) -> Optional[MLPrediction]:
        """
        Retrieve ML prediction for prospect

        @param prospect_id - Prospect ID

        @returns ML prediction if available

        @since 4.4.0
        """
        stmt = select(MLPrediction).where(
            MLPrediction.prospect_id == prospect_id
        ).order_by(MLPrediction.prediction_date.desc())

        result = await self.db.execute(stmt)
        return result.scalars().first()

    def _get_fit_rating(self, overall_score: float) -> str:
        """
        Convert numeric score to rating label

        @param overall_score - Overall fit score (0-10)

        @returns Fit rating label

        @since 4.4.0
        """
        if overall_score >= 8.5:
            return "excellent"
        elif overall_score >= 7.0:
            return "very_good"
        elif overall_score >= 5.5:
            return "good"
        elif overall_score >= 4.0:
            return "fair"
        else:
            return "poor"

    async def calculate_league_specific_fit(
        self,
        prospect: Prospect,
        team_analysis: Dict[str, Any],
        league_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate fit score with league-specific adjustments

        @param prospect - Prospect to evaluate
        @param team_analysis - Team analysis
        @param league_settings - League scoring and roster settings

        @returns Adjusted fit score with league context

        @since 4.4.0
        """
        base_fit = await self.calculate_fit_score(prospect, team_analysis, league_settings)

        # Adjust for league scoring categories
        scoring_system = league_settings.get("scoring_system", "standard")

        # Position scarcity adjustments
        position_scarcity = self._assess_position_scarcity(
            prospect.position,
            league_settings
        )

        # Apply scarcity multiplier
        if position_scarcity == "high":
            base_fit["overall_score"] = min(10, base_fit["overall_score"] * 1.1)
        elif position_scarcity == "low":
            base_fit["overall_score"] = base_fit["overall_score"] * 0.95

        base_fit["league_adjustments"] = {
            "scoring_system": scoring_system,
            "position_scarcity": position_scarcity
        }

        return base_fit

    def _assess_position_scarcity(
        self,
        position: str,
        league_settings: Dict[str, Any]
    ) -> str:
        """
        Assess position scarcity in league context

        @param position - Position to assess
        @param league_settings - League configuration

        @returns Scarcity level (high/medium/low)

        @since 4.4.0
        """
        # Catchers and closers typically scarce
        if position == "C" or position == "RP":
            return "high"
        # Corner infielders and outfielders abundant
        elif position in ["1B", "OF", "LF", "RF", "CF"]:
            return "low"
        # Middle infielders moderate scarcity
        else:
            return "medium"
