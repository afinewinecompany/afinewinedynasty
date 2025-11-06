"""
Statline Ranking Service

Provides in-season statistical rankings using MILB pitch-level data.
Implements age-to-level adjustments and peer comparison logic.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, and_
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class StatlineRankingService:
    """
    Service for calculating in-season prospect rankings based on actual performance.
    Uses MILB pitch-level data for advanced metrics and age adjustments.
    """

    # Skill bucket definitions for hitters
    HITTER_SKILL_BUCKETS = {
        "power": {
            "metrics": {
                "home_run_rate": 0.15,      # HR/AB
                "iso": 0.20,                 # SLG - AVG
                "slg": 0.15,                 # Slugging %
                "hard_hit_rate": 0.25,       # From pitch data
                "pull_fly_ball_rate": 0.15,  # From pitch data
                "exit_velo_90th": 0.10       # 90th percentile exit velo
            },
            "weight": 0.20,
            "display_name": "Power",
            "icon": "⚡"
        },
        "discipline": {
            "metrics": {
                "walk_rate": 0.25,           # BB/PA
                "strikeout_rate": 0.20,      # K/PA (inverted)
                "chase_rate": 0.25,          # From pitch data (inverted)
                "discipline_score": 0.30     # From pitch data
            },
            "weight": 0.20,
            "display_name": "Discipline",
            "icon": "👁"
        },
        "contact": {
            "metrics": {
                "batting_avg": 0.20,         # H/AB
                "contact_rate": 0.30,        # From pitch data
                "whiff_rate": 0.25,          # From pitch data (inverted)
                "line_drive_rate": 0.15,     # From pitch data
                "two_strike_contact": 0.10   # From pitch data
            },
            "weight": 0.20,
            "display_name": "Contact",
            "icon": "🎯"
        },
        "speed": {
            "metrics": {
                "stolen_base_rate": 0.35,    # SB/(1B+BB+HBP)
                "sb_success_rate": 0.30,     # SB/(SB+CS)
                "triples_rate": 0.20,        # 3B/AB
                "ground_speed": 0.15         # Sprint speed if available
            },
            "weight": 0.15,
            "display_name": "Speed",
            "icon": "💨"
        },
        "approach": {
            "metrics": {
                "obp": 0.25,                         # On-base %
                "productive_swing_rate": 0.25,       # From pitch data
                "in_play_rate": 0.25,                # From pitch data
                "spray_ability": 0.25                # From pitch data
            },
            "weight": 0.15,
            "display_name": "Approach",
            "icon": "🧠"
        }
    }

    # Age adjustment factors (negative means younger is better)
    AGE_LEVEL_ADJUSTMENTS = {
        "AAA": {"avg_age": 24.5, "factor": -0.05},  # Older level, less penalty
        "AA": {"avg_age": 23.0, "factor": -0.08},
        "A+": {"avg_age": 21.5, "factor": -0.10},
        "A": {"avg_age": 20.5, "factor": -0.12},
        "ROK": {"avg_age": 18.5, "factor": -0.15}   # Younger level, more penalty
    }

    def __init__(self, db: AsyncSession):
        """Initialize the ranking service."""
        self.db = db

    async def calculate_statline_rankings(
        self,
        level: Optional[str] = None,
        min_plate_appearances: int = 100,
        season: int = 2025,
        include_pitch_data: bool = True
    ) -> List[Dict]:
        """
        Calculate comprehensive statline rankings for prospects using MILB pitch data.

        Args:
            level: Optional level filter (AAA, AA, A+, A, ROK)
            min_plate_appearances: Minimum PAs to qualify
            season: Season to analyze
            include_pitch_data: Whether to include pitch-level metrics

        Returns:
            List of ranked prospects with skill scores
        """
        logger.info(f"Calculating Statline rankings for {season} season using MILB pitch data")

        # Step 1: Get qualified players with stats from milb_batter_pitches
        players_data = await self._get_qualified_players_from_pitch_data(
            level, min_plate_appearances, season
        )

        if not players_data:
            logger.warning("No qualified players found in MILB pitch data")
            return []

        logger.info(f"Found {len(players_data)} qualified players from pitch data")

        # Step 2: Calculate skill bucket scores
        scored_players = []
        for player in players_data:
            skill_scores = self._calculate_skill_scores(player, players_data)
            player['skill_scores'] = skill_scores
            player['overall_score'] = self._calculate_overall_score(skill_scores)

            # Add age adjustment
            age_adj = self._calculate_age_adjustment(player)
            player['age_adjustment'] = age_adj
            player['adjusted_score'] = player['overall_score'] * (1 + age_adj)

            scored_players.append(player)

        # Step 3: Calculate percentiles and rank
        scored_players = self._calculate_percentiles(scored_players)
        scored_players.sort(key=lambda x: x['adjusted_score'], reverse=True)

        # Add final rankings
        for i, player in enumerate(scored_players):
            player['rank'] = i + 1

        return scored_players

    async def _get_qualified_players_from_pitch_data(
        self,
        level: Optional[str],
        min_pa: int,
        season: int
    ) -> List[Dict]:
        """Get players who meet minimum PA threshold from MILB pitch data."""

        # Build comprehensive query using milb_batter_pitches table
        base_query = """
        WITH player_stats AS (
            SELECT
                bp.mlb_batter_id,
                bp.mlb_batter_name as name,
                bp.level,
                COUNT(DISTINCT bp.game_id) as games,
                COUNT(*) as total_pitches,

                -- Plate appearances and at-bats
                COUNT(DISTINCT CASE
                    WHEN bp.event_result IS NOT NULL
                    THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                END) as total_pa,
                COUNT(DISTINCT CASE
                    WHEN bp.event_result NOT IN ('walk', 'hit_by_pitch', 'sac_fly', 'sac_bunt')
                    AND bp.event_result IS NOT NULL
                    THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                END) as total_ab,

                -- Hits breakdown
                COUNT(*) FILTER (WHERE bp.event_result IN ('single', 'double', 'triple', 'home_run')) as total_hits,
                COUNT(*) FILTER (WHERE bp.event_result = 'single') as total_1b,
                COUNT(*) FILTER (WHERE bp.event_result = 'double') as total_2b,
                COUNT(*) FILTER (WHERE bp.event_result = 'triple') as total_3b,
                COUNT(*) FILTER (WHERE bp.event_result = 'home_run') as total_hr,

                -- Other counting stats
                COUNT(*) FILTER (WHERE bp.event_result = 'walk') as total_bb,
                COUNT(*) FILTER (WHERE bp.event_result = 'strikeout') as total_k,
                COUNT(*) FILTER (WHERE bp.event_result = 'hit_by_pitch') as total_hbp,

                -- Advanced pitch metrics
                AVG(CASE WHEN bp.swing = TRUE THEN 1.0 ELSE 0.0 END) * 100 as swing_rate,
                AVG(CASE WHEN bp.contact = TRUE AND bp.swing = TRUE THEN 1.0 ELSE 0.0 END) * 100 as contact_rate,
                AVG(CASE WHEN bp.swing_and_miss = TRUE THEN 1.0 ELSE 0.0 END) * 100 as whiff_rate,
                AVG(CASE WHEN bp.swing = TRUE AND bp.zone > 9 THEN 1.0 ELSE 0.0 END) * 100 as chase_rate,

                -- Batted ball metrics
                COUNT(*) FILTER (WHERE bp.trajectory = 'line_drive') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory IS NOT NULL), 0) as line_drive_rate,
                COUNT(*) FILTER (WHERE bp.trajectory = 'fly_ball') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory IS NOT NULL), 0) as fly_ball_rate,
                COUNT(*) FILTER (WHERE bp.trajectory = 'ground_ball') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory IS NOT NULL), 0) as ground_ball_rate,

                -- Contact quality
                COUNT(*) FILTER (WHERE bp.hardness = 'hard') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.hardness IS NOT NULL), 0) as hard_hit_rate,
                AVG(bp.exit_velocity) FILTER (WHERE bp.exit_velocity IS NOT NULL) as avg_exit_velo,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY bp.exit_velocity)
                    FILTER (WHERE bp.exit_velocity IS NOT NULL) as exit_velo_90th,

                -- In-play and productive swings
                COUNT(*) FILTER (WHERE bp.contact = TRUE AND bp.foul = FALSE) * 100.0 /
                    NULLIF(COUNT(*), 0) as in_play_rate,
                COUNT(*) FILTER (WHERE bp.contact = TRUE AND bp.foul = FALSE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.swing = TRUE), 0) as productive_swing_rate,

                -- Two strike approach
                COUNT(*) FILTER (WHERE bp.contact = TRUE AND bp.strikes = 2) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.swing = TRUE AND bp.strikes = 2), 0) as two_strike_contact,

                -- Pull fly balls (power indicator)
                COUNT(*) FILTER (WHERE bp.trajectory = 'fly_ball' AND bp.hit_location IN (7, 78)) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory = 'fly_ball'), 0) as pull_fly_ball_rate,

                -- Spray chart for balance
                CASE
                    WHEN COUNT(*) FILTER (WHERE bp.hit_location IS NOT NULL) > 20 THEN
                        100 - GREATEST(
                            ABS(33 - COUNT(*) FILTER (WHERE bp.hit_location IN (7, 78, 4, 1)) * 100.0 /
                                NULLIF(COUNT(*) FILTER (WHERE bp.hit_location IS NOT NULL), 0)),
                            ABS(33 - COUNT(*) FILTER (WHERE bp.hit_location IN (8, 5, 2)) * 100.0 /
                                NULLIF(COUNT(*) FILTER (WHERE bp.hit_location IS NOT NULL), 0)),
                            ABS(33 - COUNT(*) FILTER (WHERE bp.hit_location IN (9, 89, 6, 3)) * 100.0 /
                                NULLIF(COUNT(*) FILTER (WHERE bp.hit_location IS NOT NULL), 0))
                        )
                    ELSE 50
                END as spray_ability,

                -- Discipline score calculation
                (
                    COALESCE(
                        AVG(CASE WHEN bp.contact = TRUE AND bp.swing = TRUE THEN 1.0 ELSE 0.0 END) * 100, 75
                    ) * 0.30 +
                    (100 - COALESCE(
                        AVG(CASE WHEN bp.swing_and_miss = TRUE THEN 1.0 ELSE 0.0 END) * 100, 25
                    )) * 0.30 +
                    (100 - COALESCE(
                        AVG(CASE WHEN bp.swing = TRUE AND bp.zone > 9 THEN 1.0 ELSE 0.0 END) * 100, 35
                    )) * 0.40
                ) as discipline_score

            FROM milb_batter_pitches bp
            WHERE bp.season = :season
                {level_filter}
            GROUP BY bp.mlb_batter_id, bp.mlb_batter_name, bp.level
            HAVING COUNT(DISTINCT CASE
                WHEN bp.event_result IS NOT NULL
                THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
            END) >= :min_pa
        ),
        prospect_info AS (
            -- Join with prospects table to get age and position
            SELECT
                ps.*,
                p.id as prospect_id,
                p.age,
                p.position,
                p.organization,
                -- Calculate traditional stats
                CAST(ps.total_hits AS FLOAT) / NULLIF(ps.total_ab, 0) as batting_avg,
                CAST(ps.total_hits + ps.total_bb + ps.total_hbp AS FLOAT) /
                    NULLIF(ps.total_pa, 0) as on_base_pct,
                (CAST(ps.total_1b AS FLOAT) + ps.total_2b * 2 + ps.total_3b * 3 + ps.total_hr * 4) /
                    NULLIF(ps.total_ab, 0) as slugging_pct,
                CAST(ps.total_bb AS FLOAT) / NULLIF(ps.total_pa, 0) as walk_rate,
                CAST(ps.total_k AS FLOAT) / NULLIF(ps.total_pa, 0) as strikeout_rate,
                CAST(ps.total_hr AS FLOAT) / NULLIF(ps.total_ab, 0) as home_run_rate
            FROM player_stats ps
            LEFT JOIN prospects p ON CAST(p.mlb_player_id AS INTEGER) = ps.mlb_batter_id
        )
        SELECT
            *,
            (slugging_pct - batting_avg) as iso,
            -- Power score (composite of hard hit, fly ball, and pull fly ball rates)
            COALESCE(hard_hit_rate * 0.50, 0) +
            COALESCE(fly_ball_rate * 0.25, 0) +
            COALESCE(pull_fly_ball_rate * 0.25, 0) as power_score
        FROM prospect_info
        ORDER BY total_pa DESC
        """

        level_filter = f"AND bp.level = :level" if level else ""
        query = base_query.replace("{level_filter}", level_filter)

        params = {"season": season, "min_pa": min_pa}
        if level:
            params["level"] = level

        try:
            result = await self.db.execute(text(query), params)
            rows = result.fetchall()

            # Convert to dictionaries
            players = []
            for row in rows:
                player = dict(row._mapping)
                players.append(player)

            logger.info(f"Found {len(players)} qualified players from MILB pitch data (min_pa={min_pa})")
            return players

        except Exception as e:
            logger.error(f"Error querying MILB pitch data: {e}")
            # Fall back to prospect_stats if milb_batter_pitches doesn't exist or has no data
            return await self._get_qualified_players_fallback(level, min_pa, season)

    async def _get_qualified_players_fallback(
        self,
        level: Optional[str],
        min_pa: int,
        season: int
    ) -> List[Dict]:
        """Fallback to prospect_stats table if MILB pitch data unavailable."""

        logger.info("Falling back to prospect_stats table")

        # Simplified query using prospect_stats
        query = """
        SELECT
            p.id as prospect_id,
            p.mlb_player_id as mlb_batter_id,
            p.name,
            p.position,
            p.age,
            p.level,
            ps.games_played as games,
            GREATEST(
                COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0),
                CAST(COALESCE(ps.at_bats, 0) * 1.15 AS INT)
            ) as total_pa,
            ps.at_bats as total_ab,
            ps.hits as total_hits,
            ps.home_runs as total_hr,
            ps.walks as total_bb,
            ps.strikeouts as total_k,
            ps.batting_avg,
            ps.on_base_pct,
            ps.slugging_pct,
            CAST(ps.walks AS FLOAT) / NULLIF(GREATEST(ps.at_bats + ps.walks, ps.at_bats * 1.15), 0) as walk_rate,
            CAST(ps.strikeouts AS FLOAT) / NULLIF(GREATEST(ps.at_bats + ps.walks, ps.at_bats * 1.15), 0) as strikeout_rate,
            CAST(ps.home_runs AS FLOAT) / NULLIF(ps.at_bats, 0) as home_run_rate,
            (ps.slugging_pct - ps.batting_avg) as iso,
            -- Default values for advanced metrics not in prospect_stats
            75.0 as contact_rate,
            25.0 as whiff_rate,
            35.0 as chase_rate,
            65.0 as discipline_score,
            20.0 as line_drive_rate,
            15.0 as in_play_rate,
            35.0 as productive_swing_rate,
            70.0 as two_strike_contact,
            50.0 as spray_ability,
            10.0 as hard_hit_rate,
            30.0 as pull_fly_ball_rate,
            50.0 as power_score
        FROM prospect_stats ps
        JOIN prospects p ON p.id = ps.prospect_id
        WHERE ps.at_bats > 0
            AND GREATEST(ps.at_bats + ps.walks, CAST(ps.at_bats * 1.15 AS INT)) >= :min_pa
            {level_filter}
        ORDER BY ps.at_bats DESC
        """

        level_filter = f"AND p.level = :level" if level else ""
        query = query.replace("{level_filter}", level_filter)

        params = {"min_pa": min_pa}
        if level:
            params["level"] = level

        result = await self.db.execute(text(query), params)
        rows = result.fetchall()

        players = []
        for row in rows:
            player = dict(row._mapping)
            players.append(player)

        return players

    def _calculate_skill_scores(
        self,
        player: Dict,
        all_players: List[Dict]
    ) -> Dict[str, Dict]:
        """Calculate skill bucket scores for a player."""

        skill_scores = {}

        for bucket_name, bucket_config in self.HITTER_SKILL_BUCKETS.items():
            bucket_score = 0
            bucket_details = {}

            for metric_name, metric_weight in bucket_config["metrics"].items():
                # Get the metric value
                metric_value = self._get_metric_value(player, metric_name)

                if metric_value is not None:
                    # Calculate percentile among peers
                    percentile = self._calculate_metric_percentile(
                        metric_value, metric_name, player, all_players
                    )

                    # Add weighted score
                    bucket_score += percentile * metric_weight
                    bucket_details[metric_name] = {
                        "value": metric_value,
                        "percentile": percentile
                    }

            skill_scores[bucket_name] = {
                "score": bucket_score,
                "percentile": bucket_score,  # Already 0-100 scale
                "details": bucket_details,
                "display_name": bucket_config["display_name"],
                "icon": bucket_config["icon"]
            }

        return skill_scores

    def _get_metric_value(self, player: Dict, metric_name: str) -> Optional[float]:
        """Get a metric value from player data."""

        # Direct mapping from query results
        metric_map = {
            "contact_rate": "contact_rate",
            "whiff_rate": "whiff_rate",
            "chase_rate": "chase_rate",
            "discipline_score": "discipline_score",
            "hard_hit_rate": "hard_hit_rate",
            "pull_fly_ball_rate": "pull_fly_ball_rate",
            "line_drive_rate": "line_drive_rate",
            "productive_swing_rate": "productive_swing_rate",
            "two_strike_contact": "two_strike_contact",
            "spray_ability": "spray_ability",
            "in_play_rate": "in_play_rate",
            "exit_velo_90th": "exit_velo_90th",
            "home_run_rate": "home_run_rate",
            "iso": "iso",
            "slg": "slugging_pct",
            "walk_rate": "walk_rate",
            "strikeout_rate": "strikeout_rate",
            "batting_avg": "batting_avg",
            "obp": "on_base_pct"
        }

        if metric_name in metric_map:
            return player.get(metric_map[metric_name])

        # Calculate derived metrics
        if metric_name == "stolen_base_rate":
            # We don't have stolen base data in pitch table, return default
            return 0.0
        elif metric_name == "sb_success_rate":
            return 0.75  # Default success rate
        elif metric_name == "triples_rate":
            ab = player.get('total_ab', 0)
            if ab > 0:
                return player.get('total_3b', 0) / ab
            return 0.0
        elif metric_name == "ground_speed":
            return 0.0  # No sprint speed available

        return None

    def _calculate_metric_percentile(
        self,
        value: float,
        metric_name: str,
        player: Dict,
        all_players: List[Dict]
    ) -> float:
        """Calculate percentile for a metric among peer group."""

        # Get peer values (same level or all if multi-level)
        peer_values = []
        player_level = player.get('level')

        for p in all_players:
            # Include if same level or if looking at all levels
            if player_level is None or p.get('level') == player_level:
                peer_value = self._get_metric_value(p, metric_name)
                if peer_value is not None:
                    peer_values.append(peer_value)

        if not peer_values:
            return 50.0  # Default to median if no peers

        # Invert for negative metrics (lower is better)
        if metric_name in ["strikeout_rate", "whiff_rate", "chase_rate"]:
            # Invert: best value gets 100, worst gets 0
            rank = sum(1 for v in peer_values if v > value)
        else:
            rank = sum(1 for v in peer_values if v < value)

        percentile = (rank / len(peer_values)) * 100
        return percentile

    def _calculate_overall_score(self, skill_scores: Dict[str, Dict]) -> float:
        """Calculate weighted overall score from skill buckets."""

        total_score = 0
        total_weight = 0

        for bucket_name, bucket_config in self.HITTER_SKILL_BUCKETS.items():
            if bucket_name in skill_scores:
                score = skill_scores[bucket_name]["score"]
                weight = bucket_config["weight"]
                total_score += score * weight
                total_weight += weight

        if total_weight > 0:
            return total_score / total_weight
        return 0

    def _calculate_age_adjustment(self, player: Dict) -> float:
        """Calculate age-based adjustment factor."""

        age = player.get('age', 0)
        level = player.get('level')

        if not age or not level or level not in self.AGE_LEVEL_ADJUSTMENTS:
            return 0

        level_data = self.AGE_LEVEL_ADJUSTMENTS[level]
        avg_age = level_data["avg_age"]
        factor = level_data["factor"]

        # Calculate age difference from level average
        age_diff = age - avg_age

        # Apply adjustment (negative diff = younger = bonus)
        adjustment = age_diff * factor

        return adjustment

    def _calculate_percentiles(self, players: List[Dict]) -> List[Dict]:
        """Calculate percentile rankings for all scores."""

        if not players:
            return players

        # Get all scores for percentile calculation
        overall_scores = [p['overall_score'] for p in players]
        adjusted_scores = [p['adjusted_score'] for p in players]

        for player in players:
            # Overall percentile
            player['overall_percentile'] = (
                sum(1 for s in overall_scores if s < player['overall_score']) /
                len(overall_scores)
            ) * 100

            # Adjusted percentile
            player['adjusted_percentile'] = (
                sum(1 for s in adjusted_scores if s < player['adjusted_score']) /
                len(adjusted_scores)
            ) * 100

        return players