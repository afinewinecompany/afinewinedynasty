"""
Statline Ranking Service

Provides in-season statistical rankings using composite scores from MILB data.
Focuses on discipline and power scores as primary ranking metrics.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, and_
import numpy as np
import logging

logger = logging.getLogger(__name__)


class StatlineRankingService:
    """
    Service for calculating in-season prospect rankings based on composite scores.
    Uses simplified queries focusing on discipline and power metrics.
    """

    # Age adjustment factors (negative means younger is better)
    AGE_LEVEL_ADJUSTMENTS = {
        "AAA": {"avg_age": 24.5, "factor": -0.05},
        "AA": {"avg_age": 23.0, "factor": -0.08},
        "A+": {"avg_age": 21.5, "factor": -0.10},
        "A": {"avg_age": 20.5, "factor": -0.12},
        "ROK": {"avg_age": 18.5, "factor": -0.15}
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
        Calculate statline rankings using composite discipline and power scores.

        Args:
            level: Optional level filter (AAA, AA, A+, A, ROK)
            min_plate_appearances: Minimum PAs to qualify
            season: Season to analyze
            include_pitch_data: Whether to include pitch-level metrics

        Returns:
            List of ranked prospects with composite scores
        """
        logger.info(f"Calculating Statline rankings for {season} season using composite scores")

        # Step 1: Try to get data from MILB pitch tables first
        if include_pitch_data:
            players_data = await self._get_players_with_composite_scores(
                level, min_plate_appearances, season
            )
        else:
            players_data = []

        # Step 2: Fallback to prospect_stats if no pitch data
        if not players_data:
            logger.info("No pitch data found, using prospect_stats fallback")
            players_data = await self._get_players_from_prospect_stats(
                level, min_plate_appearances
            )

        if not players_data:
            logger.warning("No qualified players found")
            return []

        logger.info(f"Found {len(players_data)} qualified players")

        # Step 3: Calculate rankings based on composite scores
        for player in players_data:
            # Calculate overall score (weighted average of discipline and power)
            discipline = player.get('discipline_score', 50)
            power = player.get('power_score', 50)

            # Weight discipline slightly more for overall ranking
            player['overall_score'] = (discipline * 0.55) + (power * 0.45)

            # Add age adjustment
            age_adj = self._calculate_age_adjustment(player)
            player['age_adjustment'] = age_adj
            player['adjusted_score'] = player['overall_score'] * (1 + age_adj)

        # Step 4: Sort and rank
        players_data.sort(key=lambda x: x['adjusted_score'], reverse=True)

        for i, player in enumerate(players_data):
            player['rank'] = i + 1

            # Add letter grades for visual display
            player['discipline_grade'] = self._score_to_grade(player.get('discipline_score', 50))
            player['power_grade'] = self._score_to_grade(player.get('power_score', 50))
            player['overall_grade'] = self._score_to_grade(player['overall_score'])

        return players_data

    async def _get_players_with_composite_scores(
        self,
        level: Optional[str],
        min_pa: int,
        season: int
    ) -> List[Dict]:
        """Get players with simplified composite scores from MILB pitch data."""

        # Simplified query focusing on key metrics for composite scores
        base_query = """
        WITH player_basics AS (
            -- First, get basic player info and check if they have enough PAs
            SELECT
                bp.mlb_batter_id,
                bp.mlb_batter_name as name,
                bp.level,
                COUNT(DISTINCT bp.game_id) as games,
                COUNT(*) as total_pitches,
                COUNT(DISTINCT CASE
                    WHEN bp.event_result IS NOT NULL
                    THEN bp.game_id || '_' || bp.pa_of_inning
                END) as total_pa,
                -- Basic counting stats
                SUM(CASE WHEN bp.event_result IN ('single', 'double', 'triple', 'home_run') THEN 1 ELSE 0 END) as hits,
                SUM(CASE WHEN bp.event_result = 'home_run' THEN 1 ELSE 0 END) as home_runs,
                SUM(CASE WHEN bp.event_result = 'walk' THEN 1 ELSE 0 END) as walks,
                SUM(CASE WHEN bp.event_result = 'strikeout' THEN 1 ELSE 0 END) as strikeouts
            FROM milb_batter_pitches bp
            WHERE bp.season = :season
                {level_filter}
            GROUP BY bp.mlb_batter_id, bp.mlb_batter_name, bp.level
            HAVING COUNT(DISTINCT CASE
                WHEN bp.event_result IS NOT NULL
                THEN bp.game_id || '_' || bp.pa_of_inning
            END) >= :min_pa
        ),
        player_metrics AS (
            -- Then calculate the metrics needed for composite scores
            SELECT
                pb.*,
                p.id as prospect_id,
                p.age,
                p.position,
                p.organization,

                -- Traditional stats
                CAST(pb.hits AS FLOAT) / NULLIF(pb.total_pa - pb.walks, 0) * 100 as batting_avg,
                CAST(pb.walks AS FLOAT) / NULLIF(pb.total_pa, 0) * 100 as walk_rate,
                CAST(pb.strikeouts AS FLOAT) / NULLIF(pb.total_pa, 0) * 100 as strikeout_rate,
                CAST(pb.home_runs AS FLOAT) / NULLIF(pb.total_pa, 0) * 100 as home_run_rate,

                -- Get pitch-level metrics for discipline score
                (SELECT
                    -- Contact rate (contact/swings)
                    AVG(CASE WHEN bp2.swing = true AND bp2.contact = true THEN 100.0
                            WHEN bp2.swing = true THEN 0.0
                            ELSE NULL END)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season) as contact_rate,

                (SELECT
                    -- Chase rate (swings outside zone)
                    AVG(CASE WHEN bp2.zone > 9 AND bp2.swing = true THEN 100.0
                            WHEN bp2.zone > 9 THEN 0.0
                            ELSE NULL END)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season) as chase_rate,

                -- Get batted ball metrics for power score
                (SELECT
                    COUNT(*) FILTER (WHERE bp2.hardness = 'hard') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp2.hardness IS NOT NULL), 0)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season
                    AND bp2.contact = true
                    AND bp2.foul = false) as hard_hit_rate,

                (SELECT
                    COUNT(*) FILTER (WHERE bp2.trajectory = 'fly_ball') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp2.trajectory IS NOT NULL), 0)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season
                    AND bp2.contact = true
                    AND bp2.foul = false) as fly_ball_rate

            FROM player_basics pb
            LEFT JOIN prospects p ON CAST(p.mlb_player_id AS INTEGER) = pb.mlb_batter_id
        )
        SELECT
            *,
            -- Calculate DISCIPLINE SCORE (0-100)
            GREATEST(0, LEAST(100,
                COALESCE(contact_rate, 75) * 0.30 +           -- 30% weight on contact
                (100 - COALESCE(chase_rate, 35)) * 0.30 +     -- 30% weight on not chasing
                COALESCE(walk_rate, 8) * 3.0 +                -- 24% weight on walks (scaled)
                (100 - LEAST(strikeout_rate, 40)) * 0.16      -- 16% weight on avoiding Ks
            )) as discipline_score,

            -- Calculate POWER SCORE (0-100)
            GREATEST(0, LEAST(100,
                COALESCE(hard_hit_rate, 10) * 2.5 +           -- 25% weight (10% avg -> 25 pts)
                COALESCE(home_run_rate * 20, 0) +             -- 20% weight (5% HR rate -> 100 pts)
                COALESCE(fly_ball_rate, 30) * 1.5 +           -- 45% weight (30% avg -> 45 pts)
                CASE
                    WHEN batting_avg > 30 THEN 10
                    WHEN batting_avg > 25 THEN 5
                    ELSE 0
                END                                            -- 10% bonus for high avg
            )) as power_score

        FROM player_metrics
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

            players = []
            for row in rows:
                player = dict(row._mapping)
                players.append(player)

            return players

        except Exception as e:
            logger.error(f"Error querying MILB pitch data: {e}")
            return []

    async def _get_players_from_prospect_stats(
        self,
        level: Optional[str],
        min_pa: int
    ) -> List[Dict]:
        """Fallback to prospect_stats table with estimated composite scores."""

        query = """
        WITH latest_stats AS (
            SELECT
                p.id as prospect_id,
                p.mlb_player_id as mlb_batter_id,
                p.name,
                p.position,
                p.age,
                p.level,
                p.organization,
                ps.games_played as games,

                -- Estimate PAs
                GREATEST(
                    COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0),
                    CAST(COALESCE(ps.at_bats, 0) * 1.15 AS INT)
                ) as total_pa,

                -- Basic stats
                ps.at_bats,
                ps.hits,
                ps.home_runs,
                ps.walks,
                ps.strikeouts,
                ps.batting_avg * 100 as batting_avg,
                ps.on_base_pct * 100 as on_base_pct,
                ps.slugging_pct * 100 as slugging_pct,

                -- Calculate rates
                CAST(ps.walks AS FLOAT) / NULLIF(GREATEST(ps.at_bats + ps.walks, ps.at_bats * 1.15), 0) * 100 as walk_rate,
                CAST(ps.strikeouts AS FLOAT) / NULLIF(GREATEST(ps.at_bats + ps.walks, ps.at_bats * 1.15), 0) * 100 as strikeout_rate,
                CAST(ps.home_runs AS FLOAT) / NULLIF(ps.at_bats, 0) * 100 as home_run_rate,

                ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ps.date_recorded DESC) as rn
            FROM prospect_stats ps
            JOIN prospects p ON p.id = ps.prospect_id
            WHERE ps.at_bats > 0
                {level_filter}
        )
        SELECT
            *,
            -- Estimate DISCIPLINE SCORE from traditional stats
            GREATEST(0, LEAST(100,
                50 +                                           -- Base score
                (walk_rate - 8) * 2 +                        -- Walk bonus/penalty
                (20 - strikeout_rate) * 1.5 +                -- K rate bonus/penalty
                CASE
                    WHEN on_base_pct > 35 THEN 10
                    WHEN on_base_pct > 32 THEN 5
                    ELSE 0
                END
            )) as discipline_score,

            -- Estimate POWER SCORE from traditional stats
            GREATEST(0, LEAST(100,
                30 +                                           -- Base score
                home_run_rate * 15 +                          -- HR rate heavily weighted
                (slugging_pct - batting_avg) * 100 +          -- ISO proxy
                CASE
                    WHEN slugging_pct > 45 THEN 15
                    WHEN slugging_pct > 40 THEN 10
                    WHEN slugging_pct > 35 THEN 5
                    ELSE 0
                END
            )) as power_score,

            -- Default pitch metrics (not available)
            75.0 as contact_rate,
            35.0 as chase_rate,
            10.0 as hard_hit_rate,
            30.0 as fly_ball_rate

        FROM latest_stats
        WHERE rn = 1
            AND total_pa >= :min_pa
        ORDER BY total_pa DESC
        """

        level_filter = f"AND p.level = :level" if level else ""
        query = query.replace("{level_filter}", level_filter)

        params = {"min_pa": min_pa}
        if level:
            params["level"] = level

        try:
            result = await self.db.execute(text(query), params)
            rows = result.fetchall()

            players = []
            for row in rows:
                player = dict(row._mapping)
                players.append(player)

            return players
        except Exception as e:
            logger.error(f"Error querying prospect_stats: {e}")
            return []

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

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""

        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "A-"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "B-"
        elif score >= 65:
            return "C+"
        elif score >= 60:
            return "C"
        elif score >= 55:
            return "C-"
        elif score >= 50:
            return "D+"
        elif score >= 45:
            return "D"
        else:
            return "D-"