import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.db.models import Prospect, ProspectStats
from app.schemas.prospect_schemas import ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate match."""
    prospect1_id: int
    prospect2_id: int
    match_type: str  # 'exact_mlb_id', 'name_similarity', 'fuzzy_match'
    confidence_score: float  # 0.0 to 1.0
    matching_fields: List[str]
    conflicting_fields: List[str]
    merge_recommendation: str  # 'merge', 'review', 'ignore'


@dataclass
class MergeResult:
    """Result of a merge operation."""
    success: bool
    primary_prospect_id: int
    merged_prospect_id: Optional[int]
    conflicts_resolved: List[str]
    data_preserved: Dict[str, Any]
    errors: List[str]


class DuplicateDetectionService:
    """Service for detecting and merging duplicate prospect records."""

    def __init__(self):
        self.similarity_thresholds = {
            "name_exact": 1.0,
            "name_high": 0.90,
            "name_medium": 0.75,
            "name_low": 0.60,
            "organization_match": 0.85,
            "position_match": 1.0
        }

        self.merge_strategies = {
            "mlb_id": "preserve_non_null",  # Keep non-null value
            "name": "prefer_longer",        # Prefer longer name
            "organization": "prefer_newer", # Prefer more recent data
            "level": "prefer_higher",       # Prefer higher level
            "age": "prefer_younger",        # Prefer younger age if reasonable
            "eta_year": "prefer_newer"      # Prefer more recent ETA
        }

    async def detect_duplicates(self, session: AsyncSession, prospect_data: Dict[str, Any] = None) -> List[DuplicateMatch]:
        """
        Detect potential duplicate prospects in the database.

        Args:
            session: Database session
            prospect_data: Optional specific prospect to check against existing records

        Returns:
            List of potential duplicate matches
        """
        matches = []

        if prospect_data:
            # Check new prospect against existing records
            matches = await self._check_prospect_against_database(session, prospect_data)
        else:
            # Check all existing records for duplicates
            matches = await self._check_all_prospects_for_duplicates(session)

        return matches

    async def _check_prospect_against_database(
        self,
        session: AsyncSession,
        prospect_data: Dict[str, Any]
    ) -> List[DuplicateMatch]:
        """Check a new prospect against existing database records."""
        matches = []

        # Get all existing prospects
        result = await session.execute(select(Prospect))
        existing_prospects = result.scalars().all()

        for existing in existing_prospects:
            match = await self._compare_prospects(prospect_data, existing)
            if match and match.confidence_score >= self.similarity_thresholds["name_low"]:
                matches.append(match)

        return sorted(matches, key=lambda x: x.confidence_score, reverse=True)

    async def _check_all_prospects_for_duplicates(self, session: AsyncSession) -> List[DuplicateMatch]:
        """Check all existing prospects against each other for duplicates."""
        matches = []

        # Get all prospects
        result = await session.execute(select(Prospect))
        all_prospects = result.scalars().all()

        # Compare each prospect with every other prospect
        for i, prospect1 in enumerate(all_prospects):
            for j, prospect2 in enumerate(all_prospects):
                if i >= j:  # Avoid duplicate comparisons
                    continue

                # Convert prospect to dict for comparison
                prospect1_data = self._prospect_to_dict(prospect1)
                match = await self._compare_prospects(prospect1_data, prospect2)

                if match and match.confidence_score >= self.similarity_thresholds["name_low"]:
                    matches.append(match)

        return sorted(matches, key=lambda x: x.confidence_score, reverse=True)

    async def _compare_prospects(
        self,
        prospect_data: Dict[str, Any],
        existing_prospect: Prospect
    ) -> Optional[DuplicateMatch]:
        """
        Compare two prospects and determine if they might be duplicates.

        Args:
            prospect_data: New prospect data
            existing_prospect: Existing prospect record

        Returns:
            DuplicateMatch if potential duplicate found, None otherwise
        """
        matching_fields = []
        conflicting_fields = []
        confidence_score = 0.0

        # Check MLB ID match (highest confidence)
        if (prospect_data.get("mlb_id") and existing_prospect.mlb_id and
            prospect_data["mlb_id"] == existing_prospect.mlb_id):
            matching_fields.append("mlb_id")
            confidence_score = 1.0
            match_type = "exact_mlb_id"
        else:
            # Check name similarity
            name_similarity = self._calculate_name_similarity(
                prospect_data.get("name", ""),
                existing_prospect.name or ""
            )

            if name_similarity >= self.similarity_thresholds["name_medium"]:
                matching_fields.append("name")
                confidence_score = name_similarity

                if name_similarity >= self.similarity_thresholds["name_high"]:
                    match_type = "name_similarity"
                else:
                    match_type = "fuzzy_match"

                # Additional matching factors
                additional_score = 0.0

                # Position match
                if (prospect_data.get("position") and existing_prospect.position and
                    prospect_data["position"] == existing_prospect.position):
                    matching_fields.append("position")
                    additional_score += 0.1

                # Organization match
                if (prospect_data.get("organization") and existing_prospect.organization):
                    org_similarity = self._calculate_text_similarity(
                        prospect_data["organization"],
                        existing_prospect.organization
                    )
                    if org_similarity >= self.similarity_thresholds["organization_match"]:
                        matching_fields.append("organization")
                        additional_score += 0.15

                # Age proximity (within 2 years)
                if (prospect_data.get("age") and existing_prospect.age and
                    abs(prospect_data["age"] - existing_prospect.age) <= 2):
                    matching_fields.append("age")
                    additional_score += 0.1

                confidence_score = min(1.0, confidence_score + additional_score)
            else:
                return None  # No significant similarity

        # Check for conflicting data
        if prospect_data.get("age") and existing_prospect.age:
            if abs(prospect_data["age"] - existing_prospect.age) > 5:
                conflicting_fields.append("age")

        if (prospect_data.get("position") and existing_prospect.position and
            prospect_data["position"] != existing_prospect.position):
            conflicting_fields.append("position")

        # Determine merge recommendation
        if confidence_score >= 0.95:
            recommendation = "merge"
        elif confidence_score >= 0.75 and len(conflicting_fields) <= 1:
            recommendation = "review"
        else:
            recommendation = "ignore"

        return DuplicateMatch(
            prospect1_id=0,  # Will be set for new prospects
            prospect2_id=existing_prospect.id,
            match_type=match_type,
            confidence_score=confidence_score,
            matching_fields=matching_fields,
            conflicting_fields=conflicting_fields,
            merge_recommendation=recommendation
        )

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        if not name1 or not name2:
            return 0.0

        # Normalize names
        name1_clean = self._normalize_name(name1)
        name2_clean = self._normalize_name(name2)

        # Exact match
        if name1_clean == name2_clean:
            return 1.0

        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, name1_clean, name2_clean).ratio()

        # Check for reversed names (First Last vs Last First)
        name1_parts = name1_clean.split()
        name2_parts = name2_clean.split()

        if len(name1_parts) >= 2 and len(name2_parts) >= 2:
            # Try reversing first and last name
            reversed_name1 = f"{name1_parts[-1]} {name1_parts[0]}"
            reversed_similarity = SequenceMatcher(None, reversed_name1, name2_clean).ratio()
            similarity = max(similarity, reversed_similarity)

        return similarity

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        if not text1 or not text2:
            return 0.0

        text1_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text1.lower().strip())
        text2_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text2.lower().strip())

        return SequenceMatcher(None, text1_clean, text2_clean).ratio()

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        if not name:
            return ""

        # Remove common suffixes and prefixes
        normalized = re.sub(r'\b(jr|sr|iii|iv|ii)\b', '', name.lower())

        # Remove punctuation and extra spaces
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    async def merge_prospects(
        self,
        session: AsyncSession,
        primary_id: int,
        duplicate_id: int,
        merge_strategy: Optional[Dict[str, str]] = None
    ) -> MergeResult:
        """
        Merge two prospect records.

        Args:
            session: Database session
            primary_id: ID of primary prospect to keep
            duplicate_id: ID of duplicate prospect to merge
            merge_strategy: Optional custom merge strategy

        Returns:
            MergeResult with operation details
        """
        try:
            # Get both prospects
            primary_result = await session.execute(
                select(Prospect).where(Prospect.id == primary_id)
                .options(selectinload(Prospect.stats))
            )
            primary_prospect = primary_result.scalar_one_or_none()

            duplicate_result = await session.execute(
                select(Prospect).where(Prospect.id == duplicate_id)
                .options(selectinload(Prospect.stats))
            )
            duplicate_prospect = duplicate_result.scalar_one_or_none()

            if not primary_prospect or not duplicate_prospect:
                return MergeResult(
                    success=False,
                    primary_prospect_id=primary_id,
                    merged_prospect_id=None,
                    conflicts_resolved=[],
                    data_preserved={},
                    errors=["One or both prospects not found"]
                )

            # Apply merge strategy
            strategy = merge_strategy or self.merge_strategies
            conflicts_resolved = []
            preserved_data = {}

            # Merge prospect fields
            for field, merge_rule in strategy.items():
                primary_value = getattr(primary_prospect, field, None)
                duplicate_value = getattr(duplicate_prospect, field, None)

                merged_value = self._resolve_field_conflict(
                    field, primary_value, duplicate_value, merge_rule,
                    primary_prospect, duplicate_prospect
                )

                if merged_value != primary_value:
                    setattr(primary_prospect, field, merged_value)
                    conflicts_resolved.append(f"{field}: {primary_value} -> {merged_value}")

                # Preserve duplicate data for audit
                if duplicate_value and duplicate_value != merged_value:
                    preserved_data[f"duplicate_{field}"] = duplicate_value

            # Merge statistics records
            await self._merge_prospect_stats(session, primary_prospect, duplicate_prospect)

            # Update timestamps
            primary_prospect.updated_at = datetime.utcnow()

            # Delete duplicate prospect
            await session.delete(duplicate_prospect)

            return MergeResult(
                success=True,
                primary_prospect_id=primary_id,
                merged_prospect_id=duplicate_id,
                conflicts_resolved=conflicts_resolved,
                data_preserved=preserved_data,
                errors=[]
            )

        except Exception as e:
            logger.error(f"Error merging prospects {primary_id} and {duplicate_id}: {str(e)}")
            return MergeResult(
                success=False,
                primary_prospect_id=primary_id,
                merged_prospect_id=duplicate_id,
                conflicts_resolved=[],
                data_preserved={},
                errors=[str(e)]
            )

    def _resolve_field_conflict(
        self,
        field: str,
        primary_value: Any,
        duplicate_value: Any,
        merge_rule: str,
        primary_prospect: Prospect,
        duplicate_prospect: Prospect
    ) -> Any:
        """Resolve conflict between two field values using merge rule."""
        if primary_value is None:
            return duplicate_value
        if duplicate_value is None:
            return primary_value

        if merge_rule == "preserve_non_null":
            return primary_value  # Primary takes precedence

        elif merge_rule == "prefer_longer":
            if isinstance(primary_value, str) and isinstance(duplicate_value, str):
                return primary_value if len(primary_value) >= len(duplicate_value) else duplicate_value
            return primary_value

        elif merge_rule == "prefer_newer":
            # Use updated_at timestamp to determine newer
            if (duplicate_prospect.updated_at and primary_prospect.updated_at and
                duplicate_prospect.updated_at > primary_prospect.updated_at):
                return duplicate_value
            return primary_value

        elif merge_rule == "prefer_higher":
            # For levels like A, AA, AAA
            level_order = {"Rookie": 0, "A-": 1, "A": 2, "A+": 3, "AA": 4, "AAA": 5, "MLB": 6}
            primary_rank = level_order.get(primary_value, -1)
            duplicate_rank = level_order.get(duplicate_value, -1)

            if duplicate_rank > primary_rank:
                return duplicate_value
            return primary_value

        elif merge_rule == "prefer_younger":
            if isinstance(primary_value, (int, float)) and isinstance(duplicate_value, (int, float)):
                # Prefer younger age if difference is reasonable (within 3 years)
                if abs(primary_value - duplicate_value) <= 3:
                    return min(primary_value, duplicate_value)
            return primary_value

        else:
            return primary_value  # Default to primary

    async def _merge_prospect_stats(
        self,
        session: AsyncSession,
        primary_prospect: Prospect,
        duplicate_prospect: Prospect
    ) -> None:
        """Merge statistics records from duplicate to primary prospect."""
        for duplicate_stat in duplicate_prospect.stats:
            # Check if primary already has stats for this date
            existing_stat = None
            for primary_stat in primary_prospect.stats:
                if primary_stat.date == duplicate_stat.date:
                    existing_stat = primary_stat
                    break

            if existing_stat:
                # Merge stats (prefer non-null values)
                for field in ['games_played', 'at_bats', 'hits', 'home_runs', 'rbi',
                             'batting_avg', 'era', 'whip', 'woba', 'wrc_plus']:
                    existing_value = getattr(existing_stat, field, None)
                    duplicate_value = getattr(duplicate_stat, field, None)

                    if existing_value is None and duplicate_value is not None:
                        setattr(existing_stat, field, duplicate_value)
            else:
                # Move stats record to primary prospect
                duplicate_stat.prospect_id = primary_prospect.id

    def _prospect_to_dict(self, prospect: Prospect) -> Dict[str, Any]:
        """Convert Prospect model to dictionary."""
        return {
            "id": prospect.id,
            "mlb_id": prospect.mlb_id,
            "name": prospect.name,
            "position": prospect.position,
            "organization": prospect.organization,
            "level": prospect.level,
            "age": prospect.age,
            "eta_year": prospect.eta_year,
            "created_at": prospect.created_at,
            "updated_at": prospect.updated_at
        }

    async def get_merge_preview(
        self,
        session: AsyncSession,
        primary_id: int,
        duplicate_id: int
    ) -> Dict[str, Any]:
        """
        Preview what would happen in a merge operation.

        Args:
            session: Database session
            primary_id: Primary prospect ID
            duplicate_id: Duplicate prospect ID

        Returns:
            Dictionary with merge preview details
        """
        # Get both prospects
        primary_result = await session.execute(select(Prospect).where(Prospect.id == primary_id))
        primary = primary_result.scalar_one_or_none()

        duplicate_result = await session.execute(select(Prospect).where(Prospect.id == duplicate_id))
        duplicate = duplicate_result.scalar_one_or_none()

        if not primary or not duplicate:
            return {"error": "One or both prospects not found"}

        preview = {
            "primary_prospect": self._prospect_to_dict(primary),
            "duplicate_prospect": self._prospect_to_dict(duplicate),
            "proposed_changes": {},
            "conflicts": [],
            "data_to_preserve": {}
        }

        # Show what each field would become
        for field, merge_rule in self.merge_strategies.items():
            primary_value = getattr(primary, field, None)
            duplicate_value = getattr(duplicate, field, None)

            merged_value = self._resolve_field_conflict(
                field, primary_value, duplicate_value, merge_rule, primary, duplicate
            )

            if merged_value != primary_value:
                preview["proposed_changes"][field] = {
                    "current": primary_value,
                    "new": merged_value,
                    "rule": merge_rule
                }

            if primary_value and duplicate_value and primary_value != duplicate_value:
                preview["conflicts"].append({
                    "field": field,
                    "primary_value": primary_value,
                    "duplicate_value": duplicate_value,
                    "resolution": merged_value,
                    "rule": merge_rule
                })

        return preview


# Singleton instance
duplicate_detection_service = DuplicateDetectionService()