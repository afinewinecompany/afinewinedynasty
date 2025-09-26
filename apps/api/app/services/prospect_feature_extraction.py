"""Prospect Feature Extraction Service

Extracts and prepares prospect features for ML prediction with caching
and optimized database queries for <500ms response time requirements.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ..core.cache_manager import CacheManager
from ..models.prospect import Prospect
from ..models.prospect_stats import ProspectStats
from ..models.scouting_grades import ScoutingGrades

logger = logging.getLogger(__name__)


class ProspectFeatureExtractor:
    """Extract and prepare prospect features for ML prediction."""

    def __init__(self):
        self.feature_cache_ttl = 1800  # 30 minutes

    async def get_prospect_features(
        self,
        prospect_id: int,
        db: Session,
        cache_manager: CacheManager
    ) -> Optional[Dict[str, Any]]:
        """
        Extract comprehensive prospect features for ML prediction.

        Returns preprocessed features ready for model input with caching
        for optimal performance.
        """
        try:
            # Check cache first for fast response
            cached_features = await cache_manager.get_cached_features(prospect_id)
            if cached_features:
                logger.debug(f"Feature cache hit for prospect {prospect_id}")
                return cached_features

            # Extract features from database
            features = await self._extract_raw_features(prospect_id, db)

            if not features:
                logger.warning(f"No features found for prospect {prospect_id}")
                return None

            # Preprocess features for ML model
            processed_features = self._preprocess_features(features)

            # Cache the processed features
            await cache_manager.cache_prospect_features(
                prospect_id=prospect_id,
                features=processed_features,
                ttl=self.feature_cache_ttl
            )

            logger.debug(f"Features extracted and cached for prospect {prospect_id}")
            return processed_features

        except Exception as e:
            logger.error(f"Failed to extract features for prospect {prospect_id}: {e}")
            return None

    async def _extract_raw_features(
        self,
        prospect_id: int,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """Extract raw prospect data from database."""

        # Get basic prospect information
        prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
        if not prospect:
            return None

        # Get recent performance statistics (last 2 years)
        cutoff_date = datetime.utcnow() - timedelta(days=730)
        recent_stats = db.query(ProspectStats).filter(
            and_(
                ProspectStats.prospect_id == prospect_id,
                ProspectStats.date >= cutoff_date
            )
        ).order_by(desc(ProspectStats.date)).all()

        # Get latest scouting grades
        latest_grades = db.query(ScoutingGrades).filter(
            ScoutingGrades.prospect_id == prospect_id
        ).order_by(desc(ScoutingGrades.updated_at)).first()

        # Organize raw features
        raw_features = {
            "prospect_info": {
                "id": prospect.id,
                "mlb_id": prospect.mlb_id,
                "name": prospect.name,
                "position": prospect.position,
                "organization": prospect.organization,
                "level": prospect.level,
                "age": prospect.age,
                "eta_year": prospect.eta_year,
                "draft_year": prospect.draft_year,
                "draft_round": prospect.draft_round,
                "height": prospect.height,
                "weight": prospect.weight,
                "bats": prospect.bats,
                "throws": prospect.throws
            },
            "performance_stats": [
                {
                    "date": stat.date,
                    "level": stat.level,
                    "team": stat.team,
                    "games": stat.games,
                    "plate_appearances": stat.plate_appearances,
                    "at_bats": stat.at_bats,
                    "hits": stat.hits,
                    "doubles": stat.doubles,
                    "triples": stat.triples,
                    "home_runs": stat.home_runs,
                    "runs": stat.runs,
                    "rbis": stat.rbis,
                    "walks": stat.walks,
                    "strikeouts": stat.strikeouts,
                    "stolen_bases": stat.stolen_bases,
                    "caught_stealing": stat.caught_stealing,
                    "batting_average": stat.batting_average,
                    "on_base_percentage": stat.on_base_percentage,
                    "slugging_percentage": stat.slugging_percentage,
                    "ops": stat.ops,
                    # Pitching stats
                    "innings_pitched": stat.innings_pitched,
                    "wins": stat.wins,
                    "losses": stat.losses,
                    "saves": stat.saves,
                    "games_started": stat.games_started,
                    "earned_runs": stat.earned_runs,
                    "hits_allowed": stat.hits_allowed,
                    "walks_allowed": stat.walks_allowed,
                    "strikeouts_pitched": stat.strikeouts_pitched,
                    "era": stat.era,
                    "whip": stat.whip
                }
                for stat in recent_stats
            ],
            "scouting_grades": {
                "hit": latest_grades.hit if latest_grades else None,
                "power": latest_grades.power if latest_grades else None,
                "run": latest_grades.run if latest_grades else None,
                "arm": latest_grades.arm if latest_grades else None,
                "field": latest_grades.field if latest_grades else None,
                "overall": latest_grades.overall if latest_grades else None,
                "fastball": latest_grades.fastball if latest_grades else None,
                "curveball": latest_grades.curveball if latest_grades else None,
                "slider": latest_grades.slider if latest_grades else None,
                "changeup": latest_grades.changeup if latest_grades else None,
                "control": latest_grades.control if latest_grades else None,
                "source": latest_grades.source if latest_grades else None,
                "updated_at": latest_grades.updated_at if latest_grades else None
            }
        }

        return raw_features

    def _preprocess_features(self, raw_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess raw features into ML-ready format.

        This method transforms raw prospect data into numerical features
        that match the training pipeline's feature engineering.
        """
        processed = {}

        # Basic prospect features
        prospect_info = raw_features["prospect_info"]
        processed.update({
            "age": prospect_info.get("age", 0),
            "height": prospect_info.get("height", 0),
            "weight": prospect_info.get("weight", 0),
            "draft_round": prospect_info.get("draft_round", 0),
            "years_since_draft": datetime.now().year - (prospect_info.get("draft_year", datetime.now().year)),
            "eta_years_remaining": (prospect_info.get("eta_year", datetime.now().year + 5) - datetime.now().year)
        })

        # Position encoding (matches training pipeline)
        position_mapping = {
            "C": 1, "1B": 2, "2B": 3, "3B": 4, "SS": 5, "LF": 6, "CF": 7, "RF": 8,
            "OF": 6.5, "INF": 3.5, "UTIL": 4.5, "DH": 9, "P": 10, "SP": 10, "RP": 11
        }
        processed["position_encoded"] = position_mapping.get(prospect_info.get("position", "UTIL"), 4.5)

        # Level encoding
        level_mapping = {
            "Rookie": 1, "Short Season": 2, "Low-A": 3, "High-A": 4, "AA": 5, "AAA": 6, "MLB": 7
        }
        processed["level_encoded"] = level_mapping.get(prospect_info.get("level", "Low-A"), 3)

        # Handedness encoding
        processed["bats_left"] = 1 if prospect_info.get("bats") == "L" else 0
        processed["bats_right"] = 1 if prospect_info.get("bats") == "R" else 0
        processed["bats_switch"] = 1 if prospect_info.get("bats") == "S" else 0
        processed["throws_left"] = 1 if prospect_info.get("throws") == "L" else 0
        processed["throws_right"] = 1 if prospect_info.get("throws") == "R" else 0

        # Performance statistics aggregation
        stats = raw_features["performance_stats"]
        if stats:
            processed.update(self._aggregate_performance_stats(stats))
        else:
            # Default values for missing stats
            processed.update(self._get_default_performance_stats())

        # Scouting grades
        grades = raw_features["scouting_grades"]
        processed.update(self._process_scouting_grades(grades))

        # Derived features
        processed.update(self._calculate_derived_features(processed))

        return processed

    def _aggregate_performance_stats(self, stats: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate performance statistics across multiple seasons/levels."""

        if not stats:
            return self._get_default_performance_stats()

        # Separate hitting and pitching stats
        hitting_stats = [s for s in stats if s.get("plate_appearances", 0) > 0]
        pitching_stats = [s for s in stats if s.get("innings_pitched", 0) > 0]

        aggregated = {}

        # Hitting statistics
        if hitting_stats:
            total_pa = sum(s.get("plate_appearances", 0) for s in hitting_stats)
            total_ab = sum(s.get("at_bats", 0) for s in hitting_stats)
            total_hits = sum(s.get("hits", 0) for s in hitting_stats)
            total_hrs = sum(s.get("home_runs", 0) for s in hitting_stats)
            total_walks = sum(s.get("walks", 0) for s in hitting_stats)
            total_ks = sum(s.get("strikeouts", 0) for s in hitting_stats)
            total_sbs = sum(s.get("stolen_bases", 0) for s in hitting_stats)

            aggregated.update({
                "career_pa": total_pa,
                "career_ab": total_ab,
                "career_avg": total_hits / total_ab if total_ab > 0 else 0,
                "career_obp": (total_hits + total_walks) / total_pa if total_pa > 0 else 0,
                "career_hr_rate": total_hrs / total_pa if total_pa > 0 else 0,
                "career_bb_rate": total_walks / total_pa if total_pa > 0 else 0,
                "career_k_rate": total_ks / total_pa if total_pa > 0 else 0,
                "career_sb_rate": total_sbs / (total_sbs + sum(s.get("caught_stealing", 0) for s in hitting_stats)) if total_sbs > 0 else 0,
                "games_played": sum(s.get("games", 0) for s in hitting_stats),
                "recent_avg": hitting_stats[0].get("batting_average", 0) if hitting_stats else 0,
                "recent_ops": hitting_stats[0].get("ops", 0) if hitting_stats else 0
            })
        else:
            aggregated.update(self._get_default_hitting_stats())

        # Pitching statistics
        if pitching_stats:
            total_ip = sum(s.get("innings_pitched", 0) for s in pitching_stats)
            total_er = sum(s.get("earned_runs", 0) for s in pitching_stats)
            total_h_allowed = sum(s.get("hits_allowed", 0) for s in pitching_stats)
            total_bb_allowed = sum(s.get("walks_allowed", 0) for s in pitching_stats)
            total_k_pitched = sum(s.get("strikeouts_pitched", 0) for s in pitching_stats)

            aggregated.update({
                "career_ip": total_ip,
                "career_era": (total_er * 9) / total_ip if total_ip > 0 else 0,
                "career_whip": (total_h_allowed + total_bb_allowed) / total_ip if total_ip > 0 else 0,
                "career_k9": (total_k_pitched * 9) / total_ip if total_ip > 0 else 0,
                "career_bb9": (total_bb_allowed * 9) / total_ip if total_ip > 0 else 0,
                "games_pitched": sum(s.get("games", 0) for s in pitching_stats),
                "games_started": sum(s.get("games_started", 0) for s in pitching_stats),
                "recent_era": pitching_stats[0].get("era", 0) if pitching_stats else 0,
                "recent_whip": pitching_stats[0].get("whip", 0) if pitching_stats else 0
            })
        else:
            aggregated.update(self._get_default_pitching_stats())

        return aggregated

    def _process_scouting_grades(self, grades: Dict[str, Any]) -> Dict[str, Any]:
        """Process scouting grades into numerical features."""

        grade_features = {}

        # Standard scouting grades (20-80 scale)
        hitting_grades = ["hit", "power", "run", "arm", "field"]
        pitching_grades = ["fastball", "curveball", "slider", "changeup", "control"]

        for grade in hitting_grades + pitching_grades + ["overall"]:
            value = grades.get(grade)
            if value is not None:
                grade_features[f"grade_{grade}"] = float(value)
            else:
                grade_features[f"grade_{grade}"] = 50.0  # Default/average grade

        # Grade age (days since last update)
        if grades.get("updated_at"):
            days_since_update = (datetime.utcnow() - grades["updated_at"]).days
            grade_features["grade_age_days"] = days_since_update
        else:
            grade_features["grade_age_days"] = 365  # Default to 1 year old

        return grade_features

    def _calculate_derived_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate derived features from base features."""

        derived = {}

        # BMI calculation
        if features.get("height", 0) > 0 and features.get("weight", 0) > 0:
            height_m = features["height"] * 0.0254  # inches to meters
            weight_kg = features["weight"] * 0.453592  # pounds to kg
            derived["bmi"] = weight_kg / (height_m ** 2)
        else:
            derived["bmi"] = 24.0  # Average BMI

        # Performance ratios
        if features.get("career_pa", 0) > 0:
            derived["hr_per_pa"] = features.get("career_hr_rate", 0)
            derived["bb_per_k"] = features.get("career_bb_rate", 0) / max(features.get("career_k_rate", 0.01), 0.01)

        # Grade combinations
        derived["hitting_tool_avg"] = (
            features.get("grade_hit", 50) + features.get("grade_power", 50)
        ) / 2

        derived["defensive_tool_avg"] = (
            features.get("grade_run", 50) + features.get("grade_arm", 50) + features.get("grade_field", 50)
        ) / 3

        derived["pitching_stuff_avg"] = (
            features.get("grade_fastball", 50) + features.get("grade_curveball", 50) +
            features.get("grade_slider", 50) + features.get("grade_changeup", 50)
        ) / 4

        return derived

    def _get_default_performance_stats(self) -> Dict[str, Any]:
        """Return default performance statistics for prospects with no data."""
        defaults = self._get_default_hitting_stats()
        defaults.update(self._get_default_pitching_stats())
        return defaults

    def _get_default_hitting_stats(self) -> Dict[str, Any]:
        """Default hitting statistics."""
        return {
            "career_pa": 0,
            "career_ab": 0,
            "career_avg": 0.250,  # League average
            "career_obp": 0.320,
            "career_hr_rate": 0.020,
            "career_bb_rate": 0.080,
            "career_k_rate": 0.220,
            "career_sb_rate": 0.750,
            "games_played": 0,
            "recent_avg": 0.250,
            "recent_ops": 0.700
        }

    def _get_default_pitching_stats(self) -> Dict[str, Any]:
        """Default pitching statistics."""
        return {
            "career_ip": 0,
            "career_era": 4.50,  # League average
            "career_whip": 1.35,
            "career_k9": 8.0,
            "career_bb9": 3.0,
            "games_pitched": 0,
            "games_started": 0,
            "recent_era": 4.50,
            "recent_whip": 1.35
        }