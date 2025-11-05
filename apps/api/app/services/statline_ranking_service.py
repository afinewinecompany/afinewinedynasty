"""
Statline Ranking Service

Provides in-season statistical rankings using game logs and pitch-level data.
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
    Combines traditional stats, pitch-level metrics, and age adjustments.
    """

    # Skill bucket definitions for hitters
    HITTER_SKILL_BUCKETS = {
        "power": {
            "metrics": {
                "home_run_rate": 0.25,      # HR/AB
                "iso": 0.25,                 # SLG - AVG
                "slg": 0.15,                 # Slugging %
                "hard_hit_rate": 0.20,       # From pitch data
                "pull_fly_ball_rate": 0.15   # From pitch data
            },
            "weight": 0.20,
            "display_name": "Power",
            "icon": "⚡"
        },
        "discipline": {
            "metrics": {
                "walk_rate": 0.25,           # BB/PA
                "strikeout_rate": 0.25,      # K/PA (inverted)
                "chase_rate": 0.20,          # From pitch data (inverted)
                "discipline_score": 0.30     # From pitch data
            },
            "weight": 0.20,
            "display_name": "Discipline",
            "icon": "👁"
        },
        "contact": {
            "metrics": {
                "batting_avg": 0.25,         # H/AB
                "contact_rate": 0.30,        # From pitch data
                "whiff_rate": 0.25,          # From pitch data (inverted)
                "line_drive_rate": 0.20      # From pitch data
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
                "ground_speed": 0.15         # Placeholder for sprint speed
            },
            "weight": 0.15,
            "display_name": "Speed",
            "icon": "💨"
        },
        "approach": {
            "metrics": {
                "obp": 0.25,                         # On-base %
                "productive_swing_rate": 0.25,       # From pitch data
                "two_strike_contact": 0.25,          # From pitch data
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

    # Multi-level weighting (when player played multiple levels)
    MULTI_LEVEL_WEIGHTS = {
        "plate_appearances": 0.7,  # Weight by PA
        "recency": 0.3             # Weight by how recent
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
        Calculate comprehensive statline rankings for prospects.

        Args:
            level: Optional level filter (AAA, AA, A+, A, ROK)
            min_plate_appearances: Minimum PAs to qualify
            season: Season to analyze
            include_pitch_data: Whether to include pitch-level metrics

        Returns:
            List of ranked prospects with skill scores
        """
        logger.info(f"Calculating Statline rankings for {season} season")

        # Step 1: Get qualified players with their stats
        players_data = await self._get_qualified_players(
            level, min_plate_appearances, season
        )

        if not players_data:
            logger.warning("No qualified players found")
            return []

        # Step 2: Get pitch-level metrics if requested
        if include_pitch_data:
            pitch_metrics = await self._get_pitch_metrics_for_players(
                [p['mlb_player_id'] for p in players_data],
                season
            )
            # Merge pitch metrics
            for player in players_data:
                player['pitch_metrics'] = pitch_metrics.get(player['mlb_player_id'], {})

        # Step 3: Calculate skill bucket scores
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

        # Step 4: Calculate percentiles and rank
        scored_players = self._calculate_percentiles(scored_players)
        scored_players.sort(key=lambda x: x['adjusted_score'], reverse=True)

        # Add final rankings
        for i, player in enumerate(scored_players):
            player['rank'] = i + 1

        return scored_players

    async def _get_qualified_players(
        self,
        level: Optional[str],
        min_pa: int,
        season: int
    ) -> List[Dict]:
        """Get players who meet minimum plate appearance threshold."""

        # Build the query for aggregate season stats using prospect_stats table
        base_query = """
        WITH latest_stats AS (
            SELECT
                ps.prospect_id,
                p.mlb_player_id,
                p.name,
                p.position,
                p.age,
                p.level,
                ps.games_played as games,
                -- Estimate PAs from ABs (assuming ~1.1 PA per AB)
                CAST(ps.at_bats * 1.1 AS INT) as total_pa,
                ps.at_bats as total_ab,
                ps.hits as total_hits,
                ps.home_runs as total_hr,
                ps.rbi as total_rbi,
                ps.batting_avg,
                ps.on_base_pct,
                ps.slugging_pct,
                ps.woba,
                ps.wrc_plus,
                -- Calculate additional stats
                CAST(ps.hits - ps.home_runs AS FLOAT) * 0.15 as total_2b, -- Estimate doubles
                CAST(ps.hits - ps.home_runs AS FLOAT) * 0.03 as total_3b, -- Estimate triples
                CAST(ps.at_bats * 0.08 AS INT) as total_bb, -- Estimate walks from typical BB rate
                CAST(ps.at_bats * 0.22 AS INT) as total_k,  -- Estimate strikeouts
                0 as total_sb, -- No SB data available
                0 as total_cs,
                0 as total_hbp,
                ps.on_base_pct as obp,
                ps.slugging_pct as slg,
                (ps.on_base_pct + ps.slugging_pct) as ops,
                p.level as levels_played,
                ps.date_recorded as last_game,
                ROW_NUMBER() OVER (PARTITION BY ps.prospect_id ORDER BY ps.date_recorded DESC) as rn
            FROM prospect_stats ps
            JOIN prospects p ON p.id = ps.prospect_id
            WHERE
                EXTRACT(YEAR FROM ps.date_recorded) = :season
                {level_filter}
                AND ps.at_bats >= :min_pa  -- Using at_bats as proxy for PAs
        )
        SELECT
            prospect_id,
            mlb_player_id,
            name,
            position,
            age,
            level,
            games,
            total_pa,
            total_ab,
            total_hits,
            total_2b,
            total_3b,
            total_hr,
            total_rbi,
            total_bb,
            total_k,
            batting_avg,
            on_base_pct as on_base_pct,
            slugging_pct as slugging_pct,
            CAST(total_bb AS FLOAT) / NULLIF(total_pa, 0) as walk_rate,
            CAST(total_k AS FLOAT) / NULLIF(total_pa, 0) as strikeout_rate,
            CAST(total_hr AS FLOAT) / NULLIF(total_ab, 0) as home_run_rate,
            -- ISO (Isolated Power)
            (slugging_pct - batting_avg) as iso,
            levels_played
        FROM latest_stats
        WHERE rn = 1  -- Get only the latest stats for each player
        ORDER BY ops DESC
        """

        level_filter = f"AND p.level = :level" if level else ""
        query = base_query.replace("{level_filter}", level_filter)

        params = {"season": season, "min_pa": min_pa}
        if level:
            params["level"] = level

        result = await self.db.execute(text(query), params)
        rows = result.fetchall()

        # Convert to dictionaries
        players = []
        for row in rows:
            player = dict(row._mapping)
            players.append(player)

        logger.info(f"Found {len(players)} qualified players")
        return players

    async def _get_pitch_metrics_for_players(
        self,
        player_ids: List[int],
        season: int
    ) -> Dict[int, Dict]:
        """Get pitch-level metrics for a list of players."""

        from .pitch_data_aggregator_with_batted_balls import BattedBallPitchDataAggregator

        metrics = {}
        aggregator = BattedBallPitchDataAggregator(self.db)

        for player_id in player_ids:
            try:
                # Get comprehensive metrics including discipline and power scores
                player_metrics = await aggregator.get_comprehensive_hitter_metrics(
                    str(player_id),
                    level=None,  # Will get all levels
                    days=365     # Full season
                )

                if player_metrics:
                    metrics[player_id] = player_metrics
            except Exception as e:
                logger.warning(f"Failed to get pitch metrics for player {player_id}: {e}")
                continue

        logger.info(f"Retrieved pitch metrics for {len(metrics)} players")
        return metrics

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

        # Check if it's from pitch data
        if metric_name in ["contact_rate", "whiff_rate", "chase_rate",
                          "discipline_score", "hard_hit_rate", "pull_fly_ball_rate",
                          "line_drive_rate", "productive_swing_rate",
                          "two_strike_contact", "spray_ability"]:
            pitch_metrics = player.get('pitch_metrics', {})

            if metric_name == "discipline_score":
                return pitch_metrics.get('discipline_score')
            elif metric_name == "hard_hit_rate":
                return pitch_metrics.get('hard_hit_rate')
            elif metric_name == "pull_fly_ball_rate":
                return pitch_metrics.get('pull_fly_ball_rate')
            elif metric_name == "line_drive_rate":
                return pitch_metrics.get('line_drive_rate')
            elif metric_name == "contact_rate":
                return pitch_metrics.get('contact_rate')
            elif metric_name == "whiff_rate":
                return pitch_metrics.get('whiff_rate')
            elif metric_name == "chase_rate":
                return pitch_metrics.get('chase_rate')
            elif metric_name == "productive_swing_rate":
                return pitch_metrics.get('productive_swing_rate')
            elif metric_name == "two_strike_contact":
                return pitch_metrics.get('two_strike_contact')
            elif metric_name == "spray_ability":
                return pitch_metrics.get('spray_balance_score')
            # Return None if pitch metrics not available
            return None

        # Game log stats
        elif metric_name == "home_run_rate":
            return player.get('home_run_rate', 0.0)
        elif metric_name == "iso":
            return player.get('iso', 0.0)
        elif metric_name == "slg":
            return player.get('slugging_pct')
        elif metric_name == "walk_rate":
            return player.get('walk_rate')
        elif metric_name == "strikeout_rate":
            return player.get('strikeout_rate')
        elif metric_name == "batting_avg":
            return player.get('batting_avg')
        elif metric_name == "obp":
            return player.get('on_base_pct')
        elif metric_name == "stolen_base_rate":
            # We don't have SB data, return 0
            return 0.0
        elif metric_name == "sb_success_rate":
            # We don't have SB data, return 0
            return 0.0
        elif metric_name == "triples_rate":
            # Use estimated triples
            ab = player.get('total_ab', 0)
            if ab > 0:
                return player.get('total_3b', 0) / ab
            return 0.0
        elif metric_name == "ground_speed":
            # No ground speed data available
            return 0.0

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