"""Service for finding and analyzing similar prospects."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging

from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction
from app.core.cache_manager import cache_manager
from app.ml.feature_engineering import FeatureEngineeringPipeline

logger = logging.getLogger(__name__)


class ProspectComparisonsService:
    """Service for finding and analyzing similar prospects."""

    @staticmethod
    async def find_similar_prospects(
        db: AsyncSession,
        prospect_id: int,
        limit: int = 5,
        include_historical: bool = True
    ) -> Dict[str, Any]:
        """
        Find prospects similar to a given prospect using ML feature similarity.

        Args:
            db: Database session
            prospect_id: Prospect ID to find comparisons for
            limit: Maximum number of similar prospects to return
            include_historical: Whether to include historical comparisons

        Returns:
            Dictionary with current and historical comparisons
        """
        cache_key = f"comparisons:{prospect_id}:{limit}:{include_historical}"
        cached = await cache_manager.get_cached_features(cache_key)
        if cached:
            return cached

        # Get target prospect with all data
        target = await ProspectComparisonsService._get_prospect_with_features(
            db, prospect_id
        )

        if not target:
            return {"error": "Prospect not found"}

        # Find current similar prospects
        current_comparisons = await ProspectComparisonsService._find_current_similar(
            db, target, limit
        )

        # Find historical comparisons if requested
        historical_comparisons = []
        if include_historical:
            historical_comparisons = await ProspectComparisonsService._find_historical_similar(
                db, target, limit
            )

        result = {
            "prospect_id": prospect_id,
            "prospect_name": target["prospect"].name,
            "current_comparisons": current_comparisons,
            "historical_comparisons": historical_comparisons,
            "comparison_metadata": {
                "method": "cosine_similarity",
                "features_used": ProspectComparisonsService._get_feature_list(),
                "generated_at": datetime.utcnow().isoformat()
            }
        }

        # Cache for 12 hours
        await cache_manager.cache_prospect_features(
            cache_key, result, ttl=43200
        )

        return result

    @staticmethod
    async def get_organizational_context(
        db: AsyncSession,
        prospect_id: int
    ) -> Dict[str, Any]:
        """
        Get organizational depth chart context for a prospect.

        Args:
            db: Database session
            prospect_id: Prospect ID

        Returns:
            Dictionary with organizational context
        """
        cache_key = f"org_context:{prospect_id}"
        cached = await cache_manager.get_cached_features(cache_key)
        if cached:
            return cached

        # Get target prospect
        query = select(Prospect).where(Prospect.id == prospect_id)
        result = await db.execute(query)
        prospect = result.scalar_one_or_none()

        if not prospect:
            return {"error": "Prospect not found"}

        # Get other prospects in the same organization and position
        org_query = select(Prospect).where(
            and_(
                Prospect.organization == prospect.organization,
                Prospect.position == prospect.position,
                Prospect.id != prospect_id
            )
        ).order_by(Prospect.eta_year, Prospect.age)

        org_result = await db.execute(org_query)
        org_prospects = org_result.scalars().all()

        # Get system ranking within organization
        system_rank_query = select(
            func.count(Prospect.id)
        ).where(
            and_(
                Prospect.organization == prospect.organization,
                Prospect.id != prospect_id
            )
        )

        # This would need dynasty scores, so we'll estimate
        system_rank = 1  # Placeholder

        # Build depth chart
        depth_chart = {
            "ahead": [],
            "behind": []
        }

        for org_prospect in org_prospects:
            entry = {
                "id": org_prospect.id,
                "name": org_prospect.name,
                "level": org_prospect.level,
                "age": org_prospect.age,
                "eta_year": org_prospect.eta_year
            }

            if org_prospect.eta_year and prospect.eta_year:
                if org_prospect.eta_year < prospect.eta_year:
                    depth_chart["ahead"].append(entry)
                else:
                    depth_chart["behind"].append(entry)
            elif org_prospect.age and prospect.age:
                if org_prospect.age < prospect.age:
                    depth_chart["ahead"].append(entry)
                else:
                    depth_chart["behind"].append(entry)

        result = {
            "prospect_id": prospect_id,
            "prospect_name": prospect.name,
            "organization": prospect.organization,
            "position": prospect.position,
            "level": prospect.level,
            "organizational_depth": {
                "total_at_position": len(org_prospects),
                "prospects_ahead": len(depth_chart["ahead"]),
                "prospects_behind": len(depth_chart["behind"]),
                "system_rank_estimate": system_rank
            },
            "depth_chart": depth_chart,
            "blocked_status": len(depth_chart["ahead"]) >= 2  # Blocked if 2+ ahead
        }

        # Cache for 6 hours
        await cache_manager.cache_prospect_features(
            cache_key, result, ttl=21600
        )

        return result

    @staticmethod
    async def _get_prospect_with_features(
        db: AsyncSession,
        prospect_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get prospect with all features for comparison."""
        # Get prospect with all related data
        query = select(Prospect).options(
            selectinload(Prospect.stats),
            selectinload(Prospect.scouting_grades)
        ).where(Prospect.id == prospect_id)

        result = await db.execute(query)
        prospect = result.scalar_one_or_none()

        if not prospect:
            return None

        # Get ML prediction
        ml_query = select(MLPrediction).where(
            and_(
                MLPrediction.prospect_id == prospect_id,
                MLPrediction.prediction_type == 'success_rating'
            )
        ).order_by(MLPrediction.generated_at.desc()).limit(1)

        ml_result = await db.execute(ml_query)
        ml_prediction = ml_result.scalar_one_or_none()

        # Get latest stats
        latest_stats = None
        if prospect.stats:
            latest_stats = max(prospect.stats, key=lambda s: s.date_recorded)

        # Get best scouting grade
        best_grade = None
        if prospect.scouting_grades:
            for source in ['Fangraphs', 'MLB Pipeline', 'Baseball America']:
                grades = [g for g in prospect.scouting_grades if g.source == source]
                if grades:
                    best_grade = grades[0]
                    break

        return {
            "prospect": prospect,
            "latest_stats": latest_stats,
            "scouting_grade": best_grade,
            "ml_prediction": ml_prediction,
            "features": ProspectComparisonsService._extract_features(
                prospect, latest_stats, best_grade, ml_prediction
            )
        }

    @staticmethod
    async def _find_current_similar(
        db: AsyncSession,
        target: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Find similar current prospects."""
        # Get all prospects in similar position and age range
        age_range = 3  # +/- 3 years
        target_age = target["prospect"].age or 20

        query = select(Prospect).options(
            selectinload(Prospect.stats),
            selectinload(Prospect.scouting_grades)
        ).where(
            and_(
                Prospect.id != target["prospect"].id,
                Prospect.position == target["prospect"].position,
                Prospect.age.between(target_age - age_range, target_age + age_range)
            )
        ).limit(50)  # Get more to filter by similarity

        result = await db.execute(query)
        candidates = result.scalars().all()

        # Calculate similarity scores
        similarities = []

        for candidate in candidates:
            # Get features for candidate
            latest_stats = max(candidate.stats, key=lambda s: s.date_recorded) if candidate.stats else None
            best_grade = None
            if candidate.scouting_grades:
                for source in ['Fangraphs', 'MLB Pipeline', 'Baseball America']:
                    grades = [g for g in candidate.scouting_grades if g.source == source]
                    if grades:
                        best_grade = grades[0]
                        break

            candidate_features = ProspectComparisonsService._extract_features(
                candidate, latest_stats, best_grade, None
            )

            # Calculate similarity
            similarity = ProspectComparisonsService._calculate_similarity(
                target["features"], candidate_features
            )

            similarities.append({
                "prospect": {
                    "id": candidate.id,
                    "name": candidate.name,
                    "organization": candidate.organization,
                    "level": candidate.level,
                    "position": candidate.position,
                    "age": candidate.age,
                    "eta_year": candidate.eta_year
                },
                "similarity_score": round(similarity, 3),
                "matching_features": ProspectComparisonsService._get_matching_features(
                    target["features"], candidate_features
                ),
                "latest_stats": ProspectComparisonsService._format_comparison_stats(latest_stats),
                "scouting_grade": {
                    "overall": best_grade.overall if best_grade else None,
                    "future_value": best_grade.future_value if best_grade else None
                }
            })

        # Sort by similarity and return top N
        similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similarities[:limit]

    @staticmethod
    async def _find_historical_similar(
        db: AsyncSession,
        target: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Find historical prospects with similar profiles.

        Note: In production, this would query a historical database of MLB players
        at similar ages/levels. For now, we return a placeholder structure.
        """
        # This would query historical prospect data and their MLB outcomes
        # For demonstration, returning structure with placeholder data

        historical_comps = []

        # Example structure for historical comparisons
        if target["prospect"].position in ['SS', '2B', '3B']:
            historical_comps = [
                {
                    "player_name": "Francisco Lindor",
                    "similarity_score": 0.875,
                    "age_at_similar_level": target["prospect"].age,
                    "mlb_outcome": {
                        "reached_mlb": True,
                        "peak_war": 41.4,
                        "all_star_appearances": 4,
                        "career_ops": 0.788
                    },
                    "minor_league_stats_at_age": {
                        "avg": 0.278,
                        "obp": 0.348,
                        "slg": 0.428
                    }
                },
                {
                    "player_name": "Gleyber Torres",
                    "similarity_score": 0.823,
                    "age_at_similar_level": target["prospect"].age,
                    "mlb_outcome": {
                        "reached_mlb": True,
                        "peak_war": 13.2,
                        "all_star_appearances": 2,
                        "career_ops": 0.762
                    },
                    "minor_league_stats_at_age": {
                        "avg": 0.275,
                        "obp": 0.358,
                        "slg": 0.421
                    }
                }
            ]
        elif target["prospect"].position in ['SP', 'RP']:
            historical_comps = [
                {
                    "player_name": "Shane Bieber",
                    "similarity_score": 0.892,
                    "age_at_similar_level": target["prospect"].age,
                    "mlb_outcome": {
                        "reached_mlb": True,
                        "peak_war": 20.1,
                        "cy_young_awards": 1,
                        "career_era": 3.22
                    },
                    "minor_league_stats_at_age": {
                        "era": 2.86,
                        "whip": 1.16,
                        "k_9": 9.8
                    }
                }
            ]

        return historical_comps[:limit]

    @staticmethod
    def _extract_features(
        prospect: Prospect,
        stats: Optional[ProspectStats],
        grade: Optional[ScoutingGrades],
        ml_pred: Optional[MLPrediction]
    ) -> np.ndarray:
        """Extract feature vector for comparison."""
        features = []

        # Age and level features
        features.append(prospect.age or 20)
        level_map = {'Rookie': 1, 'A': 2, 'A+': 3, 'AA': 4, 'AAA': 5}
        features.append(level_map.get(prospect.level, 3))

        # Statistical features
        if stats:
            if stats.batting_avg is not None:
                features.extend([
                    stats.batting_avg or 0,
                    stats.on_base_pct or 0,
                    stats.slugging_pct or 0,
                    stats.wrc_plus or 100,
                    stats.strikeout_rate or 20,
                    stats.walk_rate or 8
                ])
            else:
                features.extend([0, 0, 0, 100, 20, 8])

            if stats.era is not None:
                features.extend([
                    stats.era or 4.0,
                    stats.whip or 1.3,
                    stats.k_per_9 or 8,
                    stats.bb_per_9 or 3
                ])
            else:
                features.extend([4.0, 1.3, 8, 3])
        else:
            features.extend([0, 0, 0, 100, 20, 8, 4.0, 1.3, 8, 3])

        # Scouting grades
        if grade:
            features.extend([
                grade.overall or 50,
                grade.future_value or 50
            ])
        else:
            features.extend([50, 50])

        # ML prediction
        if ml_pred:
            features.append(ml_pred.success_probability or 0.5)
        else:
            features.append(0.5)

        return np.array(features)

    @staticmethod
    def _calculate_similarity(features1: np.ndarray, features2: np.ndarray) -> float:
        """Calculate cosine similarity between two feature vectors."""
        if len(features1) != len(features2):
            return 0.0

        # Normalize features
        features1 = features1.reshape(1, -1)
        features2 = features2.reshape(1, -1)

        # Handle any NaN values
        features1 = np.nan_to_num(features1, nan=0.0)
        features2 = np.nan_to_num(features2, nan=0.0)

        # Calculate cosine similarity
        similarity = cosine_similarity(features1, features2)[0][0]

        # Ensure it's between 0 and 1
        return max(0.0, min(1.0, similarity))

    @staticmethod
    def _get_matching_features(features1: np.ndarray, features2: np.ndarray) -> List[str]:
        """Identify which features are most similar."""
        matching = []

        feature_names = [
            "age", "level", "batting_avg", "obp", "slg", "wrc_plus",
            "k_rate", "bb_rate", "era", "whip", "k_9", "bb_9",
            "overall_grade", "future_value", "ml_score"
        ]

        # Calculate percentage difference for each feature
        for i, name in enumerate(feature_names):
            if i < len(features1) and i < len(features2):
                if features1[i] != 0:
                    diff = abs((features2[i] - features1[i]) / features1[i])
                    if diff < 0.1:  # Within 10%
                        matching.append(name)

        return matching

    @staticmethod
    def _format_comparison_stats(stats: Optional[ProspectStats]) -> Optional[Dict[str, Any]]:
        """Format stats for comparison display."""
        if not stats:
            return None

        formatted = {}

        if stats.batting_avg is not None:
            formatted["batting"] = {
                "avg": stats.batting_avg,
                "obp": stats.on_base_pct,
                "slg": stats.slugging_pct,
                "ops": round((stats.on_base_pct or 0) + (stats.slugging_pct or 0), 3)
            }

        if stats.era is not None:
            formatted["pitching"] = {
                "era": stats.era,
                "whip": stats.whip,
                "k_9": stats.k_per_9,
                "bb_9": stats.bb_per_9
            }

        return formatted

    @staticmethod
    def _get_feature_list() -> List[str]:
        """Get list of features used for comparison."""
        return [
            "age", "minor_league_level", "batting_average", "on_base_percentage",
            "slugging_percentage", "wrc_plus", "strikeout_rate", "walk_rate",
            "era", "whip", "k_per_9", "bb_per_9", "scouting_overall_grade",
            "scouting_future_value", "ml_success_probability"
        ]