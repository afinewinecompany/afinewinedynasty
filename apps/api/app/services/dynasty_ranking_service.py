"""Dynasty-specific ranking algorithm for prospects."""

from typing import Dict, Optional
from datetime import date
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction


class DynastyRankingService:
    """Service for calculating dynasty-specific prospect rankings."""

    @staticmethod
    def calculate_dynasty_score(
        prospect: Prospect,
        ml_prediction: Optional[MLPrediction] = None,
        latest_stats: Optional[ProspectStats] = None,
        scouting_grade: Optional[ScoutingGrades] = None
    ) -> Dict[str, float]:
        """
        Calculate dynasty-specific ranking score for a prospect.

        Weights:
        - ML Prediction Score: 35%
        - Scouting Grade: 25%
        - Age Factor: 20%
        - Performance Stats: 15%
        - ETA Factor: 5%

        Returns dictionary with score components and total.
        """
        score_components = {
            'ml_score': 0.0,
            'scouting_score': 0.0,
            'age_score': 0.0,
            'performance_score': 0.0,
            'eta_score': 0.0,
            'total_score': 0.0,
            'confidence_level': 'Low'
        }

        # ML Prediction component (35% weight)
        if ml_prediction and ml_prediction.prediction_type == 'success_rating':
            ml_raw = ml_prediction.prediction_value * 100  # Convert to 0-100 scale
            score_components['ml_score'] = ml_raw * 0.35

            # Set confidence level based on ML confidence
            if ml_prediction.confidence_score:
                if ml_prediction.confidence_score >= 0.8:
                    score_components['confidence_level'] = 'High'
                elif ml_prediction.confidence_score >= 0.6:
                    score_components['confidence_level'] = 'Medium'

        # Scouting Grade component (25% weight)
        if scouting_grade and scouting_grade.future_value:
            # Convert 20-80 grade to 0-100 scale
            scout_raw = ((scouting_grade.future_value - 20) / 60) * 100
            score_components['scouting_score'] = scout_raw * 0.25

        # Age Factor component (20% weight) - younger is better
        if prospect.age:
            current_year = date.today().year
            age_factor = max(0, min(100, (25 - prospect.age) * 10))  # Peak at age 15, decline after 25
            score_components['age_score'] = age_factor * 0.20

        # Performance Stats component (15% weight)
        if latest_stats:
            perf_score = 0.0

            # For hitters
            if prospect.position not in ['SP', 'RP']:
                if latest_stats.batting_avg is not None and latest_stats.batting_avg > 0:
                    perf_score += min(50, (latest_stats.batting_avg / 0.300) * 25)  # Cap at 50 points
                if latest_stats.on_base_pct is not None and latest_stats.on_base_pct > 0:
                    perf_score += min(50, (latest_stats.on_base_pct / 0.400) * 25)  # Cap at 50 points
                if latest_stats.slugging_pct is not None and latest_stats.slugging_pct > 0:
                    perf_score += min(50, (latest_stats.slugging_pct / 0.500) * 25)  # Cap at 50 points
                if latest_stats.wrc_plus is not None and latest_stats.wrc_plus > 0:
                    perf_score += min(50, (latest_stats.wrc_plus / 100) * 25)  # Cap at 50 points

            # For pitchers
            else:
                if latest_stats.era is not None and latest_stats.era > 0:
                    # Lower ERA is better (inverted scale, cap at 50 points)
                    perf_score += max(0, min(50, (4.0 - latest_stats.era) / 4.0 * 50))  # ERA under 4 is good
                if latest_stats.whip is not None and latest_stats.whip > 0:
                    # Lower WHIP is better (inverted scale, cap at 25 points)
                    perf_score += max(0, min(25, (1.3 - latest_stats.whip) / 1.3 * 25))  # WHIP under 1.3 is good
                if latest_stats.strikeouts_per_nine is not None and latest_stats.strikeouts_per_nine > 0:
                    perf_score += min(25, (latest_stats.strikeouts_per_nine / 9.0) * 25)  # 9+ K/9 is good

            score_components['performance_score'] = min(100, perf_score) * 0.15

        # ETA Factor component (5% weight) - sooner is better
        if prospect.eta_year:
            current_year = date.today().year
            years_to_majors = max(0, prospect.eta_year - current_year)
            eta_factor = max(0, 100 - (years_to_majors * 20))  # Lose 20 points per year
            score_components['eta_score'] = eta_factor * 0.05

        # Calculate total score
        score_components['total_score'] = (
            score_components['ml_score'] +
            score_components['scouting_score'] +
            score_components['age_score'] +
            score_components['performance_score'] +
            score_components['eta_score']
        )

        return score_components

    @staticmethod
    def rank_prospects(prospects_with_scores: list) -> list:
        """
        Rank prospects based on their dynasty scores.

        Args:
            prospects_with_scores: List of tuples (prospect, score_dict)

        Returns:
            Sorted list with rankings added
        """
        # Sort by total score descending
        sorted_prospects = sorted(
            prospects_with_scores,
            key=lambda x: x[1]['total_score'],
            reverse=True
        )

        # Add rankings
        for rank, (prospect, scores) in enumerate(sorted_prospects, 1):
            scores['dynasty_rank'] = rank

        return sorted_prospects